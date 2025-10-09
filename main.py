from fastapi import FastAPI, Request, HTTPException, Depends, Form, status, File, UploadFile, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import List, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import requests
from dotenv import load_dotenv
from jose import JWTError, jwt
from auth import router as auth_router
from database import User, CartItem, Product, get_db, pwd_context, PasswordReset
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import logging
from werkzeug.utils import secure_filename
from database import Order, OrderItem


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

app = FastAPI()

# JWT настройки
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
ADMIN_EMAIL = os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", ""))
ADMIN_PASSWORD = os.getenv("SMTP_PASSWORD", "")

def get_paypal_base_url():
    """Возвращает базовый URL для PayPal в зависимости от режима"""
    if PAYPAL_MODE == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    else:
        return "https://api-m.paypal.com"

def get_paypal_access_token():
    base_url = get_paypal_base_url()
    url = f"{base_url}/v1/oauth2/token"
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}
    auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)
    logger.info(f"Requesting PayPal token from: {url}")
    try:
        response = requests.post(url, headers=headers, data=data, auth=auth, timeout=10)
        if response.status_code == 200:
            token = response.json()["access_token"]
            logger.info("PayPal token acquired successfully")
            return token
        else:
            logger.error(f"PayPal token error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail="Ошибка аутентификации PayPal")
    except requests.exceptions.RequestException as e:
        logger.error(f"PayPal request error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка соединения с PayPal")

# Подключение роутера auth
app.include_router(auth_router)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fastestore.onrender.com", "https://fastestore.onrender.com/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")
app.mount("/image", StaticFiles(directory=os.path.join(BASE_DIR, "image")), name="image")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Шаблоны
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Настройки GetResponse
GETRESPONSE_API_KEY = os.getenv("GETRESPONSE_API_KEY")
GETRESPONSE_LIST_ID = os.getenv("GETRESPONSE_LIST_ID")
GETRESPONSE_FROM_FIELD_ID = os.getenv("GETRESPONSE_FROM_FIELD_ID")

# Настройка директории для загрузки файлов
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
# Создаем папку, если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.on_event("startup")
async def startup():
    try:
        logger.info(f"API Key: {GETRESPONSE_API_KEY}")
        logger.info(f"List ID: {GETRESPONSE_LIST_ID}")
        logger.info(f"From Field ID: {GETRESPONSE_FROM_FIELD_ID}")
        if not all([GETRESPONSE_API_KEY, GETRESPONSE_LIST_ID, GETRESPONSE_FROM_FIELD_ID]):
            raise ValueError("Одна или несколько переменных окружения GetResponse отсутствуют")
        
        # Проверка SMTP
        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            logger.warning("SMTP credentials not configured - email sending may fail")
        
        # Rate limiting отключён (Redis не используется)
        logger.info("Rate limiting отключён")
        
    except Exception as e:
        logger.error(f"Ошибка при старте: {e}")
        raise
# Модели
class ContactForm(BaseModel):
    email: str
    phone: str
    message: str

class SubscribeForm(BaseModel):
    email: EmailStr

class NewsletterForm(BaseModel):
    subject: str
    content: str

class CartItemBase(BaseModel):
    product_id: str
    name: str
    price: float
    image: str
    quantity: int

    class Config:
        from_attributes = True

class CartItemCreate(CartItemBase):
    pass

class CartItemUpdate(BaseModel):
    quantity: int

class CartResponse(BaseModel):
    success: bool
    data: List[CartItemBase] = []
    error: str | None = None

class ProductBase(BaseModel):
    id: int
    name: str
    price: float
    image: str
    category: str | None = None
    is_new_arrival: bool

    class Config:
        from_attributes = True

class ProductsResponse(BaseModel):
    success: bool
    data: List[ProductBase]
    total: int
    page: int
    limit: int

class ProductResponse(BaseModel): 
    success: bool
    data: ProductBase  # Для одного продукта

class UserInfo(BaseModel):
    username: str
    is_admin: bool

class ForgotPasswordForm(BaseModel):
    email: EmailStr

class ResetPasswordForm(BaseModel):
    password: str
    confirm_password: str

# Получение текущего пользователя
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительный токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = request.cookies.get("access_token")
    logger.info(f"Token from cookie in get_current_user: {token[:20] if token else 'None'}...")
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"Token payload: {payload}")
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None

async def get_current_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещен: только для админов")
    return current_user

# Функция для отправки email (общая для contact и forgot)
def send_email(to_email: str, subject: str, body: str, from_email: str = None):
    from_email = from_email or ADMIN_EMAIL
    if not from_email or not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="SMTP credentials not configured")
    
    logger.info(f"Attempting SMTP connection: email={from_email}")
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    server = smtplib.SMTP('smtp.yandex.ru', 587)
    server.set_debuglevel(1)
    logger.info("Connecting to smtp.yandex.ru:587...")
    server.starttls()
    logger.info("TLS activated")
    server.login(from_email, ADMIN_PASSWORD)
    logger.info("SMTP authentication successful")
    text = msg.as_string()
    server.sendmail(from_email, to_email, text)
    logger.info("Email sent successfully")
    server.quit()

# Маршруты
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    logger.info(f"Request to /: cookies={request.cookies}")
    return templates.TemplateResponse("index.html", {"request": request, "user": current_user})

@app.get("/shop", response_class=HTMLResponse)
async def shop(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    logger.info(f"Request to /shop: cookies={request.cookies}")
    return templates.TemplateResponse("shop.html", {"request": request, "user": current_user})

@app.get("/api/me", response_model=dict)
async def get_me(request: Request, db: Session = Depends(get_db)):
    logger.info(f"Request to /api/me: cookies={request.cookies}")
    try:
        user = await get_current_user(request, db)
        return {"success": True, "user": {"username": user.username, "is_admin": user.is_admin}}
    except HTTPException:
        return {"success": False, "user": None}

@app.exception_handler(422)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.post("/contact")
async def contact_submit(form_data: ContactForm):
    try:
        subject = "Новое сообщение с формы контактов"
        body = f"""
        Новое сообщение с сайта:

        Email отправителя: {form_data.email}
        Телефон: {form_data.phone}
        Сообщение: {form_data.message}

        Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        send_email(ADMIN_EMAIL, subject, body)
        return {"success": True, "message": "Сообщение отправлено успешно"}
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка аутентификации: неверный email или пароль")
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке сообщения: {str(e)}")

@app.post("/subscribe")
async def subscribe(form_data: SubscribeForm):
    try:
        url = "https://api.getresponse.com/v3/contacts"
        headers = {
            "X-Auth-Token": f"api-key {GETRESPONSE_API_KEY}",
            "Client-Id": "eStoreApp",
            "Content-Type": "application/json"
        }
        data = {
            "name": form_data.email.split('@')[0],
            "email": form_data.email,
            "campaign": {"campaignId": GETRESPONSE_LIST_ID},
            "dayOfCycle": 0
        }
        logger.info(f"Sending to GetResponse: {data}")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        logger.info(f"GetResponse response: status={response.status_code}, body={response.text}")
        if response.status_code == 200 or response.status_code == 202:
            return {"success": True, "message": "Подписка создана! Проверьте email для подтверждения."}
        elif response.status_code == 429:
            logger.error("GetResponse rate limit exceeded")
            raise HTTPException(status_code=429, detail="Слишком много запросов, попробуйте позже")
        elif response.status_code == 409:
            return {"success": True, "message": "Этот email уже подписан."}
        else:
            try:
                error_msg = response.json().get("message", f"Неизвестная ошибка (статус {response.status_code})")
            except ValueError:
                error_msg = f"Невалидный или пустой ответ от GetResponse: {response.text or 'пусто'}"
            logger.error(f"GetResponse error: {error_msg}")
            raise HTTPException(status_code=response.status_code, detail=f"Ошибка подписки: {error_msg}")
    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to GetResponse")
        raise HTTPException(status_code=504, detail="Таймаут соединения с GetResponse, попробуйте позже")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to GetResponse API: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка соединения с GetResponse: {str(e)}")
    except Exception as e:
        logger.error(f"General error: {e}")
        raise HTTPException(status_code=500, detail=f"Попробуйте позже: {str(e)}")

@app.post("/send-newsletter")
async def send_newsletter(form_data: NewsletterForm):
    try:
        url = "https://api.getresponse.com/v3/newsletters"
        headers = {
            "X-Auth-Token": f"api-key {GETRESPONSE_API_KEY}",
            "Client-Id": "eStoreApp",
            "Content-Type": "application/json"
        }
        html_content = f"""
        <html>
            <body>
                <h2>{form_data.subject}</h2>
                <p>{form_data.content}</p>
                <p><a href="https://fastestore.onrender.com">Посетите наш магазин</a></p>
                <p><small>Отписаться: {{unsubscribe}}</small></p>
            </body>
        </html>
        """
        newsletter_data = {
            "name": f"Newsletter {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "subject": form_data.subject,
            "fromField": {"fromFieldId": GETRESPONSE_FROM_FIELD_ID},
            "campaign": {"campaignId": GETRESPONSE_LIST_ID},
            "content": {
                "html": html_content,
                "plain": form_data.content
            },
            "sendSettings": {
                "selectedCampaigns": [GETRESPONSE_LIST_ID],
                "excludedCampaigns": [],
                "selectedSegments": [],
                "selectedSuppressions": [],
                "timeTravel": "no",
                "perfectTiming": "no"
            }
        }
        logger.info(f"Sending newsletter: {newsletter_data}")
        response = requests.post(url, headers=headers, json=newsletter_data)
        logger.info(f"Newsletter response: status={response.status_code}, body={response.text}")
        if response.status_code == 201:
            return {"success": True, "message": "Рассылка успешно отправлена!"}
        else:
            try:
                error_msg = response.json().get("message", "Неизвестная ошибка")
            except ValueError:
                error_msg = f"Невалидный ответ от GetResponse: {response.text}"
            logger.error(f"Newsletter error: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Ошибка при отправке рассылки: {error_msg}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to GetResponse API: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка соединения с GetResponse: {str(e)}")
    except Exception as e:
        logger.error(f"General error: {e}")
        raise HTTPException(status_code=500, detail=f"Попробуйте позже: {str(e)}")

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()
        logger.info(f"Received webhook: {payload}")
        event_type = payload.get("type")
        if event_type == "subscription":
            logger.info("Subscription confirmed!")
        return {"success": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки вебхука")

@app.get("/api/products", response_model=ProductsResponse)
async def get_products(
    page: int = 1,
    limit: int = 9,
    sort: str = "default",
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Product)
        if category:
            query = query.filter(Product.category == category)
        if search:
            like_pattern = f"%{search}%"
            query = query.filter(Product.name.ilike(like_pattern))
        
        if sort == "price-low":
            query = query.order_by(asc(Product.price))
        elif sort == "price-high":
            query = query.order_by(desc(Product.price))
        elif sort == "latest":
            query = query.order_by(desc(Product.id))
        else:
            query = query.order_by(asc(Product.id))

        total = query.count()
        offset = (page - 1) * limit
        db_products = query.offset(offset).limit(limit).all()
        products = [ProductBase.from_orm(p) for p in db_products]
        
        return ProductsResponse(
            success=True,
            data=products,
            total=total,
            page=page,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения товаров: {str(e)}")

# Новый роут для single
@app.get("/api/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        product_data = ProductBase.from_orm(product)
        
        return ProductResponse(
            success=True,
            data=product_data
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения товара: {str(e)}")


@app.get("/product", response_class=HTMLResponse)
async def product(request: Request):
    return templates.TemplateResponse("product.html", {"request": request})


@app.get("/api/cart", response_model=CartResponse)
async def get_cart(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        logger.info(f"Fetching cart for user: {current_user.username}")
        items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
        cart_items = [CartItemBase.from_orm(item) for item in items]
        return CartResponse(success=True, data=cart_items)
    except Exception as e:
        logger.error(f"Error in get_cart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения корзины: {str(e)}")

@app.post("/api/cart", response_model=CartResponse)
async def add_to_cart(
    item: CartItemBase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Adding to cart for user {current_user.username}: {item}")
        existing_item = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == item.product_id
        ).first()

        if existing_item:
            existing_item.quantity += item.quantity
            db.commit()
            db.refresh(existing_item)
            logger.info(f"Updated existing item: {existing_item.product_id}, new quantity: {existing_item.quantity}")
        else:
            new_item = CartItem(
                user_id=current_user.id,
                product_id=item.product_id,
                name=item.name,
                price=item.price,
                image=item.image,
                quantity=item.quantity
            )
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            logger.info(f"Added new item: {new_item.product_id}")

        items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
        cart_items = [CartItemBase.from_orm(item) for item in items]
        return CartResponse(success=True, data=cart_items)
    except Exception as e:
        db.rollback()
        logger.error(f"Error in add_to_cart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка добавления в корзину: {str(e)}")

@app.put("/api/cart/{product_id}", response_model=CartResponse)
async def update_cart(product_id: str, update_data: CartItemUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        logger.info(f"Updating cart item {product_id} for user {current_user.username}: quantity={update_data.quantity}")
        if update_data.quantity < 1:
            raise HTTPException(status_code=400, detail="Количество должно быть больше 0")
        item = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == product_id
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Товар не найден в корзине")
        item.quantity = update_data.quantity
        db.commit()
        db.refresh(item)
        items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
        cart_items = [CartItemBase.from_orm(item) for item in items]
        return CartResponse(success=True, data=cart_items)
    except Exception as e:
        db.rollback()
        logger.error(f"Error in update_cart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления корзины: {str(e)}")

@app.delete("/api/cart/{product_id}", response_model=CartResponse)
async def remove_from_cart(product_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        logger.info(f"Removing cart item {product_id} for user {current_user.username}")
        item = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == product_id
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Товар не найден в корзине")
        db.delete(item)
        db.commit()
        items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
        cart_items = [CartItemBase.from_orm(item) for item in items]
        return CartResponse(success=True, data=cart_items)
    except Exception as e:
        db.rollback()
        logger.error(f"Error in remove_from_cart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления из корзины: {str(e)}")

# Админ-панель
@app.get("/administrator", response_class=HTMLResponse)
async def admin_login_page(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    logger.info(f"Request to /administrator: cookies={request.cookies}")
    if current_user and current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return templates.TemplateResponse("admin_login.html", {"request": request, "user": current_user})

@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin login attempt: username={username}")
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password_hash) or not user.is_admin:
        logger.warning(f"Admin login failed: username={username}")
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "Неверный логин, пароль или не админ"}
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode(
        {"sub": user.username, "is_admin": user.is_admin, "exp": datetime.utcnow() + access_token_expires},
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    logger.info(f"Admin login successful: username={username}, set cookie: access_token={access_token[:20]}...")
    return response

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    edit_product_id: int = None,
    message: str = None,
    success: bool = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    logger.info(f"Request to /admin/dashboard: username={current_admin.username}, edit_product_id={edit_product_id}")
    products = db.query(Product).all()
    edit_product = db.query(Product).filter(Product.id == edit_product_id).first() if edit_product_id else None
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "products": products,
            "edit_product": edit_product,
            "message": message,
            "success": success
        }
    )

@app.post("/admin/add")
async def add_product(
    name: str = Form(...),
    price: float = Form(...),
    image: UploadFile = File(...),
    category: str = Form(None),
    is_new_arrival: bool = Form(False),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    logger.info(f"Adding product: name={name}, price={price}, category={category}, is_new_arrival={is_new_arrival}")
    try:
        if not image.filename or not allowed_file(image.filename):
            logger.error("Invalid file type or no file uploaded")
            return RedirectResponse(
                url="/admin/dashboard?message=Недопустимый тип файла или файл не загружен&success=false",
                status_code=303
            )

        filename = secure_filename(image.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as f:
            f.write(await image.read())
        
        image_path = f"/static/uploads/{filename}"

        new_product = Product(
            name=name,
            price=price,
            image=image_path,
            category=category,
            is_new_arrival=is_new_arrival
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        logger.info(f"Product added successfully: id={new_product.id}")
        return RedirectResponse(url="/admin/dashboard?message=Товар добавлен&success=true", status_code=303)
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding product: {str(e)}")
        return RedirectResponse(
            url=f"/admin/dashboard?message=Ошибка при добавлении товара: {str(e)}&success=false",
            status_code=303
        )

@app.get("/admin/edit/{product_id}", response_class=HTMLResponse)
async def edit_product_page(
    product_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    logger.info(f"Request to /admin/edit/{product_id}: username={current_admin.username}")
    return RedirectResponse(url=f"/admin/dashboard?edit_product_id={product_id}", status_code=303)

@app.post("/admin/edit/{product_id}")
async def edit_product(
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    image: UploadFile = File(None),
    category: str = Form(None),
    is_new_arrival: bool = Form(False),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    logger.info(f"Editing product {product_id}: name={name}, price={price}, category={category}, is_new_arrival={is_new_arrival}")
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            logger.error(f"Product {product_id} not found")
            return RedirectResponse(url="/admin/dashboard?message=Товар не найден&success=false", status_code=303)

        product.name = name
        product.price = price
        product.category = category
        product.is_new_arrival = is_new_arrival

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            with open(file_path, "wb") as f:
                f.write(await image.read())
            product.image = f"/static/uploads/{filename}"

        db.commit()
        db.refresh(product)
        logger.info(f"Product {product_id} updated successfully")
        return RedirectResponse(url="/admin/dashboard?message=Товар обновлён&success=true", status_code=303)
    except Exception as e:
        db.rollback()
        logger.error(f"Error editing product: {str(e)}")
        return RedirectResponse(
            url=f"/admin/dashboard?message=Ошибка при обновлении товара: {str(e)}&success=false",
            status_code=303
        )

@app.post("/admin/delete/{product_id}")
async def delete_product(
    product_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    logger.info(f"Deleting product {product_id}: username={current_admin.username}")
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            logger.error(f"Product {product_id} not found")
            return RedirectResponse(url="/admin/dashboard?message=Товар не найден&success=false", status_code=303)
        db.delete(product)
        db.commit()
        logger.info(f"Product {product_id} deleted successfully")
        return RedirectResponse(url="/admin/dashboard?message=Товар удалён&success=true", status_code=303)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting product: {str(e)}")
        return RedirectResponse(
            url=f"/admin/dashboard?message=Ошибка при удалении товара: {str(e)}&success=false",
            status_code=303
        )

@app.get("/admin/logout")
async def admin_logout():
    logger.info("Admin logout requested")
    response = RedirectResponse(url="/administrator")
    response.delete_cookie("access_token", path="/")
    return response

@app.get("/api/new-arrivals", response_model=List[ProductBase])
async def get_new_arrivals(db: Session = Depends(get_db)):
    logger.info("Fetching new arrivals")
    try:
        products = db.query(Product).filter(Product.is_new_arrival == True).limit(4).all()
        logger.info(f"New arrivals fetched: {len(products)} products")
        return products
    except Exception as e:
        logger.error(f"Error fetching new arrivals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения новинок: {str(e)}")

# Основные маршруты
@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/blog", response_class=HTMLResponse)
async def blog(request: Request):
    return templates.TemplateResponse("blog.html", {"request": request})

@app.get("/cart", response_class=HTMLResponse)
async def cart(request: Request):
    return templates.TemplateResponse("cart.html", {"request": request})

@app.get("/contactus", response_class=HTMLResponse)
async def contactus(request: Request):
    return templates.TemplateResponse("contactus.html", {"request": request})

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot-password.html", {"request": request})

@app.post("/forgot-password")
async def forgot_password(
    form_data: ForgotPasswordForm,
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.email == form_data.email).first()
        if not user:
            return {"success": False, "message": "If an account with this email exists, a reset link has been sent."}

        db.query(PasswordReset).filter(
            PasswordReset.user_id == user.id,
            PasswordReset.used == False,
            PasswordReset.expires_at < datetime.utcnow()
        ).delete()
        db.commit()

        # Generate JWT token for reset (expires in 1 hour)
        reset_payload = {
            "sub": user.username,  # or user.id if you prefer
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        reset_token = jwt.encode(reset_payload, SECRET_KEY, algorithm=ALGORITHM)

        # Store in DB
        reset_entry = PasswordReset(
            user_id=user.id,
            token=reset_token, 
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used=False
        )
        db.add(reset_entry)
        db.commit()
        logger.info(f"Reset token stored for user {user.id}")

        # Send email
        logger.info(f"Sending reset email to: {form_data.email}")
        
        # Use your ngrok domain or localhost for reset link
        RESET_URL = f"https://fastestore.onrender.com/reset-password?token={reset_token}"
        
        subject = "Password Reset for eStore"
        body = f"""
        Hello, {user.username}!

        You have requested a password reset. Click the link below to set a new password:
        {RESET_URL}

        This link is valid for 1 hour. If you did not request a reset, please ignore this email.

        Best regards,
        eStore Team
      """
        
        send_email(form_data.email, subject, body, ADMIN_EMAIL)
        
        return {"success": True, "message": "Проверьте email для ссылки на сброс пароля!"}
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка аутентификации email")
    except Exception as e:
        db.rollback()
        logger.error(f"Error in forgot_password: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при отправке: попробуйте позже")
    
@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = Query(..., description="Reset token")):
    # Простая проверка токена (опционально, для UX)
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    return templates.TemplateResponse("reset-password.html", {"request": request, "token": token})
    

@app.post("/reset-password")
async def reset_password(
    form_data: ResetPasswordForm,
    token: str = Query(..., description="Reset token from email link"),
    db: Session = Depends(get_db)
):
    try:
        # Валидация токена (JWT decode)
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "password_reset":
                raise HTTPException(status_code=400, detail="Invalid token type")
            username = payload.get("sub")
            if not username:
                raise HTTPException(status_code=400, detail="Invalid token")
        except JWTError:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        # Найти user по username
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Найти reset_entry по token
        reset_entry = db.query(PasswordReset).filter(
            PasswordReset.token == token,
            PasswordReset.user_id == user.id,
            PasswordReset.used == False,
            PasswordReset.expires_at > datetime.utcnow()
        ).first()
        if not reset_entry:
            raise HTTPException(status_code=400, detail="Invalid, expired, or used token")

        # Валидация паролей
        if form_data.password != form_data.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")
        if len(form_data.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        # Обновить пароль
        hashed_password = pwd_context.hash(form_data.password)
        user.password_hash = hashed_password

        # Отметить токен как used
        reset_entry.used = True
        db.commit()
        logger.info(f"Password reset successful for user {user.username}")

        return {"success": True, "message": "Password reset successfully! Redirecting to login..."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in reset_password: {e}")
        raise HTTPException(status_code=500, detail="Error resetting password")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(status_code=204)

@app.get("/{page_name}.html", response_class=HTMLResponse)
async def render_page(request: Request, page_name: str):
    template_file = f"{page_name}.html"
    template_path = os.path.join("templates", template_file)
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Page not found")
    return templates.TemplateResponse(template_file, {"request": request})

# PayPal
@app.post("/api/create-paypal-order", response_model=dict)
async def create_paypal_order(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Получаем корзину
        cart_items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
        if not cart_items:
            raise HTTPException(status_code=400, detail="Корзина пуста")

        total = sum(item.price * item.quantity for item in cart_items)

        # Создаём заказ в БД (pending)
        order = Order(user_id=current_user.id, total=total)
        db.add(order)
        db.commit()
        db.refresh(order)

        # Добавляем items в заказ
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                name=item.name,
                price=item.price,
                image=item.image,
                quantity=item.quantity
            )
            db.add(order_item)
        db.commit()

        # Создаём PayPal order
        access_token = get_paypal_access_token()
        base_url = get_paypal_base_url()
        paypal_url = f"{base_url}/v2/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "PayPal-Request-Id": str(order.id)  # Для идемпотентности
        }
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": "USD",  # Или твоя валюта
                    "value": f"{total:.2f}"
                },
                "description": f"Order #{order.id} from eStore"
            }],
            "application_context": {
                "return_url": f"https://fastestore.onrender.com/api/capture-paypal-order?order_id={order.id}",  # Замени на ngrok или домен
                "cancel_url": f"https://fastestore.onrender.com/cart"  # На корзину при отмене
            }
        }
        logger.info(f"Creating PayPal order at: {paypal_url}")
        response = requests.post(paypal_url, headers=headers, json=body, timeout=10)
        if response.status_code != 201:
            db.delete(order)  # Откатываем заказ
            db.commit()
            logger.error(f"PayPal create order error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail="PayPal error")

        paypal_order = response.json()
        order.paypal_order_id = paypal_order["id"]
        db.commit()

        # Возвращаем approval URL
        approval_url = next(link["href"] for link in paypal_order["links"] if link["rel"] == "approve")
        logger.info(f"PayPal approval URL generated: {approval_url}")
        return {"success": True, "approval_url": approval_url, "order_id": order.id}

    except Exception as e:
        db.rollback()
        logger.error(f"Create PayPal order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/capture-paypal-order")
async def capture_paypal_order(
    order_id: int = Query(...),
    db: Session = Depends(get_db)
):
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order or order.status != "pending":
            raise HTTPException(status_code=400, detail="Invalid order")

        access_token = get_paypal_access_token()
        base_url = get_paypal_base_url()
        paypal_url = f"{base_url}/v2/checkout/orders/{order.paypal_order_id}/capture"
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.info(f"Capturing PayPal order at: {paypal_url}")
        response = requests.post(paypal_url, headers=headers, timeout=10)
        if response.status_code != 201:
            order.status = "failed"
            db.commit()
            logger.error(f"PayPal capture error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail="Payment failed")

        # Успех: обновляем статус, очищаем корзину
        order.status = "paid"
        db.commit()

        # Очищаем корзину пользователя
        db.query(CartItem).filter(CartItem.user_id == order.user_id).delete()
        db.commit()

        # Перенаправляем на success страницу
        logger.info(f"PayPal order {order_id} captured successfully")
        return RedirectResponse(url=f"https://fastestore.onrender.com/order-success?order_id={order_id}", status_code=303)

    except Exception as e:
        logger.error(f"Capture PayPal order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    


@app.get("/order-success", response_class=HTMLResponse)
async def order_success(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order or order.status != "paid":
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse("order-success.html", {"request": request, "order": order})