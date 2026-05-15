from types import SimpleNamespace

import pytest

from services import ai_service


class FakeCompletions:
    def __init__(self, value=None, stream=None, error=None):
        self.value = value
        self.stream = stream
        self.error = error

    def create(self, **kwargs):
        if self.error:
            raise self.error
        if kwargs.get("stream"):
            return self.stream
        return self.value


class FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_generate_day_plan_success(monkeypatch):
    fake = FakeClient(FakeCompletions(_response('{"summary":"Ok","time_blocks":[],"top_3":[],"avoid":"noise"}')))
    monkeypatch.setattr(ai_service, "_require_client", lambda: fake)

    result = ai_service.generate_day_plan("Brain dump", [])

    assert isinstance(result, dict)
    assert "time_blocks" in result


def test_generate_day_plan_openai_error(monkeypatch):
    fake = FakeClient(FakeCompletions(error=RuntimeError("OpenAI failed")))
    monkeypatch.setattr(ai_service, "_require_client", lambda: fake)

    try:
        ai_service.generate_day_plan("Brain dump", [])
    except RuntimeError as exc:
        assert "OpenAI failed" in str(exc)
    else:
        pytest.fail("Expected OpenAI failure to be raised cleanly")


def test_generate_onboarding_brief_success(monkeypatch):
    fake = FakeClient(FakeCompletions(_response("Welcome to Solo.")))
    monkeypatch.setattr(ai_service, "_require_client", lambda: fake)

    result = ai_service.generate_onboarding_brief("Alex", [], [])

    assert isinstance(result, str)
    assert result


def test_build_system_prompt():
    tasks = [SimpleNamespace(priority="urgent", title="Fix billing", status="todo", due_date=None)]

    prompt = ai_service.build_system_prompt(tasks, "Plan text")

    assert "Fix billing" in prompt
    assert "Today is" in prompt
    assert "Plan text" in prompt


def test_stream_chat_tool_call(monkeypatch):
    tool_call = SimpleNamespace(
        index=0,
        function=SimpleNamespace(name="create_task", arguments='{"title":"Test","priority":"high"}'),
    )
    chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[tool_call]))]
    )
    fake = FakeClient(FakeCompletions(stream=[chunk]))
    monkeypatch.setattr(ai_service, "_require_client", lambda: fake)

    chunks = list(ai_service.stream_chat([], [], None))

    assert any("__TOOL_CALL__:create_task" in item for item in chunks)
