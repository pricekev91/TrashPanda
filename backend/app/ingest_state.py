from backend.app.schemas import IngestSourceResponse, IngestStateResponse


def build_ingest_state_response(state: dict) -> IngestStateResponse:
    state_updated_at = state.get("updated_at")
    raw_sources = state.get("sources", [])

    if isinstance(raw_sources, dict):
        sources = [
            IngestSourceResponse(
                name=name,
                inserted=inserted,
                status="ok",
                last_ingest_at=state_updated_at,
                errors=[],
            )
            for name, inserted in raw_sources.items()
        ]
    else:
        sources = [
            IngestSourceResponse(
                name=source.get("name", "unknown"),
                inserted=source.get("inserted", 0),
                status=source.get("status", "unknown"),
                last_ingest_at=source.get("last_ingest_at") or state_updated_at,
                errors=source.get("errors", []),
            )
            for source in raw_sources
            if isinstance(source, dict)
        ]

    return IngestStateResponse(
        updated_at=state_updated_at,
        poll_interval_seconds=state.get("poll_interval_seconds", 1800),
        total_jobs=state.get("total_jobs", 0),
        feed_count=state.get("feed_count", len(sources)),
        errors=state.get("errors", []),
        sources=sources,
    )