import json
import logging
import re
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import delete, select

from backend.app.config import get_settings
from backend.app.database import Base, SessionLocal, engine, ensure_job_schema
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
            "name": "remoteok-jobs",
            "kind": "remote_ok",
            "url": "https://remoteok.com/api",
        },
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


def build_source_key(source_url: str, company: str, title: str) -> str:
    if source_url:
        return source_url
    return f"{company.lower()}::{title.lower()}"


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


def infer_initial_next_action(company: str, location: str, title: str, summary: str, score: float) -> str:
    lowered_title = title.lower()
    lowered_summary = summary.lower()
    lowered_company = company.lower()

    if any(term in lowered_title for term in ("product specialist", "new grad", "entry-level")):
        return "archive"
    if "unknown company" in lowered_company or location == "Unknown":
        return "research"
    if score >= 70:
        return "apply_now"
    if score >= 58 or any(term in lowered_summary for term in ("terraform", "python", "platform", "infrastructure")):
        return "resume_tailoring"
    return "research"


def build_summary(description: str, source_url: str) -> str:
    parts = []
    if description:
        parts.append(description[:220])
    if source_url:
        parts.append(f"Source: {source_url}")
    summary = " ".join(parts)
    return summary[:320] if summary else "Source discovered by live ingest."


def get_source_timeout_seconds(source_config: dict[str, Any]) -> float:
    raw_timeout = source_config.get("timeout_seconds", 20)
    try:
        parsed = float(raw_timeout)
    except (TypeError, ValueError):
        return 20.0
    return parsed if parsed > 0 else 20.0


def get_source_retry_count(source_config: dict[str, Any]) -> int:
    raw_retry = source_config.get("retry_count", 1)
    try:
        parsed = int(raw_retry)
    except (TypeError, ValueError):
        return 1
    return parsed if parsed >= 0 else 1


def get_source_retry_backoff_seconds(source_config: dict[str, Any]) -> float:
    raw_backoff = source_config.get("retry_backoff_seconds", 1)
    try:
        parsed = float(raw_backoff)
    except (TypeError, ValueError):
        return 1.0
    return parsed if parsed >= 0 else 1.0


def classify_source_error(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, HTTPError):
        return "http_error"
    if isinstance(error, URLError):
        if isinstance(error.reason, TimeoutError):
            return "timeout"
        return "network_error"
    if isinstance(error, json.JSONDecodeError):
        return "invalid_payload"
    return "unknown_error"


def fetch_json(
    url: str,
    *,
    timeout_seconds: float,
    retry_count: int,
    retry_backoff_seconds: float,
) -> dict[str, Any] | list[dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "TrashPanda/0.1 (+self-hosted job ingestion)"})
    attempts = max(1, retry_count + 1)
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.load(response)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt + 1 >= attempts:
                break
            if retry_backoff_seconds > 0:
                time.sleep(retry_backoff_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("fetch_json failed without an exception")


def iter_hn_jobs(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for hit in payload.get("hits", []):
        raw_title = compact_text(hit.get("title") or hit.get("story_title"))
        if not raw_title:
            continue
        yield hit


def iter_remoteok_jobs(payload: list[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for item in payload:
        if not isinstance(item, dict):
            continue
        if not item.get("id"):
            continue
        if not compact_text(item.get("position")):
            continue
        yield item


def ingest_remoteok_source(session: SessionLocal, source_config: dict[str, Any], ingest_config: dict[str, Any]) -> int:
    payload = fetch_json(
        source_config["url"],
        timeout_seconds=get_source_timeout_seconds(source_config),
        retry_count=get_source_retry_count(source_config),
        retry_backoff_seconds=get_source_retry_backoff_seconds(source_config),
    )
    existing_jobs = {
        job.source_key or build_source_key(job.source_url or "", job.company, job.title): job
        for job in session.query(Job).filter(Job.source == source_config["name"]).all()
    }
    seen_keys: set[str] = set()

    for item in iter_remoteok_jobs(payload):
        title = normalize_title_name(compact_text(item.get("position")))
        company = normalize_company_name(compact_text(item.get("company")))
        location = compact_text(item.get("location")) or "Remote"
        tags = " ".join(compact_text(tag) for tag in item.get("tags", []) if compact_text(tag))
        description = strip_html(item.get("description"))
        source_url = compact_text(item.get("url"))
        searchable_text = " ".join(part for part in (title, company, location, tags, description) if part)
        dedupe_key = build_source_key(source_url, company, title)

        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        summary = build_summary(" ".join(part for part in (location, tags, description) if part), source_url)
        score = compute_score(searchable_text, ingest_config["score_keywords"])
        next_action = infer_initial_next_action(company, location, title, summary, score)

        job = existing_jobs.get(dedupe_key)
        if job is None:
            job = Job(
                title=title,
                company=company,
                location=location,
                source=source_config["name"],
                source_key=dedupe_key,
                source_url=source_url or None,
                score=score,
                status="queued",
                next_action=next_action,
                tailoring_required=next_action == "resume_tailoring",
                summary=summary,
            )
        else:
            job.title = title
            job.company = company
            job.location = location
            job.source_key = dedupe_key
            job.source_url = source_url or None
            job.score = score
            job.summary = summary
            if job.status not in {"applied", "not_interested", "archived", "shortlisted"}:
                job.status = "queued"
                job.next_action = next_action
                if not job.tailored_resume_exists:
                    job.tailoring_required = next_action == "resume_tailoring"

        session.add(job)

    stale_job_ids = [
        job.id
        for key, job in existing_jobs.items()
        if key not in seen_keys and job.status in {"discovered", "queued"} and job.applied_at is None and not job.decision_reason
    ]
    if stale_job_ids:
        session.execute(delete(Job).where(Job.id.in_(stale_job_ids)))

    return len(seen_keys)


def ingest_hn_source(session: SessionLocal, source_config: dict[str, Any], ingest_config: dict[str, Any]) -> int:
    payload = fetch_json(
        source_config["url"],
        timeout_seconds=get_source_timeout_seconds(source_config),
        retry_count=get_source_retry_count(source_config),
        retry_backoff_seconds=get_source_retry_backoff_seconds(source_config),
    )
    existing_jobs = {
        job.source_key or build_source_key(job.source_url or "", job.company, job.title): job
        for job in session.query(Job).filter(Job.source == source_config["name"]).all()
    }
    seen_keys: set[str] = set()

    for hit in iter_hn_jobs(payload):
        raw_title = compact_text(hit.get("title") or hit.get("story_title"))
        description = strip_html(hit.get("story_text"))
        source_url = compact_text(hit.get("url") or hit.get("story_url") or "")
        company, title = parse_company_and_title(raw_title)
        searchable_text = " ".join(part for part in (raw_title, description) if part)
        dedupe_key = build_source_key(source_url, company, title)

        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        job = existing_jobs.get(dedupe_key)
        if job is None:
            summary = build_summary(description, source_url)
            next_action = infer_initial_next_action(company, classify_location(searchable_text, ingest_config["location_keywords"]), title, summary, compute_score(searchable_text, ingest_config["score_keywords"]))
            job = Job(
                title=title,
                company=company,
                location=classify_location(searchable_text, ingest_config["location_keywords"]),
                source=source_config["name"],
                source_key=dedupe_key,
                source_url=source_url or None,
                score=compute_score(searchable_text, ingest_config["score_keywords"]),
                status="queued",
                next_action=next_action,
                tailoring_required=next_action == "resume_tailoring",
                summary=summary,
            )
        else:
            summary = build_summary(description, source_url)
            job.title = title
            job.company = company
            job.location = classify_location(searchable_text, ingest_config["location_keywords"])
            job.source_key = dedupe_key
            job.source_url = source_url or None
            job.score = compute_score(searchable_text, ingest_config["score_keywords"])
            job.summary = summary
            if job.status not in {"applied", "not_interested", "archived", "shortlisted"}:
                next_action = infer_initial_next_action(job.company, job.location, job.title, summary, job.score)
                job.status = "queued"
                job.next_action = next_action
                if not job.tailored_resume_exists:
                    job.tailoring_required = next_action == "resume_tailoring"

        session.add(job)

    stale_job_ids = [
        job.id
        for key, job in existing_jobs.items()
        if key not in seen_keys and job.status in {"discovered", "queued"} and job.applied_at is None and not job.decision_reason
    ]
    if stale_job_ids:
        session.execute(delete(Job).where(Job.id.in_(stale_job_ids)))

    return len(seen_keys)


def write_ingest_state(summary: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def run_ingest_cycle() -> int:
    Base.metadata.create_all(bind=engine)
    ensure_job_schema()
    ensure_runtime_paths()
    ingest_config = load_ingest_config()
    source_states = {
        source_config["name"]: {
            "name": source_config["name"],
            "inserted": 0,
            "last_ingest_at": None,
            "status": "pending",
            "errors": [],
            "error_type": None,
        }
        for source_config in ingest_config.get("sources", [])
        if source_config.get("name")
    }
    errors: list[str] = []

    total_jobs = 0

    with SessionLocal() as session:
        for source_config in ingest_config.get("sources", []):
            try:
                if source_config.get("kind") == "hn_algolia":
                    inserted = ingest_hn_source(session, source_config, ingest_config)
                elif source_config.get("kind") == "remote_ok":
                    inserted = ingest_remoteok_source(session, source_config, ingest_config)
                else:
                    errors.append(f"unsupported source kind: {source_config.get('kind')}")
                    if source_config.get("name") in source_states:
                        source_states[source_config["name"]]["status"] = "unsupported"
                        source_states[source_config["name"]]["errors"].append(
                            f"unsupported source kind: {source_config.get('kind')}"
                        )
                    continue

                source_state = source_states.get(source_config["name"])
                if source_state is not None:
                    source_state["inserted"] = inserted
                    source_state["last_ingest_at"] = datetime.now(timezone.utc).isoformat()
                    source_state["status"] = "ok" if inserted > 0 else "empty"
                    source_state["error_type"] = None
                log.info("source %s inserted %s jobs", source_config["name"], inserted)
            except Exception as error:
                error_type = classify_source_error(error)
                message = f"source {source_config.get('name', 'unknown')} failed ({error_type}): {error}"
                errors.append(message)
                if source_config.get("name") in source_states:
                    source_states[source_config["name"]]["status"] = "failed"
                    source_states[source_config["name"]]["error_type"] = error_type
                    source_states[source_config["name"]]["errors"].append(f"{error_type}: {error}")
                log.warning(message)

        session.commit()

        if session.scalar(select(Job.id).where(Job.source != "demo-seed").limit(1)) is not None:
            deleted = session.execute(delete(Job).where(Job.source == "demo-seed")).rowcount or 0
            if deleted:
                session.commit()
                log.info("removed %s demo-seed jobs", deleted)

        total_jobs = session.query(Job).count()

    write_ingest_state(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": list(source_states.values()),
            "errors": errors,
            "poll_interval_seconds": ingest_config.get("poll_interval_seconds", 1800),
            "total_jobs": total_jobs,
            "feed_count": len(source_states),
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