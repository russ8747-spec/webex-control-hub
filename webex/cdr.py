"""
modules/cdr.py - Call Detail Record (CDR) API

Two endpoints are available:

  CDR Feed   (/v1/cdr_feed)
    - Historical records from 5 minutes to 30 days ago
    - Filtered by call START time
    - Query window limited to 12 hours per request
    - Best for: one-time reports, historical analysis

  CDR Stream (/v1/cdr_stream)
    - Records available ~1 minute after a call ends
    - Filtered by database WRITE timestamp (no duplicates)
    - Best for: continuous polling / real-time monitoring

Required admin scope: spark-admin:calling_cdr_read
Required admin role:  "Webex Calling Detailed Call History API access"
"""

from __future__ import annotations

import time
import requests
from datetime import datetime, timedelta, timezone
from config import ACCESS_TOKEN
from webex.client import client as _webex_client

# CDR uses a different base URL than the rest of the Webex API
CDR_BASE_URL = "https://analytics.webexapis.com/v1"


def _iso(dt: datetime) -> str:
    """Convert a datetime to the ISO-8601 format Webex expects."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _cdr_get(path: str, params: dict, max_retries: int = 3) -> list:
    """
    Make paginated GET requests to the CDR analytics host.
    Automatically retries on 429 rate-limit responses, waiting
    the number of seconds specified in the Retry-After header.
    """
    # Always read the live token from the shared client session so that
    # token updates via the Settings page are reflected in CDR requests.
    live_token = _webex_client.session.headers.get(
        "Authorization", f"Bearer {ACCESS_TOKEN}"
    )
    headers = {
        "Authorization": live_token,
        "Accept": "application/json",
    }
    url = f"{CDR_BASE_URL}/{path.lstrip('/')}"
    all_items = []

    while url:
        for attempt in range(1, max_retries + 1):
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 429:
                # Honor Retry-After header, but always wait at least 60 seconds
                retry_after = max(60, int(response.headers.get("Retry-After", 60)))
                print(f"  Rate limited. Waiting {retry_after}s before retry "
                      f"(attempt {attempt}/{max_retries})...")
                time.sleep(retry_after)
                continue  # retry

            try:
                response.raise_for_status()
            except requests.HTTPError:
                try:
                    detail = response.json()
                    msg = detail.get("message", response.text)
                    errors = detail.get("errors", [])
                    description = errors[0].get("description", "") if errors else ""
                    full_msg = f"{msg}" + (f" — {description}" if description else "")
                except ValueError:
                    full_msg = response.text
                raise requests.HTTPError(
                    f"CDR API error {response.status_code}: {full_msg}",
                    response=response,
                ) from None

            break  # success — exit retry loop
        else:
            raise requests.HTTPError(
                f"CDR API still rate-limited after {max_retries} retries.",
                response=response,
            )

        data = response.json()
        all_items.extend(data.get("items", []))

        # Follow pagination
        params = {}
        link = response.headers.get("Link", "")
        url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")

    return all_items


class CDR:
    """
    Methods for retrieving Webex Calling call detail records.
    """

    def get_feed(
        self,
        start_time: datetime,
        end_time: datetime,
        locations: list[str] = None,
        max_records: int = 500,
    ) -> list[dict]:
        """
        Fetch historical CDR records using the CDR Feed endpoint.

        Automatically splits windows larger than 12 hours into multiple
        sequential requests (the API enforces a 12-hour maximum per request).

        Args:
            start_time:  Start of the query window (call start time).
            end_time:    End of the query window. Must be >5 min in the past.
            locations:   Optional list of location IDs to filter by.
            max_records: Records per page (500–5000). Defaults to 500.

        Returns:
            List of CDR record dicts across all chunks.
        """
        CHUNK = timedelta(hours=12)
        all_records = []
        chunk_start = start_time

        while chunk_start < end_time:
            chunk_end = min(chunk_start + CHUNK, end_time)
            params = {
                "startTime": _iso(chunk_start),
                "endTime": _iso(chunk_end),
                "max": max_records,
            }
            if locations:
                params["locations"] = ",".join(locations)

            all_records.extend(_cdr_get("/cdr_feed", params=params))
            chunk_start = chunk_end

        return all_records

    def get_stream(
        self,
        start_time: datetime,
        end_time: datetime,
        locations: list[str] = None,
        max_records: int = 500,
    ) -> list[dict]:
        """
        Fetch near-real-time CDR records using the CDR Stream endpoint.

        Unlike CDR Feed, timestamps here refer to when the record was
        WRITTEN to the database — not when the call started. This makes
        it reliable for continuous polling without duplicates.

        Args:
            start_time:  Start of the query window (write timestamp).
            end_time:    End of the query window.
            locations:   Optional list of location IDs to filter by.
            max_records: Records per page (500–5000). Defaults to 500.

        Returns:
            List of CDR record dicts.
        """
        params = {
            "startTime": _iso(start_time),
            "endTime": _iso(end_time),
            "max": max_records,
        }
        if locations:
            params["locations"] = ",".join(locations)

        return _cdr_get("/cdr_stream", params=params)

    def summarize(self, records: list[dict]) -> dict:
        """
        Produce a simple summary from a list of CDR records.

        Returns a dict with:
          - total_calls
          - answered_calls
          - unanswered_calls
          - total_duration_seconds
          - average_duration_seconds
          - by_direction  (INBOUND / OUTBOUND counts)
          - by_call_type  (counts by call type)
        """
        total = len(records)
        answered = sum(1 for r in records if r.get("answered"))
        durations = [
            int(r.get("duration", 0))
            for r in records
            if r.get("answered")
        ]
        total_duration = sum(durations)
        avg_duration = total_duration // len(durations) if durations else 0

        by_direction: dict[str, int] = {}
        by_call_type: dict[str, int] = {}
        for r in records:
            direction = r.get("direction", "UNKNOWN")
            call_type = r.get("callType", "UNKNOWN")
            by_direction[direction] = by_direction.get(direction, 0) + 1
            by_call_type[call_type] = by_call_type.get(call_type, 0) + 1

        return {
            "total_calls": total,
            "answered_calls": answered,
            "unanswered_calls": total - answered,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": avg_duration,
            "by_direction": by_direction,
            "by_call_type": by_call_type,
        }


# Module-level singleton — import and use directly
cdr = CDR()
