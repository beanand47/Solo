import json
import os
import time
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
import sentry_sdk

from utils.logger import get_logger


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key, timeout=30.0, max_retries=2) if api_key else None
logger = get_logger("solo.ai")


def _capture_exception(exc: Exception) -> None:
    if os.getenv("SENTRY_DSN"):
        sentry_sdk.capture_exception(exc)


def _handle_openai_exception(exc: Exception, function_name: str) -> None:
    _capture_exception(exc)
    if isinstance(exc, APITimeoutError):
        logger.error("OpenAI timeout", extra={"function": function_name})
        raise ValueError("The AI is taking too long. Please try again.") from exc
    if isinstance(exc, RateLimitError):
        logger.error("OpenAI rate limit hit", extra={"function": function_name})
        raise ValueError("AI service is busy. Please wait a moment and try again.") from exc
    if isinstance(exc, APIConnectionError):
        logger.error("OpenAI connection error", extra={"function": function_name})
        raise ValueError("Could not reach the AI service. Check your connection.") from exc
    if isinstance(exc, APIStatusError):
        logger.error(f"OpenAI API error: {exc.status_code}", extra={"function": function_name})
        raise ValueError("The AI service returned an error. Please try again.") from exc


SYSTEM_PROMPT = (
    "You are a calm, focused productivity assistant.\n"
    "You help solo founders plan their day with clarity.\n"
    "Be direct. No fluff. Prioritize ruthlessly."
)


def format_tasks(tasks):
    if not tasks:
        return "No open tasks."

    lines = []
    for task in tasks:
        due = f", due {task.due_date}" if task.due_date else ""
        project = f", project {task.project}" if task.project else ""
        lines.append(f"- [{task.priority}] {task.title} ({task.status}{due}{project})")
    return "\n".join(lines)


def _require_client():
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return client


def generate_day_plan(brain_dump: str, tasks: list) -> dict:
    start = time.time()
    function_name = "generate_day_plan"
    logger.info("AI call starting", extra={"function": function_name})
    prompt = f"""
    The user's brain dump for today:
    {brain_dump}

    Their open tasks (by priority):
    {format_tasks(tasks)}

    Return a JSON object with this exact structure:
    {{
      "summary": "one sentence about the day's theme",
      "time_blocks": [
        {{
          "time": "9:00 - 10:30",
          "label": "Deep work: [task title]",
          "category": "deep_work",
          "note": "optional short tip"
        }}
      ],
      "top_3": ["priority 1", "priority 2", "priority 3"],
      "avoid": "one thing to not do today"
    }}

    Categories: deep_work / meeting / admin / break / review
    Return ONLY valid JSON. No markdown, no extra text.
    """

    try:
        response = _require_client().chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        logger.info(
            "AI call completed",
            extra={"function": function_name, "duration_ms": round((time.time() - start) * 1000, 2)},
        )
        return result
    except Exception as e:
        logger.error("AI call failed", extra={"function": function_name, "error": str(e)})
        _handle_openai_exception(e, function_name)
        _capture_exception(e)
        raise


def generate_reflection_questions(day_plan: str) -> list[str]:
    start = time.time()
    function_name = "generate_reflection_questions"
    logger.info("AI call starting", extra={"function": function_name})
    prompt = f"""
    Based on this planned day, return 3 short, specific reflection questions.

    Planned day:
    {day_plan}

    Return ONLY a JSON array of strings. No markdown, no extra text.
    """

    try:
        response = _require_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "[]"
        parsed = json.loads(content)
        result = [str(question) for question in parsed][:3] if isinstance(parsed, list) else []
        logger.info(
            "AI call completed",
            extra={"function": function_name, "duration_ms": round((time.time() - start) * 1000, 2)},
        )
        return result
    except Exception as e:
        logger.error("AI call failed", extra={"function": function_name, "error": str(e)})
        _handle_openai_exception(e, function_name)
        _capture_exception(e)
        raise


def build_system_prompt(tasks: list, day_plan: str | None) -> str:
    today = datetime.now().strftime("%A, %B %d %Y")
    task_text = "\n".join(
        [
            f"- [{task.priority.upper()}] {task.title} ({task.status})"
            + (f" - due {task.due_date}" if task.due_date else "")
            for task in tasks[:12]
        ]
    ) or "No open tasks."

    return f"""You are the personal AI chief of staff for a solo founder.
Today is {today}.

Their open tasks:
{task_text}

Today's plan:
{day_plan or "Not planned yet."}

Your personality:
- Direct and warm. Like a trusted advisor, not a chatbot.
- Reference their actual tasks. Never be generic.
- If they seem overwhelmed, help them pick ONE thing to start.
- When they ask you to add a task or update one, call the right function.
- Keep responses concise. Use short paragraphs. Avoid bullet spam."""


tools = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["urgent", "high", "medium", "low"],
                    },
                    "due_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD or null",
                    },
                    "project": {"type": "string"},
                },
                "required": ["title", "priority"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Update the status of an existing task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "done"],
                    },
                },
                "required": ["task_id", "status"],
            },
        },
    },
]


def stream_chat(messages: list, tasks: list, day_plan: str | None):
    start = time.time()
    function_name = "stream_chat"
    logger.info("AI stream starting", extra={"function": function_name})
    system = build_system_prompt(tasks, day_plan)
    full_messages = [{"role": "system", "content": system}] + messages

    try:
        stream = _require_client().chat.completions.create(
            model="gpt-4o",
            messages=full_messages,
            tools=tools,
            stream=True,
        )

        tool_calls = {}
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    index = tool_call.index
                    current = tool_calls.setdefault(index, {"name": "", "arguments": ""})
                    if tool_call.function.name:
                        current["name"] += tool_call.function.name
                    if tool_call.function.arguments:
                        current["arguments"] += tool_call.function.arguments

        for tool_call in tool_calls.values():
            if tool_call["name"]:
                yield f"\n__TOOL_CALL__:{tool_call['name']}:{tool_call['arguments']}"

        logger.info(
            "AI stream completed",
            extra={"function": function_name, "duration_ms": round((time.time() - start) * 1000, 2)},
        )
    except Exception as e:
        logger.error("AI stream failed", extra={"function": function_name, "error": str(e)})
        _handle_openai_exception(e, function_name)
        _capture_exception(e)
        raise


def generate_onboarding_brief(member_name: str, tasks: list, projects: list) -> str:
    start = time.time()
    function_name = "generate_onboarding_brief"
    logger.info("AI call starting", extra={"function": function_name})
    task_summary = "\n".join(
        [f"- [{task.priority}] {task.title} ({task.status})" for task in tasks[:15]]
    )
    if not task_summary:
        task_summary = "- No active tasks yet."

    projects_text = ", ".join(set(task.project for task in tasks if task.project)) or "various"

    prompt = f"""
Write a warm, clear onboarding brief for {member_name}, a new team member.

Current work in progress:
{task_summary}

Active project areas: {projects_text}

Write 3 short sections:
1. "What we're building" - 2 sentences on the mission/product
2. "Right now" - 3 bullet points of the most important active tasks
3. "How we work" - 3 bullet points of working style / principles

Tone: warm, direct, founder-to-teammate. Not corporate. Not generic.
Max 220 words total.
"""
    try:
        response = _require_client().chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        result = response.choices[0].message.content or ""
        logger.info(
            "AI call completed",
            extra={"function": function_name, "duration_ms": round((time.time() - start) * 1000, 2)},
        )
        return result
    except Exception as e:
        logger.error("AI call failed", extra={"function": function_name, "error": str(e)})
        _handle_openai_exception(e, function_name)
        _capture_exception(e)
        raise
