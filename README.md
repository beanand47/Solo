# Solo AI

A personal productivity manager built for solo founders.

## Why this project

Solo AI helps users stay focused by combining task management, scheduling, and AI-powered planning in one polished web app.
This repo is a strong portfolio piece because it demonstrates:
- end-to-end product thinking from auth to dashboard to AI workflow
- modern backend architecture using FastAPI and SQLAlchemy
- real product utility with AI-driven day planning and team onboarding support
- deployment readiness with production-grade config and documentation

## Product features

- **Secure authentication** with sign-up, login, and session management
- **Task management** with create/update/delete, priorities, deadlines, assignment, and status tracking
- **AI planning** using OpenAI to generate structured daily plans from a user brain dump
- **Schedule workflow** for building a day plan and capturing reflection questions
- **Conversational productivity assistant** with chat-based task guidance and tool-enabled task actions
- **Team onboarding** with member brief generation and collaboration-ready summaries
- **Server-side rendering** with Jinja2 templates for a responsive, polished UI

## Tech stack

- Python 3.11
- FastAPI
- Uvicorn
- SQLAlchemy
- Jinja2 templates
- OpenAI API
- `python-dotenv` for environment configuration
- `passlib[bcrypt]` for password hashing

## Architecture

- `main.py`: app bootstrap, router registration, database initialization, static file mounting
- `routers/`: route handlers for auth, tasks, schedule, chat, and team pages
- `services/`: business logic and AI integration separated from request handling
- `database.py`: SQLAlchemy engine and session management
- `templates/` + `static/`: UI layer, responsive pages, and style assets

## Run locally

1. Clone the repo
2. Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Create a `.env` file with:

```env
OPENAI_API_KEY=sk-your-openai-key
SECRET_KEY=your-secret-key
APP_ENV=development
COOKIE_SECURE=false
DATABASE_URL=sqlite:///./solo_ai.db
```

5. Start the app

```bash
uvicorn main:app --reload
```

6. Open `http://127.0.0.1:8000` in your browser

## Deployment

This project is ready for deployment on platforms like **Render** or **Railway**.

Recommended start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

- `OPENAI_API_KEY`
- `SECRET_KEY`
- `APP_ENV=production`
- `COOKIE_SECURE=true`

Optional but recommended for production:

- `DATABASE_URL` for a managed database (PostgreSQL recommended)

## Notes

- Keep `.env` out of source control
- The app defaults to SQLite for quick setup, but a managed DB is recommended for production
- The health check endpoint is available at `/health`
