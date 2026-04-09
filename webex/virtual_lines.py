"""
webex/virtual_lines.py - Webex Calling Virtual Lines API

Virtual lines are org-level resources filtered by locationId.
Used here to rename display names during a store rename operation.

Endpoints:
  GET /v1/telephony/config/virtualLines
  GET /v1/telephony/config/virtualLines/{virtualLineId}
  PUT /v1/telephony/config/virtualLines/{virtualLineId}

Required scopes:
  spark-admin:telephony_config_read   (GET)
  spark-admin:telephony_config_write  (PUT)
"""

from __future__ import annotations
from webex.client import client

_BASE = "/telephony/config/virtualLines"

# Fields returned by GET that must not appear in PUT bodies
_READ_ONLY = ("id", "locationId", "locationName")


class VirtualLines:

    def list(self, location_id: str) -> list[dict]:
        """
        List all virtual lines in a location.

        Uses the org-level endpoint with locationId as a query param
        (same pattern as hunt_groups.py).

        Args:
            location_id: The location's unique ID.

        Returns:
            List of virtual line dicts, each including id, displayName,
            firstName, and lastName.
        """
        return client.get_all_pages(
            _BASE,
            params={"locationId": location_id},
            items_key="virtualLines",
        )

    def get(self, virtual_line_id: str) -> dict:
        """Get full details for one virtual line."""
        return client.get(f"{_BASE}/{virtual_line_id}")

    def update(
        self,
        virtual_line_id: str,
        first_name:      str = None,
        last_name:       str = None,
        display_name:    str = None,
    ) -> dict:
        """
        Update a virtual line's name fields.

        GETs the current full record, merges only the provided fields,
        strips read-only fields, then PUTs the complete body back.

        Args:
            virtual_line_id: Virtual line unique ID.
            first_name:      New first name.
            last_name:       New last name.
            display_name:    New display name.

        Returns:
            Updated virtual line dict (or empty dict on 204).
        """
        vl = self.get(virtual_line_id)

        for field in _READ_ONLY:
            vl.pop(field, None)

        if first_name is not None:
            vl["firstName"] = first_name
        if last_name is not None:
            vl["lastName"] = last_name
        if display_name is not None:
            vl["displayName"] = display_name

        return client.put(f"{_BASE}/{virtual_line_id}", body=vl)


virtual_lines = VirtualLines()
