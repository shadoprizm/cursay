from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


FILLER_PATTERNS = (
    r"\b(?:um+|uh+|erm+|er+|ah+)\b[,.]?\s*",
    r"\b(?:you know|I mean)\b[,.]?\s*",
)

CODE_REPLACEMENTS = (
    (r"\bnew line\b", "\n"),
    (r"\btab\b", "\t"),
    (r"\bopen paren(?:thesis)?\b", "("),
    (r"\bclose paren(?:thesis)?\b", ")"),
    (r"\bopen bracket\b", "["),
    (r"\bclose bracket\b", "]"),
    (r"\bopen brace\b", "{"),
    (r"\bclose brace\b", "}"),
    (r"\bcolon\b", ":"),
    (r"\bsemicolon\b", ";"),
    (r"\bcomma\b", ","),
    (r"\bdot\b", "."),
    (r"\bequals\b", "="),
    (r"\bplus\b", "+"),
)


def _remove_fillers(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    result = text
    for pattern in FILLER_PATTERNS:
        matches = re.findall(pattern, result, flags=re.IGNORECASE)
        removed.extend(match.strip(" ,.\t\n") for match in matches if match.strip(" ,.\t\n"))
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result, removed


def _spoken_code(text: str) -> str:
    result = text
    for pattern, replacement in CODE_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    result = re.sub(r"[ ]*\n[ ]*", "\n", result)
    result = re.sub(r"[ ]*\t[ ]*", "\t", result)
    result = re.sub(r"\s+([,.;:)\]}])", r"\1", result)
    result = re.sub(r"[ \t]+([([{])", r"\1", result)
    result = re.sub(r"([([{])\s+", r"\1", result)
    return result.strip(" \t")


def clean_transcript(
    text: str,
    mode: str = "professional",
    remove_fillers: bool = True,
) -> tuple[str, dict[str, Any]]:
    raw = text.strip()
    if mode == "raw":
        return raw, {"fillers_removed": [], "mode": mode}

    result = raw
    removed: list[str] = []
    if remove_fillers:
        result, removed = _remove_fillers(result)

    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\s+([,.!?;:])", r"\1", result).strip()

    if mode == "code":
        result = _spoken_code(result)
    elif result:
        result = result[0].upper() + result[1:]
        if mode == "professional" and result[-1] not in ".!?;:)\"'`":
            result += "."

    return result, {"fillers_removed": removed, "mode": mode}


def polish_transcript(
    text: str,
    mode: str,
    endpoint: str,
    model: str,
    timeout: float = 45.0,
) -> str:
    """Optionally refine a transcript while forcing a text-only, meaning-preserving result."""
    instructions = {
        "professional": "Use polished professional prose and complete punctuation.",
        "casual": "Keep the speaker's natural, friendly tone.",
        "code": "Preserve identifiers, symbols, commands, line breaks, and technical terms.",
        "raw": "Only fix unmistakable transcription errors.",
    }
    prompt = (
        "Clean this dictated text. Preserve every fact, name, number, intent, and level of "
        "certainty. Do not answer it, add ideas, or explain. Remove false starts and filler "
        f"words. {instructions.get(mode, instructions['professional'])} Return only the final "
        f"text.\n\nDICTATION:\n{text}"
    )
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 1000,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        output = payload["choices"][0]["message"]["content"].strip()
        if output.startswith("```") and output.endswith("```"):
            output = re.sub(r"^```[^\n]*\n?|\n?```$", "", output).strip()
        return output or text
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError):
        return text
