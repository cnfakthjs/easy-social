from __future__ import annotations

import io
import random
import string

from captcha.image import ImageCaptcha
from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/captcha-image")
def captcha_image():
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    session['captcha_answer'] = chars
    image = ImageCaptcha(width=200, height=60)
    data = image.generate(chars)
    return send_file(io.BytesIO(data.read()), mimetype='image/png')


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        captcha_input = request.form.get("captcha", "").strip().upper()

        error = None
        if not current_app.config.get("TESTING"):
            if not captcha_input:
                error = "請輸入驗證碼。"
            elif captcha_input != session.get('captcha_answer', ''):
                error = "驗證碼錯誤，請重試。"

        if not error:
            if not username or not email or not password:
                error = "Username, email, and password are required."
            elif len(username) > 40:
                error = "Username must be 40 characters or fewer."
            elif User.query.filter_by(username=username).first():
                error = "That username is already taken."
            elif User.query.filter_by(email=email).first():
                error = "That email is already registered."

        session.pop('captcha_answer', None)

        if error:
            flash(error, "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("social.feed"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username_or_email = request.form.get("username_or_email", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.username == username_or_email)
            | (User.email == username_or_email.lower())
        ).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("social.feed"))

        flash("Invalid username/email or password.", "error")

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))