from __future__ import annotations

import re
from collections.abc import Callable

from pydantic import BaseModel, Field, field_validator, model_validator

from pii_guard.recognizers.validators import inn_valid, luhn_valid, snils_valid

VALID_MASK_STYLES = frozenset({"partial", "label", "token", "full"})
VALIDATORS: dict[str, Callable[[str], bool] | None] = {
    "luhn": luhn_valid,
    "inn": inn_valid,
    "snils": snils_valid,
    "null": None,
}


class PartialSpecModel(BaseModel):
    keep_start: int = 0
    keep_end: int = 0


class CustomRuleModel(BaseModel):
    regex: str
    base_score: float
    context: list[str] = Field(default_factory=list)
    context_bonus: float = 0.0
    context_window: int = 40
    validator: str | None = None
    negative: list[str] = Field(default_factory=list)
    negative_penalty: float = 0.0

    @field_validator("regex")
    @classmethod
    def _valid_regex(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"битый regex: {exc}") from exc
        return value

    @field_validator("validator")
    @classmethod
    def _valid_validator(cls, value: str | None) -> str | None:
        if value is not None and value not in VALIDATORS:
            raise ValueError(f"неизвестный validator: {value!r}")
        return value


class CustomTypeModel(BaseModel):
    label: str
    description: str = ""
    rules: list[CustomRuleModel]


class PiiTypesConfig(BaseModel):
    partial_specs: dict[str, PartialSpecModel] = Field(default_factory=dict)
    custom_types: dict[str, CustomTypeModel] = Field(default_factory=dict)


class SystemRuleModel(BaseModel):
    type: str
    requires_any: list[str] = Field(default_factory=list)


class SystemConfigModel(BaseModel):
    enabled: bool = True
    pii_types: str | list[str] = "all"
    mask_style: str = "partial"
    unmask: bool = True
    strict: bool = False
    api_key_sha256: str | None = None
    rules: list[SystemRuleModel] = Field(default_factory=list)

    @field_validator("mask_style")
    @classmethod
    def _valid_mask_style(cls, value: str) -> str:
        if value not in VALID_MASK_STYLES:
            raise ValueError(f"неизвестный mask_style: {value!r}")
        return value


class SystemsDefaultsModel(BaseModel):
    mask_style: str = "partial"
    unmask: bool = True
    strict: bool = False

    @field_validator("mask_style")
    @classmethod
    def _valid_mask_style(cls, value: str) -> str:
        if value not in VALID_MASK_STYLES:
            raise ValueError(f"неизвестный mask_style: {value!r}")
        return value


class SystemsConfig(BaseModel):
    defaults: SystemsDefaultsModel = Field(default_factory=SystemsDefaultsModel)
    systems: dict[str, SystemConfigModel] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _apply_defaults(self) -> SystemsConfig:
        for system in self.systems.values():
            if "mask_style" not in system.model_fields_set:
                system.mask_style = self.defaults.mask_style
            if "unmask" not in system.model_fields_set:
                system.unmask = self.defaults.unmask
            if "strict" not in system.model_fields_set:
                system.strict = self.defaults.strict
        return self
