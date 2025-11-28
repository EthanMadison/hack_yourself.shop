import click
from .extensions import db
from .models import Category, Product, User

def register_cli(app):
    """
    Регистрирует пользовательские CLI-команды Flask для проекта магазина.

    После вызова этой функции в приложении становятся доступны команды:

    * ``flask --app run seed`` — заполнить базу демоданными (категории и товары);
    * ``flask --app run create-admin`` — создать администратора с указанными
      email и паролем (через аргументы команды или переменные окружения).

    Аргументы:
        app: Экземпляр Flask-приложения, к которому нужно привязать команды.

    Возвращает:
        None: Команды регистрируются побочным эффектом.
    """
    @app.cli.command("seed")
    def seed():
        """
        Создаёт набор демонстрационных категорий и товаров в базе данных.

        Если какие‑то категории или товары уже существуют, повторно они не создаются.
        Команда удобна для быстрого развёртывания проекта в учебных и тестовых целях.
        Запускается как ``flask --app run seed``.

        Возвращает:
            None: Результат выводится в стандартный вывод и сохраняется в базе данных.
        """
        cats = {}
        for name in ["Одежда","Сувениры","Стикеры"]:
            c = Category.query.filter_by(name=name).first()
            if not c:
                c = Category(name=name); db.session.add(c); db.session.flush()
            cats[name] = c
        demo = [
            {
                "name":"Футболка hack_yourself",
                "price":1999.99,
                "description":"Хлопковая футболка c принтом hack_yourself",
                "image":"img/tshirt.png",
                "category":cats["Одежда"]
            },
            {
                "name":"Кружка hack_yourself",
                "price":350.50,"description":"Керамическая кружка c логотипом hack_yourself",
                "image":"img/mug.png",
                "category":cats["Сувениры"]
            },
            {
                "name":"Наклейки hack_yourself",
                "price":114.90,
                "description":"Набор наклеек hack_yourself",
                "image":"img/stickers.png",
                "category":cats["Стикеры"]
            },
        ]
        for d in demo:
            if not Product.query.filter_by(name=d["name"]).first():
                p = Product(name=d["name"],
                            price=d["price"],
                            description=d["description"],
                            image=d["image"],
                            category=d["category"])
                db.session.add(p)
        db.session.commit(); print("Демо товары загружены.")

    @app.cli.command("create-admin")
    @click.option("--email", envvar="ADMIN_EMAIL", required=False)
    @click.option("--password", envvar="ADMIN_PASSWORD", required=False)
    def create_admin(email, password):
        """
        Создаёт или обновляет учётную запись администратора магазина.

        Email и пароль администратора можно передать либо через аргументы команды
        ``--email`` и ``--password``, либо через переменные окружения
        ``ADMIN_EMAIL`` и ``ADMIN_PASSWORD``. Если пользователь с таким email уже
        существует, ему выдается роль администратора и обновляется пароль.

        Аргументы:
            email: Email администратора, полученный из аргументов или окружения.
            password: Новый пароль администратора.

        Возвращает:
            None: Информация об операции выводится в консоль, изменения сохраняются в базе.
        """
        if not email or not password:
            print("Set ADMIN_EMAIL and ADMIN_PASSWORD or pass --email/--password")
            return
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            user = User(email=email.lower(), is_admin=True)
            user.set_password(password)
            db.session.add(user)
        else:
            user.is_admin = True
            user.set_password(password)
        db.session.commit()
        print(f"Администратор подтверждён: {email}")