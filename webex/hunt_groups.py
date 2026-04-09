"""
webex/hunt_groups.py - Webex Calling Hunt Groups API

Used primarily to locate a hunt group's phone number before
moving it to an Auto Attendant.

Endpoints:
  GET /v1/telephony/config/locations/{locationId}/huntGroups
  GET /v1/telephony/config/locations/{locationId}/huntGroups/{id}
  PUT /v1/telephony/config/locations/{locationId}/huntGroups/{id}

Required scope: spark-admin:telephony_config_read   (GET)
               spark-admin:telephony_config_write  (PUT)
"""

from __future__ import annotations
from webex.client import client

_BASE     = "/telephony/config/huntGroups"
_BASE_LOC = "/telephony/config/locations/{location_id}/huntGroups"


class HuntGroups:

    def list(self, location_id: str, name: str = None) -> list[dict]:
        """
        List all hunt groups in a location.

        Uses the org-level endpoint with locationId as a query param
        (the location-path variant returns 404 for some orgs).

        Args:
            location_id: The location's unique ID.
            name:        Optional name filter.

        Returns:
            List of hunt group dicts, each including id, name,
            phoneNumber, extension, and enabled.
        """
        params: dict = {"locationId": location_id}
        if name:
            params["name"] = name

        return client.get_all_pages(
            _BASE,
            params=params,
            items_key="huntGroups",
        )

    def get(self, location_id: str, hunt_group_id: str) -> dict:
        """Get full details for one hunt group."""
        return client.get(
            f"{_BASE}/{hunt_group_id}",
            params={"locationId": location_id},
        )

    def find_by_extension(self, location_id: str, extension: str) -> dict | None:
        """
        Find the hunt group at a given extension within a location.
        Returns the full hunt group detail dict, or None if not found.

        Used to locate the retail (4000) or priority (4001) hunt group
        and retrieve its phone number before AA creation.
        """
        all_hgs = self.list(location_id=location_id)
        for hg in all_hgs:
            if str(hg.get("extension", "")) == str(extension):
                # Fetch full details to get phoneNumber
                try:
                    return self.get(location_id, hg["id"])
                except Exception:
                    return hg
        return None

    def find_by_name_fragment(self, location_id: str, fragment: str) -> list[dict]:
        """
        Find hunt groups whose name contains a given string (case-insensitive).
        Useful for finding 'Retail' or 'Priority' hunt groups by name.
        """
        fragment_lower = fragment.lower()
        return [
            hg for hg in self.list(location_id=location_id)
            if fragment_lower in hg.get("name", "").lower()
        ]

    def update(self, location_id: str, hunt_group_id: str, name: str = None) -> dict:
        """
        Update a hunt group's name (and optionally other fields).

        Fetches the full HG config, merges provided fields, strips read-only
        fields, then PUTs it back. Mirrors the same GET-strip-PUT pattern
        used by clear_phone_number().

        Args:
            location_id:   Location unique ID.
            hunt_group_id: Hunt group unique ID.
            name:          New name for the hunt group.

        Returns:
            Empty dict on success (API returns 204).
        """
        hg = self.get(location_id, hunt_group_id)

        for field in ("id", "phoneNumber", "locationId", "locationName"):
            hg.pop(field, None)

        if name is not None:
            hg["name"] = name

        return client.put(f"{_BASE}/{hunt_group_id}", body=hg)

    def clear_phone_number(self, location_id: str, hunt_group_id: str) -> dict:
        """
        Remove the phone number from a hunt group so it can be assigned elsewhere.

        Fetches the full HG config, strips the phoneNumber field, then PUTs
        it back. The extension remains intact — only the DID is removed.

        Args:
            location_id:   Location unique ID.
            hunt_group_id: Hunt group unique ID.

        Returns:
            Empty dict on success (API returns 204).
        """
        hg = self.get(location_id, hunt_group_id)

        # Fields that must not appear in the PUT body
        for field in ("id", "phoneNumber", "locationId", "locationName"):
            hg.pop(field, None)

        # Use the org-level endpoint for PUT (same as GET) — the location-path
        # variant returns 404 on some orgs per the existing note at line 30.
        return client.put(
            f"{_BASE}/{hunt_group_id}",
            body=hg,
        )


hunt_groups = HuntGroups()
