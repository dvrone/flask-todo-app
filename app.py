__version__ = "0.0.1"

import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# from datetime import datetime, timezone


load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key-1-22-333")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Todo(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Task {self.id}>"


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        content = request.form.get("content")
        task = Todo(content=content)
        db.session.add(task)
        db.session.commit()
        flash("Task created successfully!", "success")
        return redirect(url_for("index"))
    tasks = Todo.query.order_by(Todo.created_at.desc()).all()
    return render_template("index.html", tasks=tasks)


@app.route("/delete/<id>")
def delete(id):
    task = Todo.query.get_or_404(id)
    try:
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("There was an issue deleting that task.", "danger")
    return redirect(url_for("index"))


@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    task = Todo.query.get_or_404(id)
    if request.method == "POST":
        task.content = request.form.get("content")
        try:
            db.session.commit()
            flash("Task updated successfully!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            flash("There was an issue updating your task.", "danger")
            return redirect(url_for("index"))
    return render_template("update.html", task=task)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=True)
