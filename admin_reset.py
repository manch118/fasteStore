from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import User, pwd_context
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def update_admin_password():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin == True).first()
        if not admin:
            print("Админ не найден")
            return
        
        new_password = os.getenv("ADMIN_PASSWORD", "admin123")
        admin.password_hash = pwd_context.hash(new_password)
        db.commit()
        print(f"Пароль админа обновлён: username={admin.username}, новый пароль из ADMIN_PASSWORD")
    except Exception as e:
        print(f"Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_admin_password()