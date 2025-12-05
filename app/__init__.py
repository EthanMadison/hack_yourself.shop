from flask import Flask
from .extensions import db, login_manager
from .models import User
from .utils import avatar_url_for, order_total

def create_app():
    """
    Создаёт и настраивает экземпляр Flask-приложения.

    Выполняет инициализацию расширений (SQLAlchemy, Flask-Login), регистрирует
    блюпринты публичной части магазина, аутентификации и админ-панели, а также
    создаёт таблицы базы данных при первом запуске.

    Возвращает:
        Flask: Сконфигурированный экземпляр приложения.
    """
    app = Flask(__name__, instance_relative_config=False, template_folder='../templates', static_folder='../static')
    app.config.update(
        SECRET_KEY="dev_secret_key_change_me",
        SQLALCHEMY_DATABASE_URI="sqlite:///shop.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER="static/uploads"
    )

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        """
        Загружает пользователя по идентификатору для Flask-Login.

        Функция регистрируется как 'user_loader' и используется Flask-Login для
        восстановления объекта пользователя из сохранённого в сессии 'user_id'.

        Параметры:
            user_id: Строковый идентификатор пользователя из сессии.

        Возвращает:
            User | None: Объект пользователя, если найден, иначе 'None'.
        """
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_helpers():
        """
        Добавляет вспомогательные функции в контекст шаблонов Jinja2.

        В шаблонах становятся доступны функции 'avatar_url_for' и 'order_total'
        без необходимости явного импорта в каждом шаблоне.

        Возвращает:
            dict: Словарь с функциями, добавляемыми в контекст шаблонов.
        """
        return {"avatar_url_for": avatar_url_for, "order_total": order_total}

    from .blueprints.shop.routes import shop_bp
    from .blueprints.auth.routes import auth_bp
    from .blueprints.admin.routes import admin_bp
    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp, url_prefix="/")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
    return app
