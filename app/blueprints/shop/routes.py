from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy import func
from ...extensions import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_CURRENCY, db
import stripe
from ...models import Product, Order, OrderItem
from ...utils import cart_items, get_cart, save_cart, order_total

shop_bp = Blueprint("shop", __name__)

@shop_bp.route("/")
def index():
    """
    Отображает главную страницу каталога товаров.

    Поддерживает простой поиск по названию и описанию товара через параметр
    строки запроса ``q``. Результаты сортируются по убыванию идентификатора,
    то есть новые товары будут показаны первыми.

    Возвращает:
        str: HTML-страница каталога с перечнем товаров.
    """
    q = request.args.get("q","").strip()
    query = Product.query
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))
    products = query.order_by(Product.id.desc()).all()
    return render_template("index.html", products=products, q=q)

@shop_bp.route("/product/<int:pid>")
def product_detail(pid: int):
    """
    Показывает детальную страницу конкретного товара.

    Параметры:
        pid: Идентификатор товара в базе данных.

    Возвращает:
        str: HTML-страница карточки товара или ошибка 404, если товар не найден.
    """
    product = Product.query.get_or_404(pid)
    return render_template("product.html", product=product)

@shop_bp.route("/cart")
def cart_view():
    """
    Отображает содержимое корзины текущего пользователя.

    Использует данные из сессии, преобразованные функцией ``cart_items``, и
    выводит таблицу с товарами, их количеством и итоговой стоимостью.

    Возвращает:
        str: HTML-страница с корзиной и общей суммой заказа.
    """
    items, total = cart_items(Product)
    return render_template("cart.html", items=items, total=total)

@shop_bp.route("/cart/add/<int:pid>", methods=["POST"])
def cart_add(pid: int):
    """
    Добавляет выбранный товар в корзину.

    Корзина хранится в сессии. Количество увеличивается на переданное значение
    или на 1 по умолчанию. При AJAX-запросе возвращает JSON с обновлённым
    количеством, при обычном запросе выполняет редирект обратно на страницу.

    Параметры:
        pid: Идентификатор добавляемого товара.

    Возвращает:
        Response: JSON-ответ для AJAX-запроса или редирект для обычного запроса.
    """
    Product.query.get_or_404(pid)
    qty = int(request.form.get("qty", 1))
    cart = get_cart()
    cart[str(pid)] = cart.get(str(pid), 0) + max(1, qty)
    save_cart(cart)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "pid": pid, "qty": cart[str(pid)], "cart_size": len(cart)})
    flash("Товар добавлен в корзину")
    return redirect(request.referrer or url_for("shop.index"))

@shop_bp.route("/cart/api/update", methods=["POST"])
def cart_update_api():
    """
    Обновляет содержимое корзины через AJAX API.

    Принимает JSON с массивом товаров и их количествами, пересчитывает корзину,
    обновляет сессию и возвращает новые суммы по строкам и общий итог.

    Ожидаемый формат тела запроса::

        {
            "items": [
                {"pid": "1", "qty": 2},
                {"pid": "5", "qty": 0}
            ]
        }

    Возвращает:
        Response: JSON с полями ``ok``, ``total``, ``lines`` и ``cart_size``.
    """
    data = request.get_json(silent=True) or {}
    incoming = data.get("items", [])
    cart = get_cart()
    for it in incoming:
        try:
            pid = str(int(it.get("pid"))); qty = max(0, int(it.get("qty", 0)))
        except (TypeError, ValueError):
            continue
        if qty > 0:
            cart[pid] = qty
        else:
            cart.pop(pid, None)
    save_cart(cart)
    items, total = cart_items(Product)
    lines = {str(row["product"].id): round(row["line_total"], 2) for row in items}
    return jsonify({"ok": True, "total": round(total, 2), "lines": lines, "cart_size": len(cart)})

@shop_bp.route("/cart/update", methods=["POST"])
def cart_update():
    """
    Обновляет корзину при отправке HTML-формы.

    Читает значения полей вида ``qty_<product_id>`` из формы, пересобирает
    словарь корзины и сохраняет его в сессию. Используется как резервный
    вариант рядом с AJAX-обновлением.

    Возвращает:
        Response: Редирект обратно на страницу корзины.
    """
    cart = {}
    for key, value in request.form.items():
        if key.startswith("qty_"):
            pid = key.split("_", 1)[1]
            try:
                qty = max(0, int(value))
            except ValueError:
                qty = 0
            if qty > 0:
                cart[pid] = qty
    save_cart(cart)
    flash("Корзина обновлена")
    return redirect(url_for("shop.cart_view"))

@shop_bp.route("/cart/clear", methods=["POST"])
def cart_clear():
    """Очистить корзину и вернуться на страницу корзины."""
    from ...utils import save_cart
    from flask import flash, redirect, url_for
    save_cart({})
    flash("Корзина очищена")
    return redirect(url_for("shop.cart_view"))

@shop_bp.route("/checkout", methods=["GET","POST"])
def checkout():
    """
    Оформляет новый заказ и при необходимости создаёт платёжную сессию Stripe.

    GET-запрос:
        Показывает страницу оформления заказа с текущим содержимым корзины.

    POST-запрос:
        * валидирует введённые имя, email и адрес;
        * создаёт запись ``Order`` и связанные ``OrderItem`` в базе данных;
        * назначает пользователю локальный номер заказа ``user_order_no``;
        * при наличии ключей Stripe пытается создать Checkout Session и
          перенаправляет пользователя на страницу оплаты;
        * при ошибке Stripe или отсутствии ключей выставляет статус
          ``awaiting_payment`` и показывает страницу благодарности.

    Возвращает:
        Response: HTML-страница оформления заказа, страница благодарности или
        редирект на Stripe Checkout.
    """
    items, total = cart_items(Product)
    if request.method == "GET":
        return render_template("checkout.html",
                               items=items,
                               total=total,
                               stripe_pk=STRIPE_PUBLISHABLE_KEY)

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    address = (request.form.get("address") or "").strip() or (
        current_user.default_address if current_user.is_authenticated else ""
    )
    if not (name and email and address):
        flash("Пожалуйста, заполните все поля")
        return render_template("checkout.html",
                               items=items,
                               total=total,
                               name=name,
                               email=email,
                               address=address,
                               stripe_pk=STRIPE_PUBLISHABLE_KEY)
    if total <= 0:
        flash("Корзина пуста")
        return redirect(url_for("shop.index"))

    order = Order(customer_name=name, email=email, address=address, status="Обработка платежа",
                  user_id=(current_user.id if current_user.is_authenticated else None))
    if order.user_id is not None:
        last_no = db.session.query(func.max(Order.user_order_no)).filter(Order.user_id == order.user_id).scalar() or 0
        order.user_order_no = last_no + 1
    else:
        last_no = db.session.query(func.max(Order.user_order_no)).filter(Order.user_id.is_(None),
                                                                         Order.email == order.email).scalar() or 0
        order.user_order_no = last_no + 1
    db.session.add(order)
    for row in items:
        db.session.add(OrderItem(order=order,
                                 product_id=row["product"].id,
                                 quantity=row["qty"],
                                 price_snapshot=row["product"].price))
    db.session.commit()

    if STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY:
        try:
            line_items = [{
                "price_data": {
                    "currency": STRIPE_CURRENCY,
                    "product_data": {"name": row["product"].name},
                    "unit_amount": int(round(row["product"].price * 100)),
                },
                "quantity": int(row["qty"]),
            } for row in items]
            session_obj = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=line_items,
                success_url=url_for("shop.payment_success", order_id=order.id, _external=True),
                cancel_url=url_for("shop.payment_cancel", order_id=order.id, _external=True),
                customer_email=email,
                metadata={"order_id": str(order.id)}
            )
            order.stripe_session_id = session_obj.id
            db.session.commit()
            save_cart({})
            return redirect(session_obj.url, code=303)
        except Exception as e:
            print("Stripe error:", e)
            flash("Не удалось создать платёжную сессию. Заказ без онлайн-оплаты.")

    order.status = "Ожидание оплаты"
    db.session.commit()
    save_cart({})
    return render_template("thankyou.html", order=order, total=order_total(order))

@shop_bp.route("/payment/success")
def payment_success():
    """
    Обрабатывает успешную оплату заказа на стороне сайта.

    По параметру ``order_id`` в строке запроса находит заказ, помечает его
    статусом ``paid`` и показывает страницу благодарности с итоговой суммой.

    Возвращает:
        Response: HTML-страница «Спасибо за заказ».
    """
    order_id = request.args.get("order_id", type=int)
    order = Order.query.get_or_404(order_id)
    order.status = "Оплачено"
    db.session.commit()
    return render_template("thankyou.html", order=order, total=order_total(order))

@shop_bp.route("/payment/cancel")
def payment_cancel():
    """
    Обрабатывает отмену оплаты на стороне Stripe.

    Помечает заказ статусом ``canceled`` и перенаправляет пользователя обратно
    на страницу оформления заказа, где он может выбрать другой способ оплаты
    или изменить корзину.

    Возвращает:
        Response: Редирект на страницу оформления заказа.
    """
    order_id = request.args.get("order_id", type=int)
    order = Order.query.get_or_404(order_id)
    order.status = "Платёж отменён"
    db.session.commit()
    return redirect(url_for("shop.checkout"))
