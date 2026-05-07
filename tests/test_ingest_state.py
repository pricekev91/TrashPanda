import unittest

from backend.app.ingest_state import build_ingest_state_response


class BuildIngestStateResponseTests(unittest.TestCase):
    def test_normalizes_legacy_source_map(self) -> None:
        response = build_ingest_state_response(
            {
                "updated_at": "2026-05-07T14:00:00+00:00",
                "poll_interval_seconds": 1800,
                "total_jobs": 12,
                "feed_count": 1,
                "errors": [],
                "sources": {"remoteok-jobs": 7},
            }
        )

        self.assertEqual(response.feed_count, 1)
        self.assertEqual(len(response.sources), 1)
        self.assertEqual(response.sources[0].name, "remoteok-jobs")
        self.assertEqual(response.sources[0].inserted, 7)
        self.assertEqual(response.sources[0].status, "ok")
        self.assertEqual(response.sources[0].errors, [])

    def test_preserves_structured_source_health(self) -> None:
        response = build_ingest_state_response(
            {
                "updated_at": "2026-05-07T14:05:00+00:00",
                "poll_interval_seconds": 1800,
                "total_jobs": 20,
                "feed_count": 2,
                "errors": ["source hn-jobs failed: timeout"],
                "sources": [
                    {
                        "name": "remoteok-jobs",
                        "inserted": 8,
                        "status": "ok",
                        "last_ingest_at": "2026-05-07T14:05:00+00:00",
                        "errors": [],
                    },
                    {
                        "name": "hn-jobs",
                        "inserted": 0,
                        "status": "failed",
                        "last_ingest_at": None,
                        "errors": ["timeout"],
                    },
                ],
            }
        )

        self.assertEqual(response.feed_count, 2)
        self.assertEqual(response.errors, ["source hn-jobs failed: timeout"])
        self.assertEqual(response.sources[1].name, "hn-jobs")
        self.assertEqual(response.sources[1].inserted, 0)
        self.assertEqual(response.sources[1].status, "failed")
        self.assertEqual(response.sources[1].errors, ["timeout"])
        self.assertEqual(response.sources[1].last_ingest_at.isoformat(), "2026-05-07T14:05:00+00:00")


if __name__ == "__main__":
    unittest.main()