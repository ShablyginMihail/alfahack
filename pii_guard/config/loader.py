from __future__ import annotations

import hmac
import re
import time
from pathlib import Path

import yaml

from pii_guard.config.keys import sha256_hex
from pii_guard.config.models import (
    VALIDATORS,
    PiiTypesConfig,
    SystemConfigModel,
    SystemsConfig,
)
from pii_guard.core.context import compile_keywords
from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker, PartialSpec
from pii_guard.core.policy import CombinationRule, Profile
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import PiiType, TypeRegistry, default_type_registry
from pii_guard.observability.logging import get_logger
from pii_guard.recognizers.base import PatternRule, RegexRecognizer

logger = get_logger("pii_guard.config")

_RELOAD_INTERVAL = 5.0


class AppConfig:
    def __init__(self, systems: SystemsConfig, pii_types: PiiTypesConfig) -> None:
        self._systems = systems
        self._pii_types = pii_types
        self._registry = self._build_type_registry()
        self._profiles: dict[str, Profile] | None = None

    def _build_type_registry(self) -> TypeRegistry:
        registry = default_type_registry()
        for code, custom in self._pii_types.custom_types.items():
            registry.register(PiiType(code, custom.label, custom.description))
        return registry

    def profiles(self) -> dict[str, Profile]:
        if self._profiles is None:
            self._profiles = self._build_profiles()
        return self._profiles

    def _build_profiles(self) -> dict[str, Profile]:
        valid = self._registry.codes()
        result: dict[str, Profile] = {}
        for name, system in self._systems.systems.items():
            if not system.enabled:
                continue
            if system.pii_types != "all":
                for pii_type in system.pii_types:
                    if pii_type not in valid:
                        raise ValueError(f"система {name}: неизвестный тип ПД {pii_type!r}")
            for rule in system.rules:
                if rule.type not in valid:
                    raise ValueError(f"система {name}: неизвестный тип ПД {rule.type!r} в правиле")
                for req in rule.requires_any:
                    if req not in valid:
                        raise ValueError(f"система {name}: неизвестный тип ПД {req!r} в правиле")
            pii_types = None if system.pii_types == "all" else frozenset(system.pii_types)
            rules = tuple(
                CombinationRule(rule.type, frozenset(rule.requires_any)) for rule in system.rules
            )
            result[name] = Profile(
                name=name,
                pii_types=pii_types,
                mask_style=system.mask_style,
                unmask=system.unmask,
                strict=system.strict,
                rules=rules,
            )
        return result

    def system_for_key(self, api_key: str) -> tuple[str, SystemConfigModel] | None:
        digest = sha256_hex(api_key)
        for name, system in self._systems.systems.items():
            if system.api_key_sha256 and hmac.compare_digest(digest, system.api_key_sha256):
                return name, system
        return None

    def type_registry(self) -> TypeRegistry:
        return self._registry

    def system_configs(self) -> dict[str, SystemConfigModel]:
        return dict(self._systems.systems)

    def partial_specs(self) -> dict[str, PartialSpec]:
        return {
            key: PartialSpec(spec.keep_start, spec.keep_end)
            for key, spec in self._pii_types.partial_specs.items()
        }


def load_config(config_dir: Path) -> AppConfig:
    systems = SystemsConfig.model_validate(
        yaml.safe_load((config_dir / "systems.yaml").read_text(encoding="utf-8"))
    )
    pii_types = PiiTypesConfig.model_validate(
        yaml.safe_load((config_dir / "pii_types.yaml").read_text(encoding="utf-8"))
    )
    return AppConfig(systems, pii_types)


def build_engine(config: AppConfig, recognizer_modules: list[str]) -> Engine:
    registry = RecognizerRegistry.from_modules(recognizer_modules)
    for code, custom in config._pii_types.custom_types.items():
        rules = []
        for rule in custom.rules:
            rules.append(
                PatternRule(
                    pii_type=code,
                    regex=re.compile(rule.regex),
                    base_score=rule.base_score,
                    validator=VALIDATORS.get(rule.validator) if rule.validator else None,
                    validator_bonus=0.35,
                    context=compile_keywords(rule.context) if rule.context else None,
                    context_bonus=rule.context_bonus,
                    context_window=rule.context_window,
                    negative=compile_keywords(rule.negative) if rule.negative else None,
                    negative_penalty=rule.negative_penalty,
                )
            )
        registry.register(RegexRecognizer(f"custom_{code}", rules))
    masker = DefaultMasker(config.type_registry(), config.partial_specs())
    return Engine(registry, masker)


class ConfigStore:
    def __init__(self, config_dir: Path, recognizer_modules: list[str]) -> None:
        self._config_dir = Path(config_dir)
        self._recognizer_modules = recognizer_modules
        self._current: tuple[AppConfig, Engine] | None = None
        self._mtimes: dict[str, float] = {}
        self._last_reload = 0.0
        self.reload()

    def current(self) -> tuple[AppConfig, Engine]:
        if self._current is None:
            raise RuntimeError("config not loaded")
        return self._current

    def reload(self) -> str | None:
        try:
            config = load_config(self._config_dir)
            engine = build_engine(config, self._recognizer_modules)
            self._current = (config, engine)
            self._mtimes = self._file_mtimes()
            return None
        except Exception as exc:
            logger.warning("config_reload_failed", error=str(exc))
            return str(exc)

    def maybe_reload(self) -> None:
        now = time.monotonic()
        if now - self._last_reload < _RELOAD_INTERVAL:
            return
        self._last_reload = now
        if self._file_mtimes() != self._mtimes:
            self.reload()

    def _file_mtimes(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for name in ("systems.yaml", "pii_types.yaml"):
            path = self._config_dir / name
            if path.exists():
                result[name] = path.stat().st_mtime
        return result
