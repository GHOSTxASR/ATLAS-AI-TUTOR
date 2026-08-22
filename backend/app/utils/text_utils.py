from __future__ import annotations

import re

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)```", re.DOTALL)


def extract_json_payload(text: str) -> str:
    """Pull the JSON document out of a model response.

    Models are asked to return "ONLY JSON" but routinely wrap it in a fenced
    code block or a sentence of preamble. Each service used to re-implement a
    fragile ``startswith("```")`` check that missed both cases; this handles
    fences anywhere in the text and trims surrounding prose.

    Returns a best-effort JSON substring - the caller still parses it and
    handles ``json.JSONDecodeError``.
    """
    if not text:
        return ""

    candidate = text.strip()
    fenced = _FENCE_RE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    starts = [i for i in (candidate.find("{"), candidate.find("[")) if i != -1]
    if not starts:
        return candidate

    start = min(starts)
    closer = "}" if candidate[start] == "{" else "]"
    end = candidate.rfind(closer)
    if end > start:
        candidate = candidate[start : end + 1]
    return candidate.strip()

