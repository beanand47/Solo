from main import get_allowed_hosts
from database import normalize_database_url


def test_allowed_hosts_includes_render_hostname(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "solo-e9op.onrender.com")

    assert get_allowed_hosts() == ["example.com", "solo-e9op.onrender.com"]


def test_allowed_hosts_strips_empty_values(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", " example.com, ,www.example.com ")
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)

    assert get_allowed_hosts() == ["example.com", "www.example.com"]


def test_normalize_database_url_accepts_postgres_scheme():
    assert normalize_database_url("postgres://user:pass@host:5432/db") == "postgresql://user:pass@host:5432/db"
