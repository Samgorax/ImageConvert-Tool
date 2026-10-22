from __future__ import annotations

from contextlib import contextmanager
import sqlite3

from storage import settings_repository


def test_boolean_policy_defaults_fail_closed_and_group_settings_are_persisted(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    @contextmanager
    def memory_connection():
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    monkeypatch.setattr(settings_repository, "get_connection", memory_connection)

    assert not settings_repository.get_bool("policy_allow_ai_suggestions")
    assert not settings_repository.get_bool("unknown_sensitive_permission")

    settings_repository.set_values({
        "local_embedding_model": "nomic-embed-text:latest",
        "local_chat_model": "phi3:latest",
        "policy_allow_ai_suggestions": "true",
        "policy_allow_document_access": "false",
    })

    assert settings_repository.get("local_embedding_model") == "nomic-embed-text:latest"
    assert settings_repository.get("local_chat_model") == "phi3:latest"
    assert settings_repository.get_bool("policy_allow_ai_suggestions")
    assert not settings_repository.get_bool("policy_allow_document_access")
    connection.close()
