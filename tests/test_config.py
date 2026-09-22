from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from pii_guard.config.loader import ConfigStore, build_engine, load_config
from pii_guard.core.policy import CHECKER_PROFILE
from pii_guard.settings import Settings

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config"


def _write_systems(tmp_path: Path, data: dict) -> None:
    (tmp_path / "systems.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )


def _write_pii_types(tmp_path: Path, data: dict) -> None:
    (tmp_path / "pii_types.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )


def _minimal_pii_types() -> dict:
    return {"partial_specs": {}, "custom_types": {}}


def test_load_repo_config() -> None:
    config = load_config(REPO_CONFIG)
    profiles = config.profiles()
    assert "checker" in profiles
    assert "crm-assistant" in profiles
    assert "marketing-bot" in profiles
    assert "support-chat" in profiles
    assert "legacy-crm" not in profiles


def test_profiles_match_yaml() -> None:
    config = load_config(REPO_CONFIG)
    profiles = config.profiles()
    assert profiles["checker"].mask_style == "partial"
    assert profiles["checker"].pii_types is None
    assert profiles["crm-assistant"].mask_style == "token"
    assert profiles["crm-assistant"].strict is True
    marketing = profiles["marketing-bot"]
    assert marketing.mask_style == "label"
    assert marketing.unmask is False
    assert marketing.pii_types == frozenset({"PERSON", "PHONE", "EMAIL", "CARD_NUMBER", "PIN"})
    assert len(marketing.rules) == 1
    assert marketing.rules[0].pii_type == "PIN"
    assert marketing.rules[0].requires_any == frozenset({"CARD_NUMBER"})
    assert profiles["support-chat"].mask_style == "partial"


def test_system_for_key(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {
                "crm-assistant": {
                    "pii_types": "all",
                    "api_key_sha256": hashlib.sha256(b"test-crm-key").hexdigest(),
                }
            },
        },
    )
    _write_pii_types(tmp_path, _minimal_pii_types())
    config = load_config(tmp_path)
    assert config.system_for_key("test-crm-key") is not None
    assert config.system_for_key("unknown-key") is None


def test_unknown_pii_type_error(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": ["UNKNOWN_TYPE"]}},
        },
    )
    _write_pii_types(tmp_path, _minimal_pii_types())
    config = load_config(tmp_path)
    with pytest.raises(ValueError):
        config.profiles()


def test_unknown_mask_style_error(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"mask_style": "bogus"}},
        },
    )
    _write_pii_types(tmp_path, _minimal_pii_types())
    with pytest.raises(ValueError):
        load_config(tmp_path)


def test_broken_regex_error(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": "all"}},
        },
    )
    _write_pii_types(
        tmp_path,
        {
            "partial_specs": {},
            "custom_types": {
                "OMS_POLICY": {
                    "label": "ПОЛИС_ОМС",
                    "rules": [{"regex": "(", "base_score": 0.2}],
                }
            },
        },
    )
    with pytest.raises(ValueError):
        load_config(tmp_path)


def test_custom_type_oms_policy(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": "all"}},
        },
    )
    _write_pii_types(
        tmp_path,
        {
            "partial_specs": {},
            "custom_types": {
                "OMS_POLICY": {
                    "label": "ПОЛИС_ОМС",
                    "description": "Полис ОМС",
                    "rules": [
                        {
                            "regex": r"(?<!\d)\d{16}(?!\d)",
                            "base_score": 0.2,
                            "context": ["полис", "омс"],
                            "context_bonus": 0.6,
                            "validator": "luhn",
                        }
                    ],
                }
            },
        },
    )
    config = load_config(tmp_path)
    engine = build_engine(config, Settings().recognizer_modules)
    result = engine.mask("полис ОМС 1234567890123456", CHECKER_PROFILE)
    assert "1234567890123456" not in result.text


def test_marketing_bot_pin_rule(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {
                "marketing-bot": {
                    "pii_types": ["PERSON", "PHONE", "EMAIL", "CARD_NUMBER", "PIN"],
                    "mask_style": "label",
                    "rules": [{"type": "PIN", "requires_any": ["CARD_NUMBER"]}],
                }
            },
        },
    )
    _write_pii_types(tmp_path, _minimal_pii_types())
    config = load_config(tmp_path)
    profile = config.profiles()["marketing-bot"]
    engine = build_engine(config, Settings().recognizer_modules)
    spans = engine.analyze("ПИН 1234", profile)
    assert not any(s.pii_type == "PIN" for s in spans)
    spans2 = engine.analyze("карта 4276 1234 5678 9012, ПИН 1234", profile)
    assert any(s.pii_type == "PIN" for s in spans2)


def test_reload_picks_up_changes(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": "all", "mask_style": "partial"}},
        },
    )
    _write_pii_types(tmp_path, _minimal_pii_types())
    store = ConfigStore(tmp_path, Settings().recognizer_modules)
    config, _ = store.current()
    assert config.profiles()["checker"].mask_style == "partial"

    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": "all", "mask_style": "token"}},
        },
    )
    store.reload()
    config2, _ = store.current()
    assert config2.profiles()["checker"].mask_style == "token"


def test_reload_keeps_old_on_broken(tmp_path: Path) -> None:
    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": "all", "mask_style": "partial"}},
        },
    )
    _write_pii_types(tmp_path, _minimal_pii_types())
    store = ConfigStore(tmp_path, Settings().recognizer_modules)
    _config, _ = store.current()

    _write_systems(
        tmp_path,
        {
            "defaults": {"mask_style": "partial"},
            "systems": {"checker": {"pii_types": "all", "mask_style": "bogus"}},
        },
    )
    store.reload()
    config2, _ = store.current()
    assert config2.profiles()["checker"].mask_style == "partial"
