from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    full_name = db.Column(db.String(120), default="")
    default_address = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(255), default="")
    email_confirmed = db.Column(db.Boolean, default=False)

    orders = db.relationship("Order", backref="user", lazy=True)

    def __init__(
        self,
        email: str,
        password_hash: str = "",
        full_name: str = "",
        default_address: str = "",
        is_admin: bool = False,
        avatar: str | None = None,
        email_confirmed: bool = False,
    ):
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.default_address = default_address
        self.is_admin = is_admin
        self.avatar = avatar
        self.email_confirmed = email_confirmed

    def set_password(self, password: str) -> None:
        """
        Устанавливает новый пароль пользователя, сохраняя только его хэш.

        Хэш пароля вычисляется с помощью ``werkzeug.security.generate_password_hash``
        и записывается в поле ``password_hash``. Сам пароль в базе данных не хранится.

        Аргументы:
            password: Пароль в открытом виде, введённый пользователем.

        Возвращает:
            None: Значение не возвращается, хэш пароля сохраняется в объекте пользователя.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Проверяет корректность введённого пользователем пароля.

        Сравнивает переданную строку с хэшем в поле ``password_hash`` с помощью
        ``werkzeug.security.check_password_hash``.

        Аргументы:
            password: Пароль в открытом виде, который нужно проверить.

        Возвращает:
            bool: ``True``, если пароль верный, иначе ``False``.
        """
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    products = db.relationship("Product", backref="category", lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(255), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="new")
    user_order_no = db.Column(db.Integer, nullable=True)
    stripe_session_id = db.Column(db.String(255), default=None)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_snapshot = db.Column(db.Float, nullable=False, default=0.0)
    product = db.relationship("Product")