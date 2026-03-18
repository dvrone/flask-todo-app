__version__ = "0.2.0"

import os

from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_babel import Babel, _
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from password_validator import PasswordValidator
from sqlalchemy import func
from werkzeug.security import generate_password_hash

# from datetime import datetime, timezone

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key-1-22-333")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["BABEL_DEFAULT_LOCALE"] = "uz"
app.config["BABEL_SUPPORTED_LOCALES"] = ["en", "uz"]

db = SQLAlchemy(app)
babel = Babel(app)
login_manager = LoginManager(app)

schema = PasswordValidator()
schema.min(8).max(100).has().uppercase().has().digits().has().no().spaces()


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    date_joined = db.Column(db.DateTime(timezone=True), server_default=func.now())

    tasks = db.relationship(
        "Todo", backref="author", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.id}>"


@login_manager.user_loader
def load_user(user_id: int):
    return User.query.get_or_404(user_id)


class Todo(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def __repr__(self):
        return f"<Task {self.id}>"


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        content = request.form.get("content")
        task = Todo(content=content)
        db.session.add(task)
        db.session.commit()
        flash(_("Task created successfully!"), "success")
        return redirect(url_for("index"))
    tasks = Todo.query.order_by(Todo.created_at.desc()).all()
    return render_template("index.html", tasks=tasks)


@app.route("/delete/<id>")
def delete(id):
    task = Todo.query.get_or_404(id)
    try:
        db.session.delete(task)
        db.session.commit()
        flash(_("Task deleted successfully!"), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("There was an issue deleting that task."), "danger")
    return redirect(url_for("index"))


@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    task = Todo.query.get_or_404(id)
    if request.method == "POST":
        task.content = request.form.get("content")
        try:
            db.session.commit()
            flash(_("Task updated successfully!"), "success")
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            flash(_("There was an issue updating your task."), "danger")
            return redirect(url_for("index"))
    return render_template("update.html", task=task)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


# AUTH ROUTES


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            valid = validate_email(email)
            email = valid.email

            if not schema.validate(password):
                flash(
                    _("Password must be 8+ chars with a digit and uppercase."), "danger"
                )
                return redirect(url_for("register"))

            if User.query.filter_by(email=email).first():
                flash(_("Email already registered."), "warning")
                return redirect(url_for("register"))

            hashed_pw = generate_password_hash(password, method="scrypt")
            user = User(email=email, password=hashed_pw)

            db.session.add(user)
            db.session.commit()

            flash(_("Success! Please log in."), "success")
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()  # Important: undo the 'add' if commit fails
            flash(_("A database error occurred. Please try again."), "danger")
    return render_template("register.html")


if __name__ == "__main__":
    app.run(debug=True)
