"""
webex/numbers.py - Webex Calling Numbers API

Provides phone number inventory, usage lookup, and bulk provisioning.

Endpoints:
  GET  /v1/telephony/config/numbers                    - list numbers in org/location
  GET  /v1/telephony/config/locations/{id}/numbers     - list numbers in a location
  POST /v1/telephony/config/locations/{id}/numbers     - add numbers to a location

Required scopes:
  spark-admin:telephony_config_read   (list/lookup)
  spark-admin:telephony_config_write  (add numbers)
"""

from __future__ import annotations

from webex.client import client


# Maps Webex owner type codes to friendly labels
OWNER_TYPE_LABELS = {
    "PEOPLE":              "User",
    "PLACE":               "Workspace",
    "AUTO_ATTENDANT":      "Auto Attendant",
    "CALL_QUEUE":          "Call Queue",
    "HUNT_GROUP":          "Hunt Group",
    "GROUP_PAGING":        "Group Paging",
    "VOICE_MESSAGING":     "Voicemail Group",
    "BROADWORKS_ANYWHERE": "BroadWorks Anywhere",
    "VIRTUAL_LINE":        "Virtual Line",
}


class Numbers:

    def list(
        self,
        location_id:       str  = None,
        phone_number:      str  = None,
        available:         bool = None,
        org_id:            str  = None,
        max_results:       int  = 1000,
    ) -> list[dict]:
        """
        List phone numbers for the org or a specific location.

        Args:
            location_id:  Filter to a specific location.
            phone_number: Filter by a specific phone number.
            available:    If True, return only unassigned numbers.
            org_id:       Override org ID.
            max_results:  Max records per page.

        Returns:
            List of phone number dicts, each with a friendly 'ownerTypeLabel'.
        """
        params: dict = {"max": max_results}
        if location_id:
            params["locationId"]   = location_id
        if phone_number:
            params["phoneNumber"]  = phone_number
        if available is not None:
            params["available"]    = str(available).lower()
        if org_id:
            params["orgId"]        = org_id

        numbers = client.get_all_pages(
            "/telephony/config/numbers",
            params=params,
            items_key="phoneNumbers",
        )

        # Attach a friendly label and resolved name for the UI
        for n in numbers:
            owner = n.get("owner", {})
            # API returns 'type' on some endpoints, 'ownerType' on others
            raw   = owner.get("type") or owner.get("ownerType", "")
            n["ownerTypeLabel"] = OWNER_TYPE_LABELS.get(raw, raw or "Unassigned")
            # Hunt groups store their name in 'lastName'; users use 'displayName'
            if raw == "HUNT_GROUP":
                n["ownerName"] = owner.get("lastName") or owner.get("displayName") or ""
            else:
                n["ownerName"] = (
                    owner.get("displayName")
                    or f"{owner.get('firstName','')} {owner.get('lastName','')}".strip()
                )

        return numbers

    def find_usage(self, phone_number: str) -> dict:
        """
        Find where a phone number is currently assigned.

        Returns a dict with:
          - found (bool)
          - number details if found
          - owner type + name
        """
        results = self.list(phone_number=phone_number)
        if not results:
            return {"found": False, "number": phone_number}

        record = results[0]
        owner  = record.get("owner", {})
        return {
            "found":          True,
            "number":         phone_number,
            "state":          record.get("state", ""),
            "location":       record.get("location", {}).get("name", ""),
            "owner_type":     record.get("ownerTypeLabel", "Unassigned"),
            "owner_name":     record.get("ownerName", ""),
            "owner_id":       owner.get("id", ""),
            "extension":      record.get("extension", ""),
            "main_number":    record.get("mainNumber", False),
        }

    def summary(self, numbers: list[dict]) -> dict:
        """Return counts by owner type from a number list."""
        by_type: dict[str, int] = {}
        for n in numbers:
            label = n.get("ownerTypeLabel", "Unassigned")
            by_type[label] = by_type.get(label, 0) + 1
        return {
            "total":         len(numbers),
            "assigned":      sum(1 for n in numbers if n.get("owner")),
            "unassigned":    sum(1 for n in numbers if not n.get("owner")),
            "by_owner_type": by_type,
        }

    def add(
        self,
        location_id:   str,
        phone_numbers: list[str],
        number_type:   str = "DID",
    ) -> None:
        """
        Add phone numbers to a location.

        Args:
            location_id:   Target location ID.
            phone_numbers: List of numbers in E.164 format (e.g. '+17705551234').
            number_type:   'DID', 'TOLLFREE', or 'MOBILE'.

        Raises:
            WebexAPIError on failure.
        """
        client.post(
            f"/telephony/config/locations/{location_id}/numbers",
            body={
                "phoneNumbers": phone_numbers,
                "numberType":   number_type,
            },
        )


numbers = Numbers()
