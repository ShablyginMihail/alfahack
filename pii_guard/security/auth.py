from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request

from pii_guard.core.policy import Profile


def current_system(
    request: Request, x_api_key: str | None = Header(default=None)
) -> tuple[str, Profile]:
    if x_api_key is None:
        raise HTTPException(status_code=401, detail={"error": "missing_api_key"})
    config_store = request.app.state.config_store
    config, _ = config_store.current()
    found = config.system_for_key(x_api_key)
    if found is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})
    name, system = found
    if not system.enabled:
        raise HTTPException(status_code=403, detail={"error": "system_disabled"})
    profile = config.profiles().get(name)
    if profile is None:
        raise HTTPException(status_code=403, detail={"error": "system_disabled"})
    return name, profile


def admin_required(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    settings = request.app.state.settings
    if settings.admin_token is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    expected = settings.admin_token.get_secret_value()
    if x_admin_token is None or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail={"error": "invalid_admin_token"})
