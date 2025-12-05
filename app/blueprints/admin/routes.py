from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ...utils import admin_required, allowed_file
from ...extensions import db
from ...models import Category, Product, Order
from werkzeug.utils import secure_filename
import os

admin_bp = Blueprint("admin", __name__)

@admin_bp.before_request
def _check_admin():
    """
    Гарантирует, что доступ к админским маршрутам имеют только администраторы.

    Вызывается автоматически перед обработкой любого маршрута блюпринта
    'admin'. Использует функцию ''admin_required' для проверки прав.

    Возвращает:
        None: При отсутствии прав выбрасывается исключение 403.
    """
    admin_required()

@admin_bp.route("/")
@login_required
def index():
    """
    Отображает главную страницу админ-панели с краткой статистикой.

    Показывает количество товаров, категорий и заказов в базе данных.

    Возвращает:
        Response: HTML-страница панели администратора.
    """
    stats = {
        "products": Product.query.count(),
        "categories": Category.query.count(),
        "orders": Order.query.count()
    }
    return render_template("admin/index.html", stats=stats)

@admin_bp.route("/categories")
@login_required
def categories():
    """
    Отображает список всех категорий товаров в админ-панели.

    Категории сортируются по названию в алфавитном порядке.

    Возвращает:
        Response: HTML-страница со списком категорий.
    """
    cats = Category.query.order_by(Category.name.asc()).all()
    return render_template("admin/categories.html", categories=cats)

@admin_bp.route("/categories/new", methods=["GET","POST"])
@login_required
def category_new():
    """
    Создаёт новую категорию товаров.

    При GET-запросе отображает форму создания категории.
    При POST-запросе валидирует название и добавляет категорию в базу данных.

    Возвращает:
        Response: HTML-страница формы или редирект на список категорий.
    """
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("Название обязательно!")
            return render_template("admin/category_form.html", category=None)
        if Category.query.filter_by(name=name).first():
            flash("Такая категория уже существует!")
            return render_template("admin/category_form.html", category=None, name=name)
        db.session.add(Category(name=name))
        db.session.commit()
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=None)

@admin_bp.route("/categories/<int:cid>/edit", methods=["GET","POST"])
@login_required
def category_edit(cid: int):
    """
    Редактирует существующую категорию товаров.

    Загружает категорию по идентификатору и при POST-запросе обновляет её
    название в базе данных.

    Аргументы:
        cid: Идентификатор редактируемой категории.

    Возвращает:
        Response: HTML-страница формы или редирект на список категорий.
    """
    cat = Category.query.get_or_404(cid)
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("Название обязательно!")
            return render_template("admin/category_form.html", category=cat)
        cat.name = name
        db.session.commit()
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=cat)

@admin_bp.route("/categories/<int:cid>/delete", methods=["POST"])
@login_required
def category_delete(cid: int):
    """
    Удаляет категорию товаров из базы данных.

    Категория выбирается по идентификатору. При успешном удалении выполняется
    редирект обратно к списку категорий.

    Аргументы:
        cid: Идентификатор категории, которую нужно удалить.

    Возвращает:
        Response: Редирект на страницу со списком категорий.
    """
    cat = Category.query.get_or_404(cid)
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for("admin.categories"))

@admin_bp.route("/products")
@login_required
def products():
    """
    Отображает список товаров в админ-панели.

    Товары сортируются по убыванию идентификатора (новые сверху). В таблице
    показываются основные поля, включая цену и превью изображения.

    Возвращает:
        Response: HTML-страница со списком товаров.
    """
    prods = Product.query.order_by(Product.id.desc()).all()
    return render_template("admin/products.html", products=prods)

@admin_bp.route("/products/new", methods=["GET","POST"])
@login_required
def product_new():
    """
    Создаёт новый товар в каталоге через админ-панель.

    При GET-запросе отображает форму создания товара. При POST-запросе
    считывает данные формы, при необходимости загружает изображение на диск
    и сохраняет запись 'Product' в базе данных.

    Возвращает:
        Response: HTML-страница формы или редирект на список товаров.
    """
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        price = float(request.form.get("price","0") or 0)
        description = request.form.get("description","").strip()
        image_url = request.form.get("image","").strip()
        category_id = request.form.get("category_id", type=int)
        file = request.files.get("file")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join("static/uploads", filename)
            os.makedirs("static/uploads", exist_ok=True)
            file.save(upload_path)
            image_url = f"uploads/{filename}"
        if not name:
            flash("Название обязательно")
            return render_template("admin/product_form.html", categories=categories, product=None)
        prod = Product(
            name=name,
            price=price,
            description=description,
            image=image_url or "",
            category_id=category_id or None
        )
        db.session.add(prod)
        db.session.commit()
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", categories=categories, product=None)

@admin_bp.route("/products/<int:pid>/edit", methods=["GET","POST"])
@login_required
def product_edit(pid: int):
    """
    Редактирует существующий товар в каталоге.

    Загружает товар по идентификатору, обновляет его данные на основе формы
    (включая изображение и категорию) и сохраняет изменения в базе данных.

    Аргументы:
        pid: Идентификатор редактируемого товара.

    Возвращает:
        Response: HTML-страница формы или редирект на список товаров.
    """
    prod = Product.query.get_or_404(pid)
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == "POST":
        prod.name = request.form.get("name","").strip()
        prod.price = float(request.form.get("price","0") or 0)
        prod.description = request.form.get("description","").strip()
        image_url = request.form.get("image","").strip()
        file = request.files.get("file")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join("static/uploads", filename)
            os.makedirs("static/uploads", exist_ok=True)
            file.save(upload_path)
            image_url = f"uploads/{filename}"
        if image_url: prod.image = image_url
        prod.category_id = request.form.get("category_id", type=int) or None
        db.session.commit(); return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", categories=categories, product=prod)

@admin_bp.route("/products/<int:pid>/delete", methods=["POST"])
@login_required
def product_delete(pid: int):
    """
    Удаляет товар из каталога.

    Товар выбирается по идентификатору. После удаления пользователь
    перенаправляется обратно к списку товаров.

    Аргументы:
        pid: Идентификатор товара, который нужно удалить.

    Возвращает:
        Response: Редирект на страницу со списком товаров.
    """
    prod = Product.query.get_or_404(pid)
    db.session.delete(prod)
    db.session.commit()
    return redirect(url_for("admin.products"))

@admin_bp.route("/orders")
@login_required
def orders():
    """
    Отображает список всех заказов в админ-панели.

    Заказы сортируются по дате создания в обратном порядке. В таблице
    показываются клиент, адрес, состав и текущий статус заказа.

    Возвращает:
        Response: HTML-страница со списком заказов.
    """
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)

@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def order_status(order_id: int):
    """
    Обновляет статус выбранного заказа.

    Принимает новый статус из формы и, если он входит в список допустимых
    значений ('new', 'pending', 'awaiting_payment', 'paid', 'canceled'),
    сохраняет изменения в базе данных.

    Аргументы:
        order_id: Идентификатор заказа, статус которого нужно изменить.

    Возвращает:
        Response: Редирект обратно на страницу со списком заказов.
    """
    order = Order.query.get_or_404(order_id)
    new_status = (request.form.get("status") or "").strip()
    if new_status in {"new","pending","awaiting_payment","paid","canceled"}:
        if new_status == "pending":
            order.status = "Обработка платежа"
        elif new_status == "awaiting_payment":
            order.status = "Ожидание платежа"
        elif new_status == "paid":
            order.status = "Оплачено"
        elif new_status == "canceled":
            order.status = "Платёж отменён"

        db.session.commit()
        flash(f"Статус заказа №{order.id} обновлён → {order.status}")
    else:
        flash("Недопустимый статус")
    return redirect(url_for("admin.orders"))
