"""
Placeholder tests for TrashPandaOmega.

Run with: pytest tests/
"""

import asyncio

import pytest

# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_placeholder() -> None:
    """Placeholder test — ensures the test runner is wired up correctly."""
    assert True


@pytest.mark.asyncio
async def test_async_placeholder() -> None:
    """Placeholder async test — confirms pytest-asyncio integration."""
    await asyncio.sleep(0)
    assert True


# ---------------------------------------------------------------------------
# TODO: Scraping engine tests
# ---------------------------------------------------------------------------
# def test_scraping_engine_fetch():
#     ...

# ---------------------------------------------------------------------------
# TODO: Job scheduler tests
# ---------------------------------------------------------------------------
# def test_job_scheduler_registers_job():
#     ...

# ---------------------------------------------------------------------------
# TODO: Pipeline orchestrator tests
# ---------------------------------------------------------------------------
# def test_pipeline_runs_end_to_end():
#     ...
