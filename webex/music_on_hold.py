"""
webex/music_on_hold.py - Webex Calling Music on Hold API

Endpoints:
  GET /v1/telephony/config/locations/{locationId}/musicOnHold
  PUT /v1/telephony/config/locations/{locationId}/musicOnHold

Required scopes:
  spark-admin:telephony_config_read   (GET)
  spark-admin:telephony_config_write  (PUT)
"""

from __future__ import annotations
from webex.client import client


class MusicOnHold:

    def get(self, location_id: str) -> dict:
        """
        Get Music on Hold settings for a location.

        Returns a dict with keys:
          callHoldEnabled  (bool)
          callParkEnabled  (bool)
          greeting         (str)  — "DEFAULT" or "CUSTOM"
          audioFile        (dict) — {name, mediaType, mediaFileType} if CUSTOM
        """
        return client.get(f"/telephony/config/locations/{location_id}/musicOnHold")

    def update(
        self,
        location_id:       str,
        call_hold_enabled: bool = None,
        call_park_enabled: bool = None,
        greeting:          str  = None,
        audio_file:        dict = None,
    ) -> dict:
        """
        Update Music on Hold settings for a location.

        Args:
            call_hold_enabled: Enable MOH for calls on hold.
            call_park_enabled: Enable MOH for parked calls.
            greeting:          "DEFAULT" or "CUSTOM".
            audio_file:        Dict with name/mediaType/mediaFileType (required if CUSTOM).
        """
        body: dict = {}
        if call_hold_enabled is not None:
            body["callHoldEnabled"] = call_hold_enabled
        if call_park_enabled is not None:
            body["callParkEnabled"] = call_park_enabled
        if greeting is not None:
            body["greeting"] = greeting
        if audio_file is not None:
            body["audioFile"] = audio_file
        return client.put(
            f"/telephony/config/locations/{location_id}/musicOnHold",
            body=body,
        )


music_on_hold = MusicOnHold()
