import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from database import engine, get_db
import models
from template_helpers import configure_templates
from utils.csrf import generate_csrf_token
from utils.errors import general_exception_handler, http_exception_handler
from utils.logger import app_logger


SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        environment=os.getenv("ENV", "development"),
        send_default_pii=False,
    )
    app_logger.info("Sentry initialized", extra={"env": os.getenv("ENV")})
else:
    app_logger.info("Sentry DSN not set, skipping error tracking")


limiter = Limiter(key_func=get_remote_address)
templates = configure_templates(Jinja2Templates(directory=BASE_DIR / "templates"))
templates.env.globals["generate_csrf_token"] = generate_csrf_token

from routers import chat, schedule, tasks, team
from routers.auth import require_auth, router as auth_router
from models import User
from services.task_service import get_all_tasks, get_tasks_summary


def get_allowed_hosts() -> list[str]:
    allowed_hosts = [
        host.strip()
        for host in os.getenv("ALLOWED_HOSTS", "*").split(",")
        if host.strip()
    ]
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_hostname and render_hostname not in allowed_hosts:
        allowed_hosts.append(render_hostname)
    railway_hostname = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway_hostname and railway_hostname not in allowed_hosts:
        allowed_hosts.append(railway_hostname)
    return allowed_hosts or ["*"]


app = FastAPI(title="Solo")
app.state.limiter = limiter
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=get_allowed_hosts(),
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(auth_router)
app.include_router(tasks.router)
app.include_router(schedule.router)
app.include_router(chat.router)
app.include_router(team.router)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    max_size = 1 * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return JSONResponse(status_code=413, content={"error": "Request too large"})
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if os.getenv("ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)

    log_data = {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
    }

    if response.status_code >= 500:
        app_logger.error("Request error", extra=log_data)
    elif response.status_code >= 400:
        app_logger.warning("Request warning", extra=log_data)
    elif duration_ms > 2000:
        app_logger.warning("Slow request", extra=log_data)
    else:
        app_logger.info("Request", extra=log_data)

    return response


@app.on_event("startup")
async def startup_event():
    app_logger.info(
        "Solo starting up",
        extra={
            "env": os.getenv("ENV", "development"),
            "database": "postgres" if "postgresql" in os.getenv("DATABASE_URL", "") else "sqlite",
        },
    )
    # Run `alembic upgrade head` before starting the app.
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        app_logger.info("Database connection healthy")
    except Exception as exc:
        app_logger.error("Database connection failed", extra={"error": str(exc)})
        raise


@app.on_event("shutdown")
async def shutdown_event():
    app_logger.info("Solo shutting down")

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": "Too many attempts. Please wait a minute.",
            "success": None,
        },
        status_code=429,
    )


@app.api_route("/", methods=["GET", "HEAD"])
def home(request: Request):
    if request.method == "HEAD":
        return Response(status_code=204)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        app_logger.error(f"Database health check failed: {e}")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "environment": os.getenv("ENV", "development"),
    }


@app.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    summary = get_tasks_summary(db, current_user.id)
    top_priorities = [
        task
        for task in get_all_tasks(db, current_user.id)
        if task.priority in {"urgent", "high"} and task.status != "done"
    ][:3]

    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "Good morning."
    elif 12 <= hour < 17:
        greeting = "Good afternoon."
    else:
        greeting = "Good evening."

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard - Solo",
            "greeting": greeting,
            "summary": summary,
            "focus_tasks": top_priorities,
            "top_priorities": top_priorities,
            "current_user": current_user,
        },
    )
