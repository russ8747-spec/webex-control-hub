"""
webex/people.py - Webex People API

Used for listing and updating people (users) within a location,
primarily to rename display names and email addresses during a
store rename operation.

Endpoints:
  GET /v1/people                 (org-level, filter by locationId)
  GET /v1/people/{personId}
  PUT /v1/people/{personId}

Required scopes:
  spark-admin:people_read    (GET)
  spark-admin:people_write   (PUT)
"""

from __future__ import annotations
from webex.client import client

# Fields returned by GET that must not appear in PUT bodies
_READ_ONLY = (
    "id", "orgId", "created", "lastModified", "lastActivity",
    "status", "invitePending", "loginEnabled", "type",
)


class People:

    def list(self, location_id: str) -> list[dict]:
        """
        List all people in a location.

        Args:
            location_id: The location's unique ID.

        Returns:
            List of person dicts, each including id, displayName,
            firstName, lastName, and emails.
        """
        return client.get_all_pages(
            "/people",
            params={"locationId": location_id},
            items_key="items",
        )

    def get(self, person_id: str) -> dict:
        """Get full details for one person."""
        return client.get(f"/people/{person_id}")

    def update(
        self,
        person_id:         str,
        display_name:      str  = None,
        first_name:        str  = None,
        last_name:         str  = None,
        emails:            list = None,
        email_replacements: dict = None,
    ) -> dict:
        """
        Update a person's display name, first/last name, or emails.

        GETs the current full record, merges only the provided fields,
        strips read-only fields, then PUTs the complete body back.

        Args:
            person_id:          Person unique ID.
            display_name:       New display name.
            first_name:         New first name.
            last_name:          New last name.
            emails:             Replacement email list (replaces existing).
            email_replacements: Dict mapping old email → new email.
                                Applied to the existing email list;
                                unmatched addresses are left unchanged.

        Returns:
            Updated person dict.
        """
        person = self.get(person_id)

        for field in _READ_ONLY:
            person.pop(field, None)

        if display_name is not None:
            person["displayName"] = display_name
        if first_name is not None:
            person["firstName"] = first_name
        if last_name is not None:
            person["lastName"] = last_name
        if emails is not None:
            person["emails"] = emails
        if email_replacements:
            person["emails"] = [
                email_replacements.get(e, e) for e in person.get("emails", [])
            ]

        return client.put(f"/people/{person_id}", body=person)


people = People()
