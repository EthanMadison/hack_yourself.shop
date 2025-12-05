import re
from flask import session, abort
from flask_login import current_user

def get_cart() -> dict:
    """
    Возвращает текущее содержимое корзины из сессии пользователя.

    Корзина хранится в объекте 'flask.session' под ключом 'cart'.
    Если корзина ещё не создавалась, возвращается пустой словарь.

    Возвращает:
        dict: Словарь вида '{str(product_id): int(quantity)}' с количеством
        каждого товара в корзине.
    """
    return session.get("cart", {})

def save_cart(cart: dict) -> None:
    """
    Сохраняет переданное состояние корзины в сессию пользователя.

    Используется всеми обработчиками корзины для обновления данных о товарах
    в текущей сессии. После сохранения помечает сессию как изменённую.

    Аргументы:
        cart: Словарь вида '{str(product_id): int(quantity)}', представляющий
            содержимое корзины.

    Возвращает:
        None: Значение не возвращается, данные сохраняются в сессию.
    """
    session["cart"] = cart
    session.modified = True

def cart_items(Product):
    """
    Преобразует содержимое корзины в список объектов товаров и подсчитывает сумму.

    По идентификаторам товаров из корзины выполняет запрос к базе данных,
    рассчитывает количество и итоговую стоимость по каждой позиции.

    Аргументы:
        Product: Модель товара SQLAlchemy, используемая для выборки из БД.

    Возвращает:
        tuple[list[dict], float]: Кортеж из двух элементов:

        * список словарей '{"product": Product, "qty": int, "line_total": float}',
        * общая сумма корзины (float).
    """
    cart = get_cart()
    ids = [int(pid) for pid in cart.keys()]
    products = Product.query.filter(Product.id.in_(ids)).all() if ids else []
    result, total = [], 0.0
    for p in products:
        qty = int(cart.get(str(p.id), 0))
        line_total = p.price * qty
        total += line_total
        result.append({"product": p, "qty": qty, "line_total": line_total})
    return result, total

def admin_required() -> None:
    """
    Проверяет, что текущий пользователь авторизован и является администратором.

    Если пользователь не авторизован или у него отсутствует флаг 'is_admin',
    выбрасывает исключение '403 Forbidden' с помощью 'flask.abort'.
    Используется как вспомогательная функция в админ-панели.

    Возвращает:
        None: При успешной проверке просто продолжает выполнение.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)

def allowed_file(filename: str) -> bool:
    """
    Проверяет, разрешено ли загружать файл с указанным именем.

    Разрешены только изображения с расширениями: 'png', 'jpg', 'jpeg',
    'gif', 'webp'. Расширение определяется по последней точке в имени файла.

    Аргументы:
        filename: Имя файла, как его присылает браузер при загрузке.

    Возвращает:
        bool: 'True', если расширение допустимо, иначе 'False'.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png","jpg","jpeg","gif","webp"}

def password_is_strong(password: str) -> bool:
    """
    Проверяет, удовлетворяет ли пароль требованиям сложности проекта.

    Текущие требования:
    * не менее 6 символов;
    * хотя бы одна заглавная буква (A–Z);
    * хотя бы одна цифра (0–9);
    * хотя бы один специальный символ (не буква и не цифра).

    Аргументы:
        password: Проверяемый пароль в виде строки.

    Возвращает:
        bool: 'True', если пароль достаточно сложный, иначе 'False'.
    """
    return (
        isinstance(password, str)
        and len(password) >= 6
        and re.search(r"[A-Z]", password) is not None
        and re.search(r"\d", password) is not None
        and re.search(r"[^A-Za-z0-9]", password) is not None
    )

def avatar_url_for(user) -> str:
    """
    Возвращает относительный путь к аватару пользователя.

    Если у пользователя указан путь к своему аватару, используется он.
    В противном случае возвращается путь к аватару по умолчанию
    'img/default_avatar.png' из папки 'static'.

    Аргументы:
        user: Экземпляр модели пользователя или объект с атрибутом 'avatar'.

    Возвращает:
        str: Относительный путь к изображению аватара для подстановки в 'url_for("static", ...)'.
    """
    try:
        path = (user.avatar or "").strip()
    except Exception:
        path = ""
    return path if path else "img/default_avatar.png"

def order_total(order) -> float:
    """
    Вычисляет общую сумму заказа по всем его позициям.

    Для каждой позиции берётся сохранённая на момент покупки цена ``price_snapshot``
    и умножается на количество 'quantity'. Сумма по всем позициям округляется
    до двух знаков после запятой.

    Аргументы:
        order: Экземпляр модели 'Order' с загруженными связанными объектами 'OrderItem'.

    Возвращает:
        float: Итоговая стоимость заказа.
    """
    return round(sum((it.price_snapshot or 0) * (it.quantity or 0) for it in order.items), 2)
