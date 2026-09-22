from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from pii_guard.security.auth import admin_required

router = APIRouter()


@router.get("/admin/config", dependencies=[Depends(admin_required)])
async def admin_config(request: Request) -> dict[str, Any]:
    config_store = request.app.state.config_store
    config, _ = config_store.current()
    systems = {}
    for name, system in config.system_configs().items():
        systems[name] = {
            "enabled": system.enabled,
            "pii_types": system.pii_types,
            "mask_style": system.mask_style,
            "unmask": system.unmask,
            "strict": system.strict,
            "rules": [
                {"type": rule.type, "requires_any": rule.requires_any} for rule in system.rules
            ],
        }
    registry = config.type_registry()
    types = [{"code": code, "label": registry.label(code)} for code in sorted(registry.codes())]
    return {"systems": systems, "types": types}


@router.post("/admin/reload", dependencies=[Depends(admin_required)])
async def admin_reload(request: Request) -> dict[str, Any]:
    config_store = request.app.state.config_store
    error = config_store.reload()
    if error is not None:
        raise HTTPException(status_code=422, detail={"error": error})
    return {"status": "reloaded"}
