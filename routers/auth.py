import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from main import limiter
from models import User
from template_helpers import configure_templates
from utils.csrf import generate_csrf_token, validate_csrf_token


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory=BASE_DIR / "templates"))
templates.env.globals["generate_csrf_token"] = generate_csrf_token

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "solo-secret-key-change-in-prod")
ENV = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
COOKIE_SECURE = os.getenv("ENV") == "production"

if ENV == "production" and SECRET_KEY in {"", "solo-secret-key-change-in-prod", "solo-super-secret-key-change-this"}:
    raise RuntimeError("Set a strong SECRET_KEY before running Solo in production.")

serializer = URLSafeTimedSerializer(SECRET_KEY)
reset_serializer = URLSafeTimedSerializer(SECRET_KEY)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_session_token(user_id: int) -> str:
    return serializer.dumps(user_id, salt="session")


def get_user_id_from_token(token: str) -> int | None:
    try:
        return serializer.loads(token, salt="session", max_age=604800)
    except Exception:
        return None


def _set_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=604800,
        path="/",
    )


def _valid_email(email: str) -> bool:
    if len(email) > 255 or "@" not in email:
        return False
    _, _, domain = email.partition("@")
    return "." in domain and bool(domain.strip("."))


def _password_has_number_or_special(password: str) -> bool:
    return bool(re.search(r"[\d\W_]", password))


def _render(template_name: str, request: Request, **context):
    return templates.TemplateResponse(
        request,
        template_name,
        {"error": None, "success": None, **context},
    )


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if not token:
        return None

    user_id = get_user_id_from_token(token)
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def require_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse(url="/dashboard", status_code=302)

    success = request.cookies.get("auth_success")
    response = _render("login.html", request, success=success)
    if success:
        response.delete_cookie("auth_success", path="/")
    return response


@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(csrf_token):
        return _render("login.html", request, error="Invalid request. Please try again.")

    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return _render("login.html", request, error="Invalid email or password")

    token = create_session_token(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    _set_session_cookie(response, token)
    return response


@router.get("/signup")
def signup_page(request: Request):
    return _render("signup.html", request)


@router.post("/signup")
@limiter.limit("5/minute")
def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(csrf_token):
        return _render("signup.html", request, error="Invalid request. Please try again.")

    clean_name = name.strip()
    clean_email = email.strip().lower()

    if len(clean_name) < 2:
        return _render("signup.html", request, error="Name must be at least 2 characters.")
    if len(clean_name) > 100:
        return _render("signup.html", request, error="Name must be 100 characters or less.")
    if not _valid_email(clean_email):
        return _render("signup.html", request, error="Enter a valid email address.")
    if len(password) < 8:
        return _render("signup.html", request, error="Password must be at least 8 characters.")
    if len(password) > 128:
        return _render("signup.html", request, error="Password must be 128 characters or less.")
    if not _password_has_number_or_special(password):
        return _render("signup.html", request, error="Password must contain at least one number or special character.")
    if password != confirm_password:
        return _render("signup.html", request, error="Passwords do not match.")

    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        return _render("signup.html", request, error="An account with this email already exists.")

    user = User(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    _set_session_cookie(response, token)
    return response


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return _render("forgot_password.html", request)


@router.post("/forgot-password")
def forgot_password(
    request: Request,
    email: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(csrf_token):
        return _render("forgot_password.html", request, error="Invalid request. Please try again.")

    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if user:
        token = reset_serializer.dumps(clean_email, salt="password-reset")
        print(f"Password reset link: /reset-password?token={token}")
        # TODO replace print with actual email sending using SendGrid or Resend

    return _render(
        "forgot_password.html",
        request,
        success="If an account exists with that email, you will receive a reset link shortly.",
    )


@router.get("/reset-password")
def reset_password_page(request: Request, token: str = ""):
    try:
        reset_serializer.loads(token, salt="password-reset", max_age=3600)
    except Exception:
        return _render("reset_password.html", request, token="", error="This reset link has expired. Please request a new one.")

    return _render("reset_password.html", request, token=token)


@router.post("/reset-password")
def reset_password(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(csrf_token):
        return _render("reset_password.html", request, token=token, error="Invalid request. Please try again.")

    try:
        email = reset_serializer.loads(token, salt="password-reset", max_age=3600)
    except Exception:
        return _render("reset_password.html", request, token="", error="This reset link has expired. Please request a new one.")

    if new_password != confirm_password:
        return _render("reset_password.html", request, token=token, error="Passwords do not match.")
    if len(new_password) < 8:
        return _render("reset_password.html", request, token=token, error="Password must be at least 8 characters.")
    if len(new_password) > 128:
        return _render("reset_password.html", request, token=token, error="Password must be 128 characters or less.")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return _render("reset_password.html", request, token="", error="This reset link has expired. Please request a new one.")

    user.password_hash = hash_password(new_password)
    db.commit()

    response = RedirectResponse(url="/login", status_code=302)
    response.set_cookie(
        "auth_success",
        "Password updated. You can sign in now.",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=300,
        path="/",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session", path="/")
    return response
