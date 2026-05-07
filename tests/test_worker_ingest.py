import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from workers.app.main import (
    classify_source_error,
    fetch_json,
    get_source_retry_backoff_seconds,
    get_source_retry_count,
    get_source_timeout_seconds,
)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class WorkerIngestConfigTests(unittest.TestCase):
    def test_timeout_parsing_defaults_for_invalid_values(self):
        self.assertEqual(get_source_timeout_seconds({}), 20.0)
        self.assertEqual(get_source_timeout_seconds({"timeout_seconds": "abc"}), 20.0)
        self.assertEqual(get_source_timeout_seconds({"timeout_seconds": 0}), 20.0)
        self.assertEqual(get_source_timeout_seconds({"timeout_seconds": 12}), 12.0)

    def test_retry_parsing_defaults_for_invalid_values(self):
        self.assertEqual(get_source_retry_count({}), 1)
        self.assertEqual(get_source_retry_count({"retry_count": "bad"}), 1)
        self.assertEqual(get_source_retry_count({"retry_count": -1}), 1)
        self.assertEqual(get_source_retry_count({"retry_count": 3}), 3)

    def test_backoff_parsing_defaults_for_invalid_values(self):
        self.assertEqual(get_source_retry_backoff_seconds({}), 1.0)
        self.assertEqual(get_source_retry_backoff_seconds({"retry_backoff_seconds": "bad"}), 1.0)
        self.assertEqual(get_source_retry_backoff_seconds({"retry_backoff_seconds": -1}), 1.0)
        self.assertEqual(get_source_retry_backoff_seconds({"retry_backoff_seconds": 0.5}), 0.5)


class WorkerFetchTests(unittest.TestCase):
    def test_fetch_json_retries_and_succeeds(self):
        payload = {"ok": True}
        responses = [
            URLError(TimeoutError("timed out")),
            _FakeResponse(json.dumps(payload).encode("utf-8")),
        ]

        with patch("workers.app.main.urlopen", side_effect=responses) as mock_urlopen, patch(
            "workers.app.main.time.sleep", return_value=None
        ):
            data = fetch_json(
                "https://example.test/feed.json",
                timeout_seconds=3,
                retry_count=1,
                retry_backoff_seconds=0,
            )

        self.assertEqual(data, payload)
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_fetch_json_raises_after_exhausting_retries(self):
        with patch("workers.app.main.urlopen", side_effect=URLError("network down")), patch(
            "workers.app.main.time.sleep", return_value=None
        ):
            with self.assertRaises(URLError):
                fetch_json(
                    "https://example.test/feed.json",
                    timeout_seconds=3,
                    retry_count=1,
                    retry_backoff_seconds=0,
                )


class WorkerErrorClassificationTests(unittest.TestCase):
    def test_error_classification(self):
        self.assertEqual(classify_source_error(TimeoutError("timeout")), "timeout")
        self.assertEqual(classify_source_error(URLError(TimeoutError("timeout"))), "timeout")
        self.assertEqual(classify_source_error(URLError("network down")), "network_error")

        http_error = HTTPError("https://example.test", 500, "boom", hdrs=None, fp=None)
        self.assertEqual(classify_source_error(http_error), "http_error")

        decode_error = json.JSONDecodeError("bad json", "x", 0)
        self.assertEqual(classify_source_error(decode_error), "invalid_payload")

        self.assertEqual(classify_source_error(RuntimeError("other")), "unknown_error")


if __name__ == "__main__":
    unittest.main()
