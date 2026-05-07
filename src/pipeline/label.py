from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

from config.prompts import LABELING_PROMPT, LABELING_SYSTEM_PROMPT
from config.settings import (
    MAX_CONTENT_LENGTH,
    MAX_RETRIES,
    MOONSHOT_BASE_URL,
    MOONSHOT_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from src.schemas import LABELED_COLUMNS, validate_labeled_df


LABEL_FIELDS = ["sentiment", "funnel_stage", "scenario", "feedback_type", "confidence"]


def _log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def _load_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("MOONSHOT_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOONSHOT_API_KEY is required")
    return api_key


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


def _normalize_labels(parsed: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for field in LABEL_FIELDS:
        value = parsed.get(field, "")
        labels[field] = str(value).strip() if value is not None else ""
    return labels


def _call_label_api(session: requests.Session, api_key: str, content: str) -> dict[str, str]:
    payload = {
        "model": MOONSHOT_MODEL,
        "messages": [
            {"role": "system", "content": LABELING_SYSTEM_PROMPT},
            {"role": "user", "content": LABELING_PROMPT.format(content=content[:MAX_CONTENT_LENGTH])},
        ],
        "temperature": 0.1,
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
            return _normalize_labels(json.loads(_extract_json_text(message)))
        except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError("Moonshot labeling failed after retries") from exc
            retry_after = _retry_after_seconds(exc)
            if retry_after is not None:
                sleep_seconds = retry_after
            elif _is_rate_limited(exc):
                sleep_seconds = 15 * attempt
            else:
                sleep_seconds = 2 ** (attempt - 1)
            _log(f"label API retry {attempt}/{MAX_RETRIES} after {sleep_seconds}s")
            time.sleep(sleep_seconds)

    raise RuntimeError("Moonshot labeling failed")


def _is_rate_limited(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 429


def _retry_after_seconds(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None

    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None

    try:
        return max(1, int(float(retry_after)))
    except ValueError:
        return None


def _stable_id(row: pd.Series) -> str:
    url = str(row.get("url") or "").strip()
    content = str(row.get("content") or "").strip()
    digest = hashlib.sha256(f"{url}|{content}".encode("utf-8")).hexdigest()
    return digest[:24]


def _first_present(row: pd.Series, columns: list[str], default: str = "") -> str:
    for column in columns:
        value = row.get(column, "")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return default


def _base_labeled_row(row: pd.Series) -> dict[str, str]:
    platform = _first_present(row, ["platform", "source"], "reddit")
    if platform == "xhs":
        platform = "xiaohongshu"

    return {
        "id": _first_present(row, ["id"], _stable_id(row)),
        "platform": platform,
        "url": _first_present(row, ["url"]),
        "author": _first_present(row, ["author"]),
        "content": _first_present(row, ["content"]),
        "created_at": _first_present(row, ["created_at", "answer_created_time"]),
        "collected_at": _first_present(row, ["collected_at", "crawl_time"], datetime.now(timezone.utc).isoformat()),
        "source_dataset": _first_present(row, ["source_dataset"], "monitoring"),
    }


def label(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    if cleaned_df.empty:
        return pd.DataFrame(columns=LABELED_COLUMNS)

    api_key = _load_api_key()
    session = requests.Session()
    rows: list[dict[str, str]] = []

    for index, row in cleaned_df.iterrows():
        base_row = _base_labeled_row(row)
        try:
            labels = _call_label_api(session, api_key, base_row["content"])
        except RuntimeError as exc:
            _log(f"skipped row after labeling failure id={base_row.get('id', '')}: {exc}")
            time.sleep(10)
            continue

        candidate = {**base_row, **labels}
        candidate_df = pd.DataFrame([candidate], columns=LABELED_COLUMNS)
        if validate_labeled_df(candidate_df):
            rows.append(candidate)
        else:
            _log(f"dropped invalid labeled row id={candidate.get('id', '')}")

        if (index + 1) % 50 == 0:
            _log(f"labeled {index + 1} rows")
        time.sleep(0.5)

    return pd.DataFrame(rows, columns=LABELED_COLUMNS)
