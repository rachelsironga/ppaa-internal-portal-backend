"""
Build ``DATABASES`` for Django settings.

Secondary DBs (performance, Maoni, RMS) share one Postgres instance in Docker
(see ``init-multiple-dbs.sh``). A common mistake is setting ``PERFORMANCE_*_HOST``
to ``localhost`` in ``.env`` while ``POSTGRES_DB_HOST`` is ``postgres`` for the
container — that makes Django connect to the app container, not Postgres.
"""
from __future__ import annotations

import os
from typing import TypedDict


class _ReportsKeys(TypedDict):
    name_key: str
    user_key: str
    pwd_key: str
    host_key: str
    port_key: str


def _env_strip(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def build_databases(
    *,
    reports_keys: _ReportsKeys | None = None,
) -> dict:
    """
    ``reports_keys`` defaults to ``RMS_REPORTS_MANAGEMENT_DB_*`` env names.
    ``settings_prod`` uses ``REPORTS_MANAGEMENT_DB_*`` instead.
    """
    rk: _ReportsKeys = reports_keys or {
        "name_key": "RMS_REPORTS_MANAGEMENT_DB_NAME",
        "user_key": "RMS_REPORTS_MANAGEMENT_DB_USER",
        "pwd_key": "RMS_REPORTS_MANAGEMENT_DB_PWD",
        "host_key": "RMS_REPORTS_MANAGEMENT_DB_HOST",
        "port_key": "RMS_REPORTS_MANAGEMENT_DB_PORT",
    }

    _postgres_name = _env_strip("POSTGRES_DB_NAME")
    _postgres_user = _env_strip("POSTGRES_DB_USER")
    _postgres_pwd = os.getenv("POSTGRES_DB_PWD")
    _postgres_host = _env_strip("POSTGRES_DB_HOST", "localhost")
    _postgres_port = _env_strip("POSTGRES_DB_PORT", "5432")

    def _secondary_db_host(specific_host: str | None) -> str:
        s = (specific_host or "").strip()
        loopback = {"localhost", "127.0.0.1", "::1"}
        if s and s not in loopback:
            return s
        if _postgres_host and _postgres_host not in loopback:
            return _postgres_host
        return s or _postgres_host or "localhost"

    def _secondary_env_points_at_loopback(host_key: str) -> bool:
        raw = _env_strip(host_key)
        loopback = {"localhost", "127.0.0.1", "::1"}
        return bool(raw and raw in loopback)

    def _secondary_db_entry(
        *,
        name_key: str,
        user_key: str,
        pwd_key: str,
        host_key: str,
        port_key: str,
        default_name: str | None,
    ) -> dict:
        raw_host = _env_strip(host_key)
        primary_non_loopback = bool(
            _postgres_host and _postgres_host not in {"localhost", "127.0.0.1", "::1"}
        )
        use_primary_creds = primary_non_loopback and (
            _secondary_env_points_at_loopback(host_key) or not raw_host
        )
        sec_user = _env_strip(user_key)
        sec_pwd = _env_strip(pwd_key)
        if use_primary_creds:
            user = _postgres_user
            password = _postgres_pwd
        else:
            user = sec_user or _postgres_user
            password = sec_pwd if sec_pwd is not None else _postgres_pwd
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env_strip(name_key, default_name) or default_name,
            "USER": user,
            "PASSWORD": password,
            "HOST": _secondary_db_host(_env_strip(host_key)),
            "PORT": _env_strip(port_key) or _postgres_port,
        }

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _postgres_name,
            "USER": _postgres_user,
            "PASSWORD": _postgres_pwd,
            "HOST": _postgres_host,
            "PORT": _postgres_port,
        },
        "performance_dashboard_db": _secondary_db_entry(
            name_key="PERFORMANCE_DASHBOARD_DB_NAME",
            user_key="PERFORMANCE_DASHBOARD_DB_USER",
            pwd_key="PERFORMANCE_DASHBOARD_DB_PWD",
            host_key="PERFORMANCE_DASHBOARD_DB_HOST",
            port_key="PERFORMANCE_DASHBOARD_DB_PORT",
            default_name="performance_dashboard_db",
        ),
        "maoni_db": _secondary_db_entry(
            name_key="MAONI_DB_NAME",
            user_key="MAONI_DB_USER",
            pwd_key="MAONI_DB_PWD",
            host_key="MAONI_DB_HOST",
            port_key="MAONI_DB_PORT",
            default_name="maoni_db",
        ),
        "reports_management_db": _secondary_db_entry(
            name_key=rk["name_key"],
            user_key=rk["user_key"],
            pwd_key=rk["pwd_key"],
            host_key=rk["host_key"],
            port_key=rk["port_key"],
            default_name="reports_management_db",
        ),
    }
