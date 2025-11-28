from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ...extensions import db
from ...models import User, Order
from ...utils import password_is_strong, allowed_file

auth_bp = Blueprint("auth", __name__)

def _ts(app):
    """
    Создаёт сериализатор токенов на основе секретного ключа приложения.

    Используется для генерации и проверки токенов подтверждения email и
    восстановления пароля через библиотеку ``itsdangerous``.

    Аргументы:
        app: Экземпляр Flask-приложения с установленным ``secret_key``.

    Возвращает:
        URLSafeTimedSerializer: Сериализатор с заданной «солью».
    """
    return URLSafeTimedSerializer(app.secret_key, salt="email-confirm-salt")

@auth_bp.route("/register", methods=["GET","POST"])
def register():
    """
    Обрабатывает регистрацию нового пользователя.

    При GET-запросе отображает форму регистрации. При POST-запросе:
    * проверяет заполненность полей;
    * валидирует сложность пароля;
    * проверяет уникальность email;
    * создаёт пользователя и предлагает ссылку для подтверждения email.

    Возвращает:
        Response: HTML-страница с формой регистрации или редирект на страницу входа.
    """
    from flask import current_app as app

    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not email or not password:
            flash("Укажите email и пароль")
            return render_template("register.html", email=email)
        if not password_is_strong(password):
            flash("Пароль слишком простой: минимум 6 символов, 1 заглавная бука, 1 цифра и 1 спецсимвол")
            return render_template("register.html", email=email)
        if User.query.filter_by(email=email).first():
            flash("Такой пользователь уже существует")
            return render_template("register.html", email=email)
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        token = _ts(app).dumps(email)
        flash(f"Регистрация прошла успешно. Подтвердите email: { url_for('auth.confirm_email',
                                                                         token=token,
                                                                         _external=True) }")
        return redirect(url_for("auth.login"))
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    """
    Выполняет аутентификацию пользователя по email и паролю.

    При успешной проверке пароля логинит пользователя через Flask-Login и
    перенаправляет либо на страницу из параметра ``next``, либо в каталог.

    Возвращает:
        Response: HTML-страница входа или редирект после успешной аутентификации.
    """
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(request.args.get("next") or url_for("shop.index"))
        flash("Неверный email или пароль")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    """
    Выполняет выход пользователя из системы.

    Очищает сессию Flask-Login и возвращает пользователя на главную страницу
    магазина, отображая сообщение об успешном выходе.

    Возвращает:
        Response: Редирект на главную страницу каталога.
    """
    logout_user()
    flash("Вы вышли из системы")
    return redirect(url_for("shop.index"))

@auth_bp.route("/confirm/send")
@login_required
def send_confirm_email():
    """
    Формирует ссылку для подтверждения email текущего пользователя.

    В учебной конфигурации ссылка не отправляется по почте, а показывается во
    flash-сообщении. Если email уже подтверждён, просто сообщает об этом.

    Возвращает:
        Response: Редирект на страницу профиля пользователя.
    """
    from flask import current_app as app

    if current_user.email_confirmed:
        flash("Email уже подтверждён")
        return redirect(url_for("auth.profile"))
    token = _ts(app).dumps(current_user.email)
    link = url_for("auth.confirm_email", token=token, _external=True)
    flash(f"Ссылка для подтверждения email: {link}")
    return redirect(url_for("auth.profile"))

@auth_bp.route("/confirm/<token>")
@login_required
def confirm_email(token):
    """
    Подтверждает email пользователя по токену.

    Валидирует токен с ограничением по времени, сравнивает email из токена
    с email текущего пользователя и при успехе помечает email как подтверждённый.

    Аргументы:
        token: Строковый токен подтверждения, полученный по ссылке.

    Возвращает:
        Response: Редирект на страницу профиля или код 403 при несоответствии email.
    """
    from flask import current_app as app

    try:
        email = _ts(app).loads(token, max_age=60*60*24)
    except SignatureExpired:
        flash("Ссылка устарела.")
        return redirect(url_for("auth.profile"))
    except BadSignature:
        flash("Некорректная ссылка.")
        return redirect(url_for("auth.profile"))
    if email.lower() != current_user.email.lower():
        return "", 403
    current_user.email_confirmed = True
    db.session.commit()
    flash("Email подтверждён!")
    return redirect(url_for("auth.profile"))

@auth_bp.route("/password/forgot", methods=["GET","POST"])
def password_forgot():
    """
    Обрабатывает запрос на восстановление пароля.

    При GET-запросе показывает форму ввода email. При POST-запросе, если
    пользователь с таким email существует, генерирует токен сброса пароля и
    показывает ссылку для сброса во flash-сообщении (в учебных целях).

    Возвращает:
        Response: HTML-страница формы или редирект на страницу входа.
    """
    from flask import current_app as app

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = _ts(app).dumps(email)
            reset_link = url_for("auth.password_reset", token=token, _external=True)
            flash(f"Если такой пользователь существует, ссылка для сброса: {reset_link} (действует 30 минут)")
        else:
            flash("Если такой пользователь существует, ссылка для сброса отправлена на email.")
        return redirect(url_for("auth.login"))
    return render_template("password_forgot.html")

@auth_bp.route("/password/reset/<token>", methods=["GET","POST"])
def password_reset(token):
    """
    Позволяет задать новый пароль по токену восстановления.

    Проверяет валидность и срок действия токена, находит пользователя по email,
    сравнивает два введённых пароля и валидирует их сложность. При успехе
    сохраняет новый пароль и перенаправляет на страницу входа.

    Аргументы:
        token: Строковый токен восстановления пароля.

    Возвращает:
        Response: HTML-страница формы смены пароля или редирект при ошибках/успехе.
    """
    from flask import current_app as app

    try:
        email = _ts(app).loads(token, max_age=60*30)
    except SignatureExpired:
        flash("Ссылка устарела.")
        return redirect(url_for("auth.password_forgot"))
    except BadSignature:
        flash("Некорректная ссылка.")
        return redirect(url_for("auth.password_forgot"))
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        flash("Пользователь не найден.")
        return redirect(url_for("auth.password_forgot"))
    if request.method == "POST":
        pwd = request.form.get("password") or ""
        pwd2 = request.form.get("password2") or ""
        if pwd != pwd2:
            flash("Пароли не совпадают.")
            return redirect(request.url)

        from ...utils import password_is_strong

        if not password_is_strong(pwd):
            flash("Пароль слишком простой.")
            return redirect(request.url)
        user.set_password(pwd)
        db.session.commit()
        flash("Пароль изменён.")
        return redirect(url_for("auth.login"))
    return render_template("password_reset.html")

@auth_bp.route("/account")
@login_required
def account():
    """
    Отображает личный кабинет пользователя с историей заказов.

    Показывает заказы, связанные с текущим пользователем по ``user_id``.
    Если таких заказов нет (например, были сделаны как гость по email),
    пытается подгрузить заказы по полю ``email``.

    Возвращает:
        Response: HTML-страница со списком заказов пользователя.
    """
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    if not orders:
        orders = Order.query.filter_by(email=current_user.email).order_by(Order.created_at.desc()).all()
    return render_template("account.html", orders=orders)

@auth_bp.route("/account/order/<int:order_id>")
@login_required
def account_order(order_id: int):
    """
    Показывает подробную информацию о конкретном заказе пользователя.

    Доступ к заказу разрешён только его владельцу (по ``user_id`` или ``email``)
    и администраторам сайта. В противном случае возвращается ответ с кодом 403.

    Аргументы:
        order_id: Идентификатор заказа в базе данных.

    Возвращает:
        Response: HTML-страница с деталями заказа или ошибка доступа.
    """
    order = Order.query.get_or_404(order_id)
    allowed = (order.user_id == current_user.id) if order.user_id is not None else (order.email == current_user.email)
    if not (allowed or current_user.is_admin):
        return "", 403
    return render_template("account_order.html", order=order)

@auth_bp.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    """
    Отображает и обновляет профиль текущего пользователя.

    Поддерживаются два режима работы, выбираемые полем ``action`` в форме:

    * ``save_profile`` — обновление имени, адреса по умолчанию и загрузка аватара;
    * ``change_password`` — смена пароля с проверкой текущего пароля и сложности нового.

    Возвращает:
        Response: HTML-страница профиля или редирект после успешного обновления.
    """
    user = current_user
    if request.method == "POST":
        action = request.form.get("action","save_profile")
        if action == "save_profile":
            user.full_name = (request.form.get("full_name") or "").strip()
            user.default_address = (request.form.get("default_address") or "").strip()
            from werkzeug.utils import secure_filename
            file = request.files.get("avatar")
            if file and file.filename and allowed_file(file.filename):
                import os
                filename = secure_filename(file.filename)
                folder = "static/uploads/avatars"
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, filename)
                file.save(path)
                user.avatar = f"uploads/avatars/{filename}"
            from ...extensions import db
            db.session.commit()
            flash("Профиль обновлён")
        elif action == "change_password":
            cur = request.form.get("current_password") or ""
            pwd = request.form.get("new_password") or ""
            pwd2 = request.form.get("new_password2") or ""
            if not user.check_password(cur):
                flash("Текущий пароль неверен")
                return redirect(url_for("auth.profile"))
            from ...utils import password_is_strong
            if not password_is_strong(pwd):
                flash("Пароль слишком простой")
                return redirect(url_for("auth.profile"))
            if pwd != pwd2:
                flash("Пароли не совпадают")
                return redirect(url_for("auth.profile"))
            user.set_password(pwd)
            from ...extensions import db
            db.session.commit()
            flash("Пароль изменён")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html", user=user)
