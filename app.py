import os
import re
import uuid
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PRODUCT_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "products")
BANNER_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "banners")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

db = SQLAlchemy(app)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    parent = db.relationship("Category", remote_side=[id], backref="children")
    products = db.relationship("Product", backref="category", lazy=True)

    @property
    def metal_type(self):
        current = self
        while current.parent:
            current = current.parent
        return current.name


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    weight = db.Column(db.String(80), nullable=False)
    purity = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))
    whatsapp_number = db.Column(db.String(32), nullable=False)
    availability_status = db.Column(db.String(40), nullable=False, default="Available")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    gallery_images = db.relationship(
        "ProductImage", backref="product", lazy=True, cascade="all, delete-orphan"
    )


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    image = db.Column(db.String(255), nullable=False)


class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subtitle = db.Column(db.String(255))
    image = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def slugify(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or f"product-{uuid.uuid4().hex[:8]}"


def unique_slug(title, product_id=None):
    base_slug = slugify(title)
    candidate = base_slug
    counter = 2
    while True:
        query = Product.query.filter_by(slug=candidate)
        if product_id:
            query = query.filter(Product.id != product_id)
        if not query.first():
            return candidate
        candidate = f"{base_slug}-{counter}"
        counter += 1


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage, folder):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        raise ValueError("Only PNG, JPG, JPEG, and WEBP files are allowed.")
    filename = secure_filename(file_storage.filename)
    filename = f"{uuid.uuid4().hex}_{filename}"
    file_storage.save(os.path.join(folder, filename))
    return filename


def whatsapp_link(product):
    message = quote(f"I want this jewellery design: {product.title}")
    number = re.sub(r"\D", "", product.whatsapp_number)
    return f"https://wa.me/{number}?text={message}"


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def top_level_categories():
    return Category.query.filter_by(parent_id=None).order_by(Category.name).all()


def seeded_defaults():
    if Category.query.count() == 0:
        gold = Category(name="Gold")
        silver = Category(name="Silver")
        db.session.add_all([gold, silver])
        db.session.flush()
        db.session.add_all(
            [
                Category(name="Ring", parent=gold),
                Category(name="Necklace", parent=gold),
                Category(name="Chain", parent=gold),
                Category(name="Bracelet", parent=gold),
                Category(name="Ring", parent=silver),
                Category(name="Payel", parent=silver),
                Category(name="Bracelet", parent=silver),
            ]
        )
    db.session.commit()


@app.context_processor
def inject_globals():
    return {
        "site_name": "TaraMaa Castings",
        "nav_categories": top_level_categories(),
        "whatsapp_link": whatsapp_link,
        "current_year": datetime.now().year,
    }


@app.route("/")
def index():
    banners = Banner.query.filter_by(is_active=True).order_by(Banner.created_at.desc()).all()
    featured_products = Product.query.order_by(Product.created_at.desc()).limit(8).all()
    gold = Category.query.filter_by(name="Gold", parent_id=None).first()
    silver = Category.query.filter_by(name="Silver", parent_id=None).first()
    gold_products = (
        Product.query.join(Category)
        .filter(or_(Category.id == gold.id, Category.parent_id == gold.id))
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
        if gold
        else []
    )
    silver_products = (
        Product.query.join(Category)
        .filter(or_(Category.id == silver.id, Category.parent_id == silver.id))
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
        if silver
        else []
    )
    return render_template(
        "index.html",
        banners=banners,
        featured_products=featured_products,
        gold_products=gold_products,
        silver_products=silver_products,
    )


@app.route("/products")
def products():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    metal = request.args.get("metal", "").strip()

    query = Product.query.join(Category)
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if metal:
        root = Category.query.filter_by(name=metal, parent_id=None).first()
        if root:
            query = query.filter(or_(Category.id == root.id, Category.parent_id == root.id))

    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=9, error_out=False
    )
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "products.html",
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        selected_category=category_id,
        selected_metal=metal,
        search=search,
    )


@app.route("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    related_products = (
        Product.query.filter(
            Product.category_id == product.category_id,
            Product.id != product.id,
        )
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )
    return render_template(
        "product_detail.html", product=product, related_products=related_products
    )


@app.route("/category/<int:category_id>")
def category_page(category_id):
    category = Category.query.get_or_404(category_id)
    child_ids = [child.id for child in category.children]
    category_ids = [category.id, *child_ids]
    products = (
        Product.query.filter(Product.category_id.in_(category_ids))
        .order_by(Product.created_at.desc())
        .all()
    )
    return render_template("category.html", category=category, products=products)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password_hash = os.environ.get(
            "ADMIN_PASSWORD_HASH", generate_password_hash("admin123")
        )
        if username == admin_username and check_password_hash(admin_password_hash, password):
            session["admin_logged_in"] = True
            flash("Welcome back.", "success")
            return redirect(url_for("admin"))
        flash("Invalid login details.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        try:
            if form_type == "category":
                parent_id = request.form.get("parent_id", type=int)
                category = Category(name=request.form["name"].strip(), parent_id=parent_id)
                db.session.add(category)
                db.session.commit()
                flash("Category added.", "success")
            elif form_type == "banner":
                filename = save_upload(request.files.get("image"), BANNER_UPLOAD_FOLDER)
                if not filename:
                    raise ValueError("Banner image is required.")
                banner = Banner(
                    title=request.form["title"].strip(),
                    subtitle=request.form.get("subtitle", "").strip(),
                    image=filename,
                    is_active=bool(request.form.get("is_active")),
                )
                db.session.add(banner)
                db.session.commit()
                flash("Banner added.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin"))

    return render_template(
        "admin.html",
        products=Product.query.order_by(Product.created_at.desc()).all(),
        categories=Category.query.order_by(Category.parent_id, Category.name).all(),
        banners=Banner.query.order_by(Banner.created_at.desc()).all(),
    )


@app.route("/admin/product/add", methods=["GET", "POST"])
@login_required
def add_product():
    categories = Category.query.filter(Category.parent_id.isnot(None)).order_by(Category.name).all()
    if request.method == "POST":
        try:
            main_image = save_upload(request.files.get("image"), PRODUCT_UPLOAD_FOLDER)
            if not main_image:
                raise ValueError("Main product image is required.")
            product = Product(
                title=request.form["title"].strip(),
                slug=unique_slug(request.form["title"].strip()),
                category_id=request.form.get("category_id", type=int),
                price=request.form.get("price", type=float),
                weight=request.form["weight"].strip(),
                purity=request.form["purity"].strip(),
                description=request.form["description"].strip(),
                image=main_image,
                whatsapp_number=request.form["whatsapp_number"].strip(),
                availability_status=request.form["availability_status"].strip(),
            )
            db.session.add(product)
            db.session.flush()
            for image_file in request.files.getlist("gallery_images"):
                filename = save_upload(image_file, PRODUCT_UPLOAD_FOLDER)
                if filename:
                    db.session.add(ProductImage(product_id=product.id, image=filename))
            db.session.commit()
            flash("Product added.", "success")
            return redirect(url_for("admin"))
        except (ValueError, KeyError):
            db.session.rollback()
            flash("Please complete all required product fields correctly.", "danger")
    return render_template("add_product.html", categories=categories, product=None)


@app.route("/admin/product/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.filter(Category.parent_id.isnot(None)).order_by(Category.name).all()
    if request.method == "POST":
        try:
            product.title = request.form["title"].strip()
            product.slug = unique_slug(product.title, product.id)
            product.category_id = request.form.get("category_id", type=int)
            product.price = request.form.get("price", type=float)
            product.weight = request.form["weight"].strip()
            product.purity = request.form["purity"].strip()
            product.description = request.form["description"].strip()
            product.whatsapp_number = request.form["whatsapp_number"].strip()
            product.availability_status = request.form["availability_status"].strip()
            new_main = save_upload(request.files.get("image"), PRODUCT_UPLOAD_FOLDER)
            if new_main:
                product.image = new_main
            for image_file in request.files.getlist("gallery_images"):
                filename = save_upload(image_file, PRODUCT_UPLOAD_FOLDER)
                if filename:
                    db.session.add(ProductImage(product_id=product.id, image=filename))
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("admin"))
        except (ValueError, KeyError):
            db.session.rollback()
            flash("Please complete all required product fields correctly.", "danger")
    return render_template("edit_product.html", product=product, categories=categories)


@app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "info")
    return redirect(url_for("admin"))


@app.route("/admin/category/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products or category.children:
        flash("Delete child categories and products first.", "warning")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted.", "info")
    return redirect(url_for("admin"))


@app.route("/admin/banner/<int:banner_id>/delete", methods=["POST"])
@login_required
def delete_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    flash("Banner deleted.", "info")
    return redirect(url_for("admin"))


@app.errorhandler(404)
def page_not_found(_error):
    return render_template("404.html"), 404


with app.app_context():
    os.makedirs(PRODUCT_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(BANNER_UPLOAD_FOLDER, exist_ok=True)
    db.create_all()
    seeded_defaults()


if __name__ == "__main__":
    app.run(debug=True)
