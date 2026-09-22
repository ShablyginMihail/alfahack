from __future__ import annotations

from pathlib import Path

import yaml

from pii_guard.settings import Settings


def write_config(
    path: Path,
    systems: dict | None = None,
    pii_types: dict | None = None,
) -> None:
    if systems is None:
        systems = {
            "defaults": {"mask_style": "partial", "unmask": True, "strict": False},
            "systems": {
                "checker": {
                    "enabled": True,
                    "pii_types": "all",
                    "mask_style": "partial",
                }
            },
        }
    if pii_types is None:
        pii_types = {"partial_specs": {}, "custom_types": {}}
    (path / "systems.yaml").write_text(
        yaml.safe_dump(systems, allow_unicode=True), encoding="utf-8"
    )
    (path / "pii_types.yaml").write_text(
        yaml.safe_dump(pii_types, allow_unicode=True), encoding="utf-8"
    )


def make_settings(tmp_path: Path, **overrides) -> Settings:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    write_config(config_dir)
    base: dict = {
        "redis_url": None,
        "max_body_bytes": 1000,
        "log_level": "WARNING",
        "config_dir": config_dir,
        "recognizer_modules": ["tests.fake_recognizers"],
    }
    base.update(overrides)
    return Settings(**base)
