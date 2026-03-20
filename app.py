__version__ = "0.3.0"

import os
from urllib.parse import urlsplit

from dotenv import load_dotenv
# from email_validator import EmailNotValidError, validate_email
from flask import (Flask, abort, flash, redirect, render_template, request,
                   url_for)
from flask_babel import Babel, _
from flask_babel import lazy_gettext as _l
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect, FlaskForm
from password_validator import PasswordValidator
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import (BooleanField, EmailField, PasswordField, StringField,
                     SubmitField)
from wtforms.validators import DataRequired, Email, Length, ValidationError

# from datetime import datetime, timezone

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key-1-22-333")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["BABEL_DEFAULT_LOCALE"] = "ru"
app.config["BABEL_SUPPORTED_LOCALES"] = ["en", "uz", "ru"]

db = SQLAlchemy(app)
babel = Babel(app)
login_manager = LoginManager(app)
csrf = CSRFProtect(app)

login_manager.login_message = _l("Please log in to view this page.")
login_manager.login_view = "login"
login_manager.login_message_category = "info"

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


# FORMS


class RegisterForm(FlaskForm):
    email = EmailField(
        _l("Email"), validators=[Email(), DataRequired(), Length(max=120)]
    )
    password = PasswordField(_l("Password"), validators=[DataRequired(), Length(min=8)])
    submit = SubmitField(_l("Sign Up"))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError(
                _l("That email is already taken. Please choose a different one.")
            )


class LoginForm(FlaskForm):
    email = EmailField(_l("Email"), validators=[DataRequired(), Length(max=120)])
    password = PasswordField(_l("Password"), validators=[DataRequired(), Length(min=8)])
    remember = BooleanField(_l("Remember me"))
    submit = SubmitField(_l("Login"))


class TaskForm(FlaskForm):
    content = StringField(_l("Content"), validators=[DataRequired(), Length(max=200)])
    submit = SubmitField(_l("Add"))


class ToggleTaskForm(FlaskForm):
    submit = SubmitField(_l("Toggle"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    form = TaskForm()
    if form.validate_on_submit():
        task = Todo(content=form.content.data, author=current_user)
        db.session.add(task)
        db.session.commit()
        flash(_("Task created successfully!"), "success")
        return redirect(url_for("index"))
    tasks = (
        Todo.query.filter_by(user_id=current_user.id)
        .order_by(Todo.created_at.desc())
        .all()
    )
    return render_template("index.html", tasks=tasks, form=form)


@app.route("/delete/<id>")
@login_required
def delete(id):
    task = Todo.query.get_or_404(id)
    if task.author != current_user:
        flash(_("You do not have permission to delete this task."), "danger")
        return redirect(url_for("index"))
    try:
        db.session.delete(task)
        db.session.commit()
        flash(_("Task deleted successfully!"), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("There was an issue deleting that task."), "danger")
    return redirect(url_for("index"))


@app.route("/update/<int:id>", methods=["GET", "POST"])
@login_required
def update(id):
    task = Todo.query.get_or_404(id)
    if task.author != current_user:
        flash(_("You don't have permission to edit this."), "danger")
        return redirect(url_for("index"))
    form = TaskForm()
    form.submit.label.text = _("Update")
    if form.validate_on_submit():
        try:
            task.content = form.content.data
            db.session.commit()
            flash(_("Task updated successfully!"), "success")
            return redirect(url_for("index"))
        except Exception:
            db.session.rollback()
            flash(_("There was an issue updating your task."), "danger")
            return redirect(url_for("index"))
    elif request.method == "GET":
        form.content.data = task.content
    return render_template("update.html", task=task, form=form)


@app.route("/toggle/<int:id>", methods=["GET", "POST"])
def toggle_task(id):
    task = db.get_or_404(Todo, id)
    if task.author != current_user:
        abort(403)
    form = ToggleTaskForm()
    if form.validate_on_submit():
        task.completed = not task.completed
        db.session.commit()
        status = _("completed") if task.completed else _("pending")
        # TODO: fix here
        flash(_(f"Task marked as {status}"), "info")
    return redirect(url_for("index"))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


# AUTH ROUTES


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data, method="scrypt")
        user = User(email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash(_("Your account has been created! You are now able to log in"), "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            if not next_page or urlsplit(next_page).netloc != "":
                next_page = url_for("index")
            flash(_("Welcome back!"), "success")
            return redirect(next_page)
        else:
            flash(_("Login Unsuccessful. Please check email and password."), "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash(_("You are logged out!"), "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
