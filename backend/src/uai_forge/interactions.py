"""Safe parsing for public choice cards emitted by a model."""

from __future__ import annotations

import json
import re
from typing import Optional, Tuple

from .models import ChoicePrompt, ChoiceOption, reject_inline_secrets


_CHOICE_MARKER = re.compile(
    r"<!--\s*uai-choice\s*:(?P<payload>\{.*\})\s*-->",
    re.IGNORECASE | re.DOTALL,
)
_SENSITIVE_TEXT = re.compile(r"api[_-]?key|authorization|bearer|access[_-]?token|password|secret", re.I)


def extract_choice_prompt(*, output: str, run_id: str) -> Tuple[str, Optional[ChoicePrompt]]:
    """Extract a bounded JSON marker and leave normal assistant prose intact."""

    if not output or len(output) > 200_000:
        return output, None
    match = _CHOICE_MARKER.search(output)
    if not match:
        return output, None
    try:
        payload = json.loads(match.group("payload"))
        if not isinstance(payload, dict):
            raise ValueError("choice payload must be an object")
        reject_inline_secrets({"choice": payload})
        raw_options = payload.get("options")
        if not isinstance(raw_options, list) or not 2 <= len(raw_options) <= 8:
            raise ValueError("choice needs 2-8 options")
        options = []
        for index, raw in enumerate(raw_options, start=1):
            if not isinstance(raw, dict):
                raise ValueError("choice option must be an object")
            option_id = str(raw.get("id") or f"option_{index}")[:80]
            options.append(
                ChoiceOption(
                    id=option_id,
                    label=str(raw.get("label") or "").strip(),
                    description=str(raw.get("description") or "").strip(),
                    recommended=bool(raw.get("recommended", False)),
                )
            )
        public_text = " ".join(
            [str(payload.get("title") or ""), str(payload.get("description") or "")]
            + [f"{option.label} {option.description}" for option in options]
        )
        if _SENSITIVE_TEXT.search(public_text):
            raise ValueError("choice contains sensitive text")
        prompt = ChoicePrompt(
            run_id=run_id,
            title=str(payload.get("title") or "请选择一种方式").strip(),
            description=str(payload.get("description") or "").strip(),
            selection_type="multiple" if payload.get("selection_type") == "multiple" else "single",
            options=options,
            required=bool(payload.get("required", False)),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return output, None
    cleaned = (output[: match.start()] + output[match.end() :]).strip()
    return cleaned, prompt
