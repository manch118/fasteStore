from sqlalchemy import Column, Integer, String, create_engine, ForeignKey, Float, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship
from passlib.context import CryptContext
import logging
from dotenv import load_dotenv
import os
from datetime import datetime


# Загружаем переменные окружения
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'users.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    is_admin = Column(Boolean, default=False, nullable=False)
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

class CartItem(Base):
    __tablename__ = "cart"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(String, index=True)
    name = Column(String)
    price = Column(Float)
    image = Column(String)
    quantity = Column(Integer, default=1)
    user = relationship("User", back_populates="cart_items")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    image = Column(String)
    category = Column(String, index=True)  # Для фильтрации по категориям
    is_new_arrival = Column(Boolean, default=False, nullable=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class PasswordReset(Base):
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    user = relationship("User", back_populates="password_resets")



class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Float, nullable=False)
    paypal_order_id = Column(String, unique=True, index=True)  # ID заказа от PayPal
    status = Column(String, default="pending")  # pending, paid, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, index=True)
    name = Column(String)
    price = Column(Float)
    image = Column(String)
    quantity = Column(Integer)
    order = relationship("Order", back_populates="order_items")

# Функция для создания админа, если он не существует
def create_admin_if_not_exists():
    db = SessionLocal()
    try:
        # Проверяем, есть ли админ
        admin_exists = db.query(User).filter(User.is_admin == True).first()
        if admin_exists:
            logger.info("Админ уже существует: username=%s", admin_exists.username)
            return
        
        # Получаем пароль из .env (по умолчанию admin123)
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        if not admin_password:
            logger.error("ADMIN_PASSWORD не задан в .env, используется стандартный пароль")
        
        # Хэшируем пароль
        hashed_password = pwd_context.hash(admin_password)
        
        # Создаём админа
        admin_username = "admin"
        admin_email = "admin@example.com"
        
        new_admin = User(
            username=admin_username,
            email=admin_email,
            password_hash=hashed_password,
            is_admin=True
        )
        db.add(new_admin)
        db.commit()
        logger.info("Админ создан: username=%s, email=%s", admin_username, admin_email)
    except Exception as e:
        logger.error("Ошибка при создании админа: %s", str(e))
        db.rollback()
    finally:
        db.close()

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
    create_admin_if_not_exists()  # Создаём админа после создания таблиц
except Exception as e:
    logger.error(f"Error creating database tables: {str(e)}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()