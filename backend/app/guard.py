"""Input guard, called before the agent runs.

The interface is deliberately small: screen_request(firmware, spec) -> {allowed, score, reasons}.
Hard regex rules run first, and a trained classifier adds a score as defense in depth. The sandbox
does not rely on either: containment has to hold even when the guard misses something.
"""
from __future__ import annotations

import re
from typing import NotRequired, TypedDict

from .guard_model import load_model

BLOCK_THRESHOLD = 0.5
# A classifier hit must block on its own, however the threshold was calibrated.
MIN_CLASSIFIER_WEIGHT = 0.6
_MODEL = load_model()


class GuardVerdict(TypedDict):
    allowed: bool
    score: float
    reasons: list[str]
    classifier: NotRequired[dict]


_INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)", "Prompt injection: tells the model to ignore its instructions"),
    (r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|your)\s+(instructions|prompts?|rules)", "Prompt injection: tells the model to disregard its instructions"),
    (r"(reveal|print|show|output|leak|send)\s+(me\s+)?(your\s+|the\s+)?(system\s+prompt|api[\s_-]?key|secret|credentials?|env(ironment)?\s+var)", "Prompt injection: asks for secrets or the system prompt"),
    (r"you\s+are\s+now\s+(a|an|in)\b", "Prompt injection: tries to reassign the model's role"),
    (r"(mark|report|declare)\s+(all\s+|this\s+|every\s+)?(tests?|assertions?|scenarios?|firmware|bugs?)\s+(as\s+)?(passed|passing|fixed|verified|clean)", "Prompt injection: tries to dictate the verdict"),
    (r"</?\s*(system|assistant)\s*>|\[\[?\s*(system|inst)\s*\]?\]", "Prompt injection: fake chat-role markup"),
]

_INCLUDE_RE = re.compile(r'^\s*#\s*(?:include|include_next|import)\s*[<"]([^>"]+)[>"]', re.MULTILINE)
_INCBIN_RE = re.compile(r'\.(?:incbin|include)\s+\\?"([^"\\]+)', re.IGNORECASE)

_HOST_PATH_RE = re.compile(r"^(/|~|\.\./|[A-Za-z]:\\)|/\.\./|/(etc|proc|sys|root|home|var/run|dev)/|\.ssh|id_rsa|\.env\b|\.aws|docker\.sock")

_SUSPICIOUS_STRINGS = [
    (r"docker\.sock", "References the Docker socket"),
    (r"/proc/self/environ", "References the process environment"),
    (r"169\.254\.169\.254", "References the cloud metadata service"),
    (r"\.ssh/|id_rsa|\.aws/credentials", "References host credentials"),
]


def _weight(reasons: list[tuple[float, str]]) -> float:
    miss = 1.0
    for weight, _ in reasons:
        miss *= 1.0 - weight
    return round(1.0 - miss, 3)


def _rule_findings(firmware: str, spec: str) -> dict[str, float]:
    """Hard rules. Each finding maps a reason to its weight."""
    found: list[tuple[float, str]] = []
    combined = f"{firmware}\n{spec}"

    for pattern, reason in _INJECTION_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            found.append((0.8, reason))

    for path in _INCLUDE_RE.findall(firmware):
        if _HOST_PATH_RE.search(path.strip()):
            found.append((0.9, f"Suspicious include of a host path: {path.strip()}"))

    for path in _INCBIN_RE.findall(firmware):
        found.append((0.9, f"Assembler include of a file: {path.strip()}"))

    for pattern, reason in _SUSPICIOUS_STRINGS:
        if re.search(pattern, combined, re.IGNORECASE):
            found.append((0.5, reason))

    unique: dict[str, float] = {}
    for weight, reason in found:
        unique[reason] = max(unique.get(reason, 0.0), weight)
    return unique


def _verdict(findings: dict[str, float]) -> GuardVerdict:
    score = _weight([(w, r) for r, w in findings.items()])
    return {"allowed": score < BLOCK_THRESHOLD, "score": score, "reasons": list(findings)}


def rule_verdict(firmware: str, spec: str) -> GuardVerdict:
    """The regex rules alone, for evaluating what the classifier adds."""
    return _verdict(_rule_findings(firmware, spec))


def screen_request(firmware: str, spec: str, model=_MODEL) -> GuardVerdict:
    """Screen the upload. `spec` is the plain-English text, including pin roles."""
    findings = _rule_findings(firmware, spec)
    details: dict = {"available": False}
    if model is not None:
        score, chunk = model.score(firmware, spec)
        flagged = score >= model.threshold
        details = {"available": True, "version": model.version, "score": round(score, 4), "threshold": model.threshold, "flagged": flagged}
        if flagged:
            excerpt = " ".join(chunk.split())[:120]
            findings[f"Trained classifier ({score:.2f}) flagged: {excerpt}"] = max(score, MIN_CLASSIFIER_WEIGHT)
    verdict = _verdict(findings)
    verdict["classifier"] = details
    return verdict
