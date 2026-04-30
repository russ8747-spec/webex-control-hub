"""
webex/announcements.py - Webex Calling org-level audio announcements

Endpoint:
  GET /v1/telephony/config/announcements

Required scope: spark-admin:telephony_config_read
"""

from __future__ import annotations
from webex.client import client


class Announcements:

    def list(self) -> list[dict]:
        """
        List all org-level audio announcements (WAV files uploaded to the
        org media library). These are the files available for AA greetings
        with mediaFileType = ORGANIZATION.

        Returns list of dicts with keys: id, name, mediaType, mediaFileType
        """
        return client.get_all_pages(
            "/telephony/config/announcements",
            items_key="announcements",
        )


announcements = Announcements()
