
from fastapi import APIRouter, Depends, Form, HTTPException, Response, Request 
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from datetime import datetime, timedelta
from jose import jwt
from database import User, get_db, pwd_context
from sqlalchemy.orm import Session
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

router = APIRouter()

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")  # Matches main.py
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    logger.info(f"Creating token with exp: {expire} (UTC: {datetime.utcnow()})")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login")
async def login_post(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    response: Response = None
):
    logger.info(f"Login request: username={username}")
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password_hash):
        logger.warning(f"Login failed for username={username}")
        return JSONResponse({"success": False, "error": "Invalid username or password"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": username, "is_admin": user.is_admin},
        expires_delta=access_token_expires
    )

    resp = JSONResponse({
        "success": True,
        "message": "Login successful!",
        "username": username,
        "is_admin": user.is_admin
    })
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="none",  # For cross-origin cookies
        secure=True,       # Must be True for HTTPS (ngrok)
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    logger.info(f"Cookie set in login: access_token={access_token[:20]}...")
    return resp

@router.get("/api/me")
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    try:
        cookies = request.cookies
        logger.info(f"/api/me cookies: {cookies}")
        token = cookies.get("access_token")
        logger.info(f"/api/me access_token: {token[:20] if token else 'None'}")
        if not token:
            logger.warning("No access_token cookie provided in /api/me")
            return JSONResponse({"success": False, "error": "No token provided"})

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            logger.info(f"/api/me JWT payload: {payload}")
        except jwt.ExpiredSignatureError as e:
            logger.error(f"JWT error in /api/me: Signature has expired: {str(e)}")
            return JSONResponse({"success": False, "error": "Token expired"})
        except jwt.JWTError as e:
            logger.error(f"JWT error in /api/me: {str(e)}")
            return JSONResponse({"success": False, "error": "Invalid token"})

        username: str = payload.get("sub")
        if not username:
            logger.warning("Invalid token: No username in payload")
            return JSONResponse({"success": False, "error": "Invalid token"})

        user = db.query(User).filter(User.username == username).first()
        if not user:
            logger.warning(f"User not found: username={username}")
            return JSONResponse({"success": False, "error": "User not found"})

        logger.info(f"User fetched: username={username}, is_admin={user.is_admin}")
        return JSONResponse({
            "success": True,
            "user": {"username": user.username, "is_admin": user.is_admin}
        })
    except Exception as e:
        logger.error(f"General error in /api/me: {str(e)}")
        return JSONResponse({"success": False, "error": "Internal error"})
    

@router.post("/signup")
async def signup_post(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Signup request: username={username}, email={email}")
    
    # Валидация confirm_password (вручную, без Pydantic)
    if password != confirm_password:
        logger.warning("Passwords do not match")
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    # Дополнительная валидация пароля (опционально)
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Проверки на существование
    if db.query(User).filter(User.username == username).first():
        logger.warning(f"Username already exists: {username}")
        raise HTTPException(status_code=400, detail="Username already exists")
    
    if db.query(User).filter(User.email == email).first():
        logger.warning(f"Email already exists: {email}")
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Хэшируем пароль
    hashed_password = pwd_context.hash(password)
    
    # Создаём пользователя
    new_user = User(
        username=username,
        email=email,
        password_hash=hashed_password,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"New user created: id={new_user.id}, username={new_user.username}")
    
    # Возвращаем JSON как в login
    return JSONResponse({
        "success": True,
        "message": "Registration successful! You can now log in.",
        "username": new_user.username
    })