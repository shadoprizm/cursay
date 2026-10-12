from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping


def validate_replacement(source: str, target: str) -> tuple[str, str]:
    source, target = source.strip(), target.strip()
    if not source or not target:
        raise ValueError("Enter both the mistaken phrase and its replacement.")
    if source == target:
        raise ValueError("The replacement must differ from the mistaken phrase.")
    if max(len(source), len(target)) > 200 or "\n" in source or "\n" in target:
        raise ValueError("Use a word or short phrase (up to 200 characters), without line breaks.")
    return source, target


def apply_replacements(text: str, rules: Iterable[Mapping[str, Any]]) -> str:
    """Replace whole phrases once, longest first; never cascade rules in a pass."""
    active = [rule for rule in rules if rule.get("enabled", True)]
    replacements = {str(rule["source"]).casefold(): str(rule["target"]) for rule in active}
    if not replacements:
        return text
    phrases = sorted({str(rule["source"]) for rule in active}, key=len, reverse=True)
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(phrase) for phrase in phrases) + r")(?!\w)",
        re.IGNORECASE,
    )
    return pattern.sub(lambda match: replacements.get(match[0].casefold(), match[0]), text)


def suggest_replacements(original: str, corrected: str) -> list[tuple[str, str]]:
    """Offer short word changes for explicit review, excluding insertions/deletions."""
    token_pattern = r"\w+(?:['’\-]\w+)*|[^\w\s]"
    before = list(re.finditer(token_pattern, original))
    after = list(re.finditer(token_pattern, corrected))
    matcher = SequenceMatcher(a=[m[0] for m in before], b=[m[0] for m in after], autojunk=False)
    suggestions: list[tuple[str, str]] = []
    for tag, start, end, new_start, new_end in matcher.get_opcodes():
        if tag != "replace" or end - start > 5 or new_end - new_start > 5:
            continue
        source = original[before[start].start():before[end - 1].end()]
        target = corrected[after[new_start].start():after[new_end - 1].end()]
        if not any(c.isalnum() for c in source) or not any(c.isalnum() for c in target):
            continue
        try:
            pair = validate_replacement(source, target)
        except ValueError:
            continue
        if pair not in suggestions:
            suggestions.append(pair)
    return suggestions
