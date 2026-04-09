"""
modules/locations.py - Webex Locations API

Locations are physical sites (offices, branches, etc.) that group
Webex Calling users, phone numbers, and features together in
Control Hub.

Endpoints used:
  GET    /v1/locations              - list all locations
  POST   /v1/locations              - create a location
  GET    /v1/locations/{id}         - get one location
  PUT    /v1/locations/{id}         - update a location

Required admin scopes:
  spark-admin:locations_read   (GET)
  spark-admin:locations_write  (POST, PUT)
"""

from __future__ import annotations

from webex.client import client


class Locations:
    """
    Methods for managing Webex Control Hub locations.
    """

    def list(self, name: str = None, org_id: str = None) -> list[dict]:
        """
        List all locations in your organization.

        Args:
            name:   Optional filter — return only locations whose name
                    contains this string (case-insensitive).
            org_id: Optional org ID override.

        Returns:
            List of location dicts.

        Example:
            all_locations = locations.list()
            ny_locations  = locations.list(name="New York")
        """
        params = {}
        if name:
            params["name"] = name
        if org_id:
            params["orgId"] = org_id

        return client.get_all_pages("/locations", params=params)

    def get(self, location_id: str, org_id: str = None) -> dict:
        """
        Get details for a single location.

        Args:
            location_id: The location's unique ID.
            org_id:      Optional org ID override.

        Returns:
            Location dict.
        """
        params = {}
        if org_id:
            params["orgId"] = org_id
        return client.get(f"/locations/{location_id}", params=params)

    def create(
        self,
        name: str,
        time_zone: str,
        preferred_language: str,
        address: dict,
        org_id: str = None,
    ) -> dict:
        """
        Create a new location.

        Args:
            name:               Display name for the location.
            time_zone:          IANA timezone string, e.g. "America/New_York".
            preferred_language: Language code, e.g. "en_us".
            address:            Dict with keys:
                                  address1   (required) street address
                                  address2   (optional) suite/floor
                                  city       (required)
                                  state      (required, 2-letter for US)
                                  postalCode (required)
                                  country    (required, 2-letter ISO)
            org_id:             Optional org ID override.

        Returns:
            Dict containing the new location's 'id'.

        Example:
            result = locations.create(
                name="Chicago HQ",
                time_zone="America/Chicago",
                preferred_language="en_us",
                address={
                    "address1": "123 Main St",
                    "city": "Chicago",
                    "state": "IL",
                    "postalCode": "60601",
                    "country": "US",
                },
            )
            print("Created location ID:", result["id"])
        """
        body = {
            "name": name,
            "timeZone": time_zone,
            "preferredLanguage": preferred_language,
            "address": address,
        }
        if org_id:
            body["orgId"] = org_id

        return client.post("/locations", body=body)

    def update(
        self,
        location_id: str,
        name: str = None,
        time_zone: str = None,
        preferred_language: str = None,
        address: dict = None,
        org_id: str = None,
    ) -> dict:
        """
        Update an existing location. Only provide the fields you want to change.

        Args:
            location_id:        The location's unique ID.
            name:               New display name (optional).
            time_zone:          New timezone (optional).
            preferred_language: New language code (optional).
            address:            New address dict (optional).
            org_id:             Optional org ID override.

        Returns:
            Empty dict on success (Webex returns 204 No Content).
        """
        body = {}
        if name is not None:
            body["name"] = name
        if time_zone is not None:
            body["timeZone"] = time_zone
        if preferred_language is not None:
            body["preferredLanguage"] = preferred_language
        if address is not None:
            body["address"] = address
        if org_id is not None:
            body["orgId"] = org_id

        return client.put(f"/locations/{location_id}", body=body)


# Module-level singleton
locations = Locations()
