import json
import logging
import re
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import delete, select

from backend.app.config import get_settings
from backend.app.database import Base, SessionLocal, engine
from backend.app.models import Job


logging.basicConfig(level=logging.INFO, format="[trashpanda-worker] %(message)s")
log = logging.getLogger(__name__)

settings = get_settings()
CONFIG_PATH = Path(settings.config_dir) / "ingest-sources.json"
STATE_PATH = Path(settings.data_dir) / "ingest-state.json"


DEFAULT_INGEST_CONFIG: dict[str, Any] = {
    "poll_interval_seconds": 1800,
    "sources": [
        {
            "name": "hn-jobs",
            "kind": "hn_algolia",
            "url": "https://hn.algolia.com/api/v1/search_by_date?tags=job&hitsPerPage=40",
        }
    ],
    "score_keywords": {
        "platform": 18,
        "infrastructure": 16,
        "site reliability": 16,
        "sre": 14,
        "devops": 14,
        "kubernetes": 12,
        "terraform": 10,
        "cloud": 10,
        "automation": 10,
        "linux": 8,
        "python": 6,
        "backend": 4,
    },
    "location_keywords": {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "onsite": "On-site",
        "on-site": "On-site",
    },
}


def ensure_runtime_paths() -> None:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.config_dir).mkdir(parents=True, exist_ok=True)


def load_ingest_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_INGEST_CONFIG

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        configured = json.load(handle)

    config = DEFAULT_INGEST_CONFIG | configured
    config["score_keywords"] = DEFAULT_INGEST_CONFIG["score_keywords"] | configured.get("score_keywords", {})
    config["location_keywords"] = DEFAULT_INGEST_CONFIG["location_keywords"] | configured.get("location_keywords", {})
    return config


def compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def strip_html(value: str | None) -> str:
    return compact_text(re.sub(r"<[^>]+>", " ", value or ""))


def parse_company_and_title(raw_title: str) -> tuple[str, str]:
    cleaned = compact_text(re.sub(r"^\[(hiring|jobs?)\]\s*", "", raw_title, flags=re.IGNORECASE))
    if not cleaned:
        return "Unknown company", "Unknown role"

    hiring_match = re.match(r"^(?P<company>.+?)\s+is hiring\s+(?P<title>.+)$", cleaned, flags=re.IGNORECASE)
    if hiring_match:
        return normalize_company_name(hiring_match.group("company")), normalize_title_name(hiring_match.group("title"))

    hiring_dash_match = re.match(r"^Hiring\s+(?P<title>.+?)\s+[\-–—]\s+(?P<company>.+)$", cleaned, flags=re.IGNORECASE)
    if hiring_dash_match:
        return normalize_company_name(hiring_dash_match.group("company")), normalize_title_name(hiring_dash_match.group("title"))

    if "|" in cleaned:
        company, title = (compact_text(part) for part in cleaned.split("|", 1))
        if company and title:
            return normalize_company_name(company), normalize_title_name(title)

    lowered = cleaned.lower()
    if " at " in lowered:
        split_at = lowered.rfind(" at ")
        title = compact_text(cleaned[:split_at])
        company = compact_text(cleaned[split_at + 4 :])
        if company and title:
            return normalize_company_name(company), normalize_title_name(title)

    for separator in (" - ", " – ", " — ", ": "):
        if separator in cleaned:
            left, right = (compact_text(part) for part in cleaned.split(separator, 1))
            if left and right and len(left.split()) <= 5:
                return normalize_company_name(left), normalize_title_name(right)

    return "Unknown company", normalize_title_name(cleaned)


def normalize_company_name(company: str) -> str:
    cleaned = compact_text(company)
    cleaned = re.sub(r"\s*\((YC|yc)\s+[A-Z0-9]+\)", "", cleaned)
    cleaned = re.sub(r"\s*\([^)]*Y\s?C[^)]*\)", "", cleaned)
    cleaned = re.sub(r"\s+Hiring$", "", cleaned, flags=re.IGNORECASE)
    return compact_text(cleaned) or "Unknown company"


def normalize_title_name(title: str) -> str:
    cleaned = compact_text(title)
    cleaned = re.sub(r"^[-–—:;,]+\s*", "", cleaned)
    cleaned = re.sub(r"^(a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\((YC|yc)\s+[A-Z0-9]+\)", "", cleaned)
    cleaned = re.sub(r"\s*\([^)]*Y\s?C[^)]*\)", "", cleaned)
    return compact_text(cleaned) or "Unknown role"


def classify_location(text: str, location_keywords: dict[str, str]) -> str:
    lowered = text.lower()
    for needle, label in location_keywords.items():
        if needle in lowered:
            return label
    return "Unknown"


def compute_score(text: str, score_keywords: dict[str, int]) -> float:
    lowered = text.lower()
    score = 45
    for needle, weight in score_keywords.items():
        if needle in lowered:
            score += weight
    return float(min(score, 98))


def build_summary(description: str, source_url: str) -> str:
    parts = []
    if description:
        parts.append(description[:220])
    if source_url:
        parts.append(f"Source: {source_url}")
    summary = " ".join(parts)
    return summary[:320] if summary else "Source discovered by live ingest."


def fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=20) as response:
        return json.load(response)


def iter_hn_jobs(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for hit in payload.get("hits", []):
        raw_title = compact_text(hit.get("title") or hit.get("story_title"))
        if not raw_title:
            continue
        yield hit


def job_exists(session: SessionLocal, source: str, company: str, title: str) -> bool:
    existing = session.scalar(
        select(Job.id)
        .where(Job.source == source)
        .where(Job.company == company)
        .where(Job.title == title)
        .limit(1)
    )
    return existing is not None


def ingest_hn_source(session: SessionLocal, source_config: dict[str, Any], ingest_config: dict[str, Any]) -> int:
    payload = fetch_json(source_config["url"])
    jobs_to_insert: list[Job] = []
    seen_keys: set[str] = set()

    for hit in iter_hn_jobs(payload):
        raw_title = compact_text(hit.get("title") or hit.get("story_title"))
        description = strip_html(hit.get("story_text"))
        source_url = compact_text(hit.get("url") or hit.get("story_url") or "")
        company, title = parse_company_and_title(raw_title)
        searchable_text = " ".join(part for part in (raw_title, description) if part)
        dedupe_key = source_url or f"{company}::{title}"

        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        jobs_to_insert.append(
            Job(
                title=title,
                company=company,
                location=classify_location(searchable_text, ingest_config["location_keywords"]),
                source=source_config["name"],
                score=compute_score(searchable_text, ingest_config["score_keywords"]),
                status="discovered",
                summary=build_summary(description, source_url),
            )
        )

    session.execute(delete(Job).where(Job.source == source_config["name"]))
    for job in jobs_to_insert:
        session.add(job)

    return len(jobs_to_insert)


def write_ingest_state(summary: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def run_ingest_cycle() -> int:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_paths()
    ingest_config = load_ingest_config()
    inserted_by_source: dict[str, int] = {}
    errors: list[str] = []

    total_jobs = 0
    unknown_company_jobs = 0
    remote_jobs = 0

    with SessionLocal() as session:
        for source_config in ingest_config.get("sources", []):
            try:
                if source_config.get("kind") != "hn_algolia":
                    errors.append(f"unsupported source kind: {source_config.get('kind')}")
                    continue

                inserted = ingest_hn_source(session, source_config, ingest_config)
                inserted_by_source[source_config["name"]] = inserted
                log.info("source %s inserted %s jobs", source_config["name"], inserted)
            except URLError as error:
                message = f"source {source_config.get('name', 'unknown')} failed: {error}"
                errors.append(message)
                log.warning(message)

        session.commit()

        if session.scalar(select(Job.id).where(Job.source != "demo-seed").limit(1)) is not None:
            deleted = session.execute(delete(Job).where(Job.source == "demo-seed")).rowcount or 0
            if deleted:
                session.commit()
                log.info("removed %s demo-seed jobs", deleted)

        total_jobs = session.query(Job).count()
        unknown_company_jobs = session.query(Job).where(Job.company == "Unknown company").count()
        remote_jobs = session.query(Job).where(Job.location == "Remote").count()

    write_ingest_state(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": inserted_by_source,
            "errors": errors,
            "poll_interval_seconds": ingest_config.get("poll_interval_seconds", 1800),
            "total_jobs": total_jobs,
            "unknown_company_jobs": unknown_company_jobs,
            "remote_jobs": remote_jobs,
        }
    )
    return int(ingest_config.get("poll_interval_seconds", 1800))


def main() -> None:
    while True:
        try:
            poll_interval = run_ingest_cycle()
            log.info("worker idle; sleeping for %s seconds", poll_interval)
            time.sleep(poll_interval)
        except Exception as error:
            log.exception("worker loop failed: %s", error)
            time.sleep(30)


if __name__ == "__main__":
    main()