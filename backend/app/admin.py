from datetime import datetime, timezone


DELETE_ALL_JOBS_CONFIRMATION = "DeleteAllJobs"


def validate_delete_all_jobs_confirmation(value: str) -> None:
    if value.strip() != DELETE_ALL_JOBS_CONFIRMATION:
        raise ValueError("Type DeleteAllJobs exactly to clear the database")


def build_cleared_ingest_state(existing_state: dict | None = None) -> dict:
    state = existing_state or {}
    updated_at = datetime.now(timezone.utc).isoformat()
    raw_sources = state.get("sources", [])

    if isinstance(raw_sources, dict):
        sources = [
            {
                "name": name,
                "inserted": 0,
                "status": "cleared",
                "last_ingest_at": updated_at,
                "errors": [],
            }
            for name in raw_sources.keys()
        ]
    else:
        sources = [
            {
                "name": source.get("name", "unknown"),
                "inserted": 0,
                "status": "cleared",
                "last_ingest_at": updated_at,
                "errors": [],
            }
            for source in raw_sources
            if isinstance(source, dict)
        ]

    return {
        "updated_at": updated_at,
        "poll_interval_seconds": state.get("poll_interval_seconds", 1800),
        "total_jobs": 0,
        "feed_count": len(sources),
        "errors": [],
        "sources": sources,
    }