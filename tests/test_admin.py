import unittest

from backend.app.admin import (
    DELETE_ALL_JOBS_CONFIRMATION,
    build_cleared_ingest_state,
    validate_delete_all_jobs_confirmation,
)


class DeleteAllJobsAdminTests(unittest.TestCase):
    def test_rejects_incorrect_confirmation(self) -> None:
        with self.assertRaises(ValueError):
            validate_delete_all_jobs_confirmation("deletealljobs")

    def test_accepts_exact_confirmation(self) -> None:
        validate_delete_all_jobs_confirmation(DELETE_ALL_JOBS_CONFIRMATION)

    def test_clears_legacy_ingest_state(self) -> None:
        cleared = build_cleared_ingest_state(
            {
                "poll_interval_seconds": 900,
                "total_jobs": 40,
                "feed_count": 2,
                "errors": ["old"],
                "sources": {"remoteok-jobs": 24, "hn-jobs": 16},
            }
        )

        self.assertEqual(cleared["total_jobs"], 0)
        self.assertEqual(cleared["feed_count"], 2)
        self.assertEqual(cleared["errors"], [])
        self.assertEqual([source["status"] for source in cleared["sources"]], ["cleared", "cleared"])
        self.assertEqual([source["inserted"] for source in cleared["sources"]], [0, 0])

    def test_clears_structured_ingest_state(self) -> None:
        cleared = build_cleared_ingest_state(
            {
                "sources": [
                    {"name": "remoteok-jobs", "inserted": 12, "status": "ok", "errors": []},
                    {"name": "hn-jobs", "inserted": 3, "status": "failed", "errors": ["timeout"]},
                ]
            }
        )

        self.assertEqual(cleared["feed_count"], 2)
        self.assertEqual(cleared["sources"][0]["name"], "remoteok-jobs")
        self.assertEqual(cleared["sources"][1]["name"], "hn-jobs")
        self.assertTrue(all(source["status"] == "cleared" for source in cleared["sources"]))
        self.assertTrue(all(source["errors"] == [] for source in cleared["sources"]))


if __name__ == "__main__":
    unittest.main()