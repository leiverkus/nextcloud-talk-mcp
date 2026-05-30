"""Tests for Settings.from_env() configuration validation."""

from __future__ import annotations

import pytest

from nextcloud_talk_core.config import Settings
from nextcloud_talk_core.errors import NextcloudConfigError

_VARS = ("NC_URL", "NC_USER", "NC_APP_PASSWORD")


@pytest.fixture
def clean_env(monkeypatch):
    for var in _VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_all_set_loads_and_normalises(clean_env):
    clean_env.setenv("NC_URL", "https://cloud.example.com/")  # trailing slash
    clean_env.setenv("NC_USER", "alice")
    clean_env.setenv("NC_APP_PASSWORD", "secret-token")

    settings = Settings.from_env()

    assert settings.nc_url == "https://cloud.example.com"  # stripped
    assert settings.nc_user == "alice"
    assert settings.nc_app_password == "secret-token"


def test_missing_url_raises(clean_env):
    clean_env.setenv("NC_USER", "alice")
    clean_env.setenv("NC_APP_PASSWORD", "secret-token")
    with pytest.raises(NextcloudConfigError, match="NC_URL is not set"):
        Settings.from_env()


def test_url_without_scheme_raises(clean_env):
    clean_env.setenv("NC_URL", "cloud.example.com")
    clean_env.setenv("NC_USER", "alice")
    clean_env.setenv("NC_APP_PASSWORD", "secret-token")
    with pytest.raises(NextcloudConfigError, match="must start with http"):
        Settings.from_env()


def test_missing_user_raises(clean_env):
    clean_env.setenv("NC_URL", "https://cloud.example.com")
    clean_env.setenv("NC_APP_PASSWORD", "secret-token")
    with pytest.raises(NextcloudConfigError, match="NC_USER is not set"):
        Settings.from_env()


def test_missing_password_raises(clean_env):
    clean_env.setenv("NC_URL", "https://cloud.example.com")
    clean_env.setenv("NC_USER", "alice")
    with pytest.raises(NextcloudConfigError, match="NC_APP_PASSWORD is not set"):
        Settings.from_env()


def test_http_scheme_accepted(clean_env):
    clean_env.setenv("NC_URL", "http://localhost:8080")
    clean_env.setenv("NC_USER", "alice")
    clean_env.setenv("NC_APP_PASSWORD", "secret-token")
    assert Settings.from_env().nc_url == "http://localhost:8080"


def test_whitespace_only_url_treated_as_missing(clean_env):
    clean_env.setenv("NC_URL", "   ")
    clean_env.setenv("NC_USER", "alice")
    clean_env.setenv("NC_APP_PASSWORD", "secret-token")
    with pytest.raises(NextcloudConfigError, match="NC_URL is not set"):
        Settings.from_env()
