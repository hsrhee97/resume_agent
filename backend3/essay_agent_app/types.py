from __future__ import annotations

from typing import Any, TypedDict

EssaySections = tuple[str, str, str, str]
DEFAULT_ESSAY_SECTIONS: EssaySections = (
    "지원동기",
    "성장과정",
    "성격의 장단점",
    "입사 후 포부",
)


class EssayDrafts(TypedDict):
    지원동기: str
    성장과정: str
    성격의_장단점: str
    입사_후_포부: str


class LLMInvokeData(TypedDict, total=False):
    invoked: bool
    raw_response: str
    parse_success: bool
    parsed_json: dict[str, Any]
    used_fallback: bool
    error: str


class Diagnostics(TypedDict):
    errors: list[str]
    warnings: list[str]
