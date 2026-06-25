"""Lenient JSON extraction for model output.

Free/reasoning models often wrap their JSON in chain-of-thought prose or
```json fences. This recovers the JSON object instead of failing outright.
"""
from __future__ import annotations
import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json_object(raw: str | None) -> Any:
    """Return the JSON value in `raw`, tolerating prose/reasoning/fence wrappers.

    Tries, in order: direct parse -> fenced ```json block -> first balanced
    {...} span (brace-matched, string-aware). Raises ValueError if none parse.
    """
    if not raw or not raw.strip():
        raise ValueError("empty model output")
    s = raw.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    m = _FENCE.search(s)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = s.find("{")
    if start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("no JSON object found in model output")
