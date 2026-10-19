"""Database connection configuration only, no live connection."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.database import connector as module


def test_connector_uses_postgres_environment(monkeypatch):
    env = {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5434",
        "POSTGRES_DB": "costpilot_test",
        "POSTGRES_USER": "tester",
        "POSTGRES_PASSWORD": "secret",
    }
    monkeypatch.setattr(module, "load_dotenv", lambda: None)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    conn_mock = MagicMock()
    monkeypatch.setattr(module.psycopg, "connect", conn_mock)
    connector = module.DBConnector()
    with connector.connect():
        pass
    conn_mock.assert_called_once_with(
        host="127.0.0.1", port=5434, dbname="costpilot_test",
        user="tester", password="secret"
    )


def test_connector_rejects_invalid_port(monkeypatch):
    monkeypatch.setattr(module, "load_dotenv", lambda: None)
    for name in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.setenv(name, "test")
    monkeypatch.setenv("POSTGRES_PORT", "bad-port")
    with pytest.raises(ValueError):
        module.DBConnector()
