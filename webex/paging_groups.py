"""
webex/paging_groups.py - Webex Calling Paging Groups API

Used here to rename paging groups during a store rename operation.

Endpoints:
  GET /v1/telephony/config/locations/{locationId}/paging
  GET /v1/telephony/config/locations/{locationId}/paging/{pagingId}
  PUT /v1/telephony/config/locations/{locationId}/paging/{pagingId}

Required scopes:
  spark-admin:telephony_config_read   (GET)
  spark-admin:telephony_config_write  (PUT)
"""

from __future__ import annotations
from webex.client import client

_BASE = "/telephony/config/locations/{location_id}/paging"

# Fields returned by GET that must not appear in PUT bodies
_READ_ONLY = ("id", "locationId", "locationName")


class PagingGroups:

    def list(self, location_id: str) -> list[dict]:
        """
        List all paging groups in a location.

        Args:
            location_id: The location's unique ID.

        Returns:
            List of paging group dicts, each including id and name.
        """
        return client.get_all_pages(
            _BASE.format(location_id=location_id),
            items_key="locationPaging",
        )

    def get(self, location_id: str, paging_id: str) -> dict:
        """Get full details for one paging group."""
        return client.get(
            f"{_BASE.format(location_id=location_id)}/{paging_id}"
        )

    def update(
        self,
        location_id: str,
        paging_id:   str,
        name:        str = None,
    ) -> dict:
        """
        Update a paging group's name.

        GETs the current full record, merges only the provided fields,
        strips read-only fields, then PUTs the complete body back.

        Args:
            location_id: Location unique ID.
            paging_id:   Paging group unique ID.
            name:        New name for the paging group.

        Returns:
            Updated paging group dict (or empty dict on 204).
        """
        pg = self.get(location_id, paging_id)

        for field in _READ_ONLY:
            pg.pop(field, None)

        if name is not None:
            pg["name"] = name

        return client.put(
            f"{_BASE.format(location_id=location_id)}/{paging_id}",
            body=pg,
        )


paging_groups = PagingGroups()
