"""Tests for the non-interactive helper functions in
scripts/kite_daily_login.py — the browser/input()-driven main() flow itself
needs a real human login and isn't unit-tested here.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kite_daily_login.py"
_spec = importlib.util.spec_from_file_location("kite_daily_login", _SCRIPT_PATH)
kite_daily_login = importlib.util.module_from_spec(_spec)
sys.modules["kite_daily_login"] = kite_daily_login
_spec.loader.exec_module(kite_daily_login)


def test_extract_request_token_from_full_url():
    url = "http://localhost:8000/callback?request_token=abc123&action=login&type=login&status=success"

    assert kite_daily_login._extract_request_token(url) == "abc123"


def test_extract_request_token_from_bare_token():
    assert kite_daily_login._extract_request_token("  abc123  ") == "abc123"


def test_update_env_file_replaces_existing_line(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("KITE_API_KEY=x\nKITE_ACCESS_TOKEN=old-value\nOTHER=y\n")
    monkeypatch.setattr(kite_daily_login, "ENV_PATH", env_file)

    kite_daily_login._update_env_file("new-value")

    text = env_file.read_text()
    assert "KITE_ACCESS_TOKEN=new-value" in text
    assert "OTHER=y" in text
    assert "old-value" not in text


def test_update_env_file_handles_a_token_containing_backslash_sequences(tmp_path, monkeypatch):
    # A naive re.sub(pattern, new_line, text) treats backslashes in the
    # replacement string as backreferences (\1, \g<name>, ...) and either
    # crashes or mangles the written value — the fix uses a callable repl.
    env_file = tmp_path / ".env"
    env_file.write_text("KITE_ACCESS_TOKEN=old-value\n")
    monkeypatch.setattr(kite_daily_login, "ENV_PATH", env_file)
    tricky_token = r"ab\1cd\g<name>ef"

    kite_daily_login._update_env_file(tricky_token)

    assert env_file.read_text() == f"KITE_ACCESS_TOKEN={tricky_token}\n"


def test_update_env_file_appends_when_no_existing_line(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("KITE_API_KEY=x\n")
    monkeypatch.setattr(kite_daily_login, "ENV_PATH", env_file)

    kite_daily_login._update_env_file("new-value")

    assert "KITE_ACCESS_TOKEN=new-value" in env_file.read_text()
