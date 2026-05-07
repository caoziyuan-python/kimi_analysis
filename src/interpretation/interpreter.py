from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from config.prompts import INTERPRETATION_PROMPT
from config.settings import (
    INTERPRETATIONS_PATH,
    MAX_RETRIES,
    MOONSHOT_BASE_URL,
    MOONSHOT_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from src.interpretation.grouper import Signal


FORBIDDEN_WORDS = [
    "should",
    "must",
    "obviously",
    "clearly",
    "the issue is",
    "users want",
    "users are",
    "the product needs to",
    "you should",
]

METRIC_HINTS = {
    "accuracy",
    "completion",
    "count",
    "error",
    "frequency",
    "latency",
    "modification",
    "rate",
    "ratio",
    "reprompt",
    "reset",
    "success",
}


@dataclass(frozen=True)
class Interpretation:
    signal_key: str
    comment_count: int
    representative_comments: list[str]
    how_i_interpret_this: str
    possible_internal_checks: list[str]
    boundary_note: str
    generated_at: str
    model: str
    content_hash: str


def _log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def _load_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("MOONSHOT_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOONSHOT_API_KEY is required")
    return api_key


def _content_hash(comments: list[str]) -> str:
    payload = json.dumps(comments, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_cache() -> dict[str, Any]:
    if not INTERPRETATIONS_PATH.exists() or INTERPRETATIONS_PATH.stat().st_size == 0:
        return {}

    try:
        return json.loads(INTERPRETATIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid interpretations cache: {INTERPRETATIONS_PATH}") from exc


def _write_cache(cache: dict[str, Any]) -> None:
    INTERPRETATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INTERPRETATIONS_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _extract_json_text(text: str) -> str:
    content = (text or "").strip()
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return content[start : end + 1]
    return content


def _prompt_for_signal(signal: Signal) -> str:
    comments = "\n".join(f"- {comment}" for comment in signal.representative_comments)
    return (
        f"{INTERPRETATION_PROMPT}\n\n"
        f"funnel_stage: {signal.funnel_stage}\n"
        f"scenario: {signal.scenario}\n"
        f"feedback_type: {signal.feedback_type}\n"
        f"comment_count: {signal.comment_count}\n"
        f"representative_comments:\n{comments}"
    )


def _call_interpretation_api(session: requests.Session, api_key: str, signal: Signal) -> dict[str, Any]:
    payload = {
        "model": MOONSHOT_MODEL,
        "messages": [{"role": "user", "content": _prompt_for_signal(signal)}],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.post(
                MOONSHOT_BASE_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]["content"]
            return json.loads(_extract_json_text(message))
        except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Moonshot interpretation failed for {signal.signal_key}") from exc
            time.sleep(2 ** (attempt - 1))

    raise RuntimeError(f"Moonshot interpretation failed for {signal.signal_key}")


def _coerce_interpretation(signal: Signal, payload: dict[str, Any], content_hash: str) -> Interpretation:
    how_i_interpret_this = _rewrite_forbidden_phrases(str(payload.get("how_i_interpret_this", "")).strip())
    possible_internal_checks = _coerce_internal_checks(payload.get("possible_internal_checks", []))
    boundary_note = _rewrite_forbidden_phrases(str(payload.get("boundary_note", "")).strip())

    if not how_i_interpret_this or not boundary_note or not possible_internal_checks:
        raise ValueError("interpretation is missing required content")

    interpretation = Interpretation(
        signal_key=signal.signal_key,
        comment_count=signal.comment_count,
        representative_comments=signal.representative_comments,
        how_i_interpret_this=how_i_interpret_this,
        possible_internal_checks=possible_internal_checks,
        boundary_note=boundary_note,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        model=MOONSHOT_MODEL,
        content_hash=content_hash,
    )
    _validate_interpretation_text(interpretation)
    return interpretation


def _validate_interpretation_text(interpretation: Interpretation) -> None:
    text_to_check = " ".join(
        [
            interpretation.how_i_interpret_this,
            interpretation.boundary_note,
            *interpretation.possible_internal_checks,
        ]
    ).lower()
    forbidden_hits = [word for word in FORBIDDEN_WORDS if word in text_to_check]
    if forbidden_hits:
        raise ValueError(f"interpretation contains forbidden words: {forbidden_hits}")


def _rewrite_forbidden_phrases(text: str) -> str:
    replacements = {
        "users are": "some comments may be",
        "Users are": "Some comments may be",
        "users want": "comments may point toward",
        "Users want": "Comments may point toward",
        "the issue is": "one possible reading is",
        "The issue is": "One possible reading is",
        "the product needs to": "I would check whether the product could",
        "The product needs to": "I would check whether the product could",
        "you should": "I would",
        "You should": "I would",
        "obviously": "possibly",
        "Obviously": "Possibly",
        "clearly": "possibly",
        "Clearly": "Possibly",
        "should": "could",
        "Should": "Could",
        "must": "may need to",
        "Must": "May need to",
    }
    rewritten = text
    for forbidden, replacement in replacements.items():
        rewritten = rewritten.replace(forbidden, replacement)
    return rewritten


def _coerce_internal_checks(value: Any) -> list[str]:
    if isinstance(value, list):
        return _clean_metrics([str(item) for item in value])

    if not isinstance(value, str):
        raise ValueError("possible_internal_checks must be a list or string")

    text = value.strip()
    prefix = "if I had access to internal data, I would check"
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix) :].strip(" :.")

    quoted_metrics = re.findall(r"'([^']+)'|\"([^\"]+)\"", text)
    metrics = [single or double for single, double in quoted_metrics]
    if metrics:
        cleaned_metrics = _clean_metrics(metrics)
        if cleaned_metrics:
            return cleaned_metrics

    text = text.replace(" and ", ", ")
    parts = [part.strip().strip("'\".") for part in text.split(",")]
    return _clean_metrics(parts)


def _clean_metrics(values: list[str]) -> list[str]:
    metrics: list[str] = []
    for value in values:
        metric = value.strip().strip("'\". ")
        if not metric or metric.lower() in {"and", ", and"}:
            continue
        if metric.startswith(",") or metric.endswith(","):
            continue
        lowered = metric.lower()
        if not any(hint in lowered for hint in METRIC_HINTS):
            continue
        metrics.append(metric)
    return metrics


def interpret(signal: Signal) -> Interpretation:
    content_hash = _content_hash(signal.representative_comments)
    cache = _read_cache()
    cached = cache.get(signal.signal_key)
    if isinstance(cached, dict) and cached.get("content_hash") == content_hash:
        try:
            interpretation = Interpretation(**cached)
            _validate_interpretation_text(interpretation)
            return interpretation
        except ValueError as exc:
            _log(f"cached interpretation invalid for {signal.signal_key}: {exc}")

    _log(f"generating interpretation for {signal.signal_key}")
    session = requests.Session()
    api_key = _load_api_key()
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload = _call_interpretation_api(session, api_key, signal)
            interpretation = _coerce_interpretation(signal, payload, content_hash)
            break
        except ValueError as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                raise
            _log(f"invalid interpretation for {signal.signal_key}, retrying: {exc}")
            time.sleep(2 ** (attempt - 1))
    else:
        raise RuntimeError(f"Moonshot interpretation failed for {signal.signal_key}") from last_error

    cache[signal.signal_key] = asdict(interpretation)
    _write_cache(cache)
    return interpretation
