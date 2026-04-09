"""
webex/devices.py - Webex Devices API

Lists and retrieves device inventory including model, status,
serial number, MAC address, and assignment. Also supports
reading and updating device line/member configurations.

Endpoints:
  GET /v1/devices                                         - list devices
  GET /v1/devices/{id}                                    - get one device
  GET /v1/telephony/config/devices/{id}/members           - get line layout
  PUT /v1/telephony/config/devices/{id}/members           - update line layout

Required scope: spark:devices_read (or spark-admin:devices_read)
               spark-admin:telephony_config_read  (members GET)
               spark-admin:telephony_config_write (members PUT)
"""

from __future__ import annotations

from webex.client import client


class Devices:

    def list(
        self,
        location_id:   str  = None,
        display_name:  str  = None,
        model:         str  = None,
        serial:        str  = None,
        mac:           str  = None,
        connection_status: str = None,
        org_id:        str  = None,
        max_results:   int  = 1000,
    ) -> list[dict]:
        """
        List devices, optionally filtered by location, model, status, etc.

        Args:
            location_id:       Filter to a specific location.
            display_name:      Partial name match.
            model:             Filter by model name (e.g. "DX80").
            serial:            Filter by serial number.
            mac:               Filter by MAC address.
            connection_status: "CONNECTED", "DISCONNECTED", or "CONNECTED_WITH_ISSUES".
            org_id:            Override org ID.
            max_results:       Max records per page (up to 1000).

        Returns:
            List of device dicts.
        """
        params = {"max": max_results}
        if location_id:
            params["locationId"]       = location_id
        if display_name:
            params["displayName"]      = display_name
        if model:
            params["product"]          = model
        if serial:
            params["serial"]           = serial
        if mac:
            params["mac"]              = mac
        if connection_status:
            params["connectionStatus"] = connection_status
        if org_id:
            params["orgId"]            = org_id

        return client.get_all_pages("/devices", params=params)

    def get(self, device_id: str) -> dict:
        """Get full details for a single device."""
        return client.get(f"/devices/{device_id}")

    def summary(self, devices: list[dict]) -> dict:
        """Return counts by status and model from a device list."""
        by_status: dict[str, int] = {}
        by_model:  dict[str, int] = {}

        for d in devices:
            status = d.get("connectionStatus", "UNKNOWN")
            model  = d.get("product", d.get("model", "UNKNOWN"))
            by_status[status] = by_status.get(status, 0) + 1
            by_model[model]   = by_model.get(model, 0) + 1

        return {
            "total":     len(devices),
            "by_status": by_status,
            "by_model":  by_model,
        }

    # ── Line / member management ───────────────────────────────────────────────

    def get_members(self, device_id: str) -> list[dict]:
        """
        Get the line layout (members) of a device.

        Each entry represents one button/line on the phone and shows which
        user, workspace, or virtual line is assigned, what port number it
        occupies, and whether it is the primary line.

        Returns:
            List of member dicts. Key fields per member:
              id, firstName, lastName, type (PEOPLE/PLACE/VIRTUAL_LINE),
              extension, lineType (PRIMARY/SHARED_CALL_APPEARANCE),
              port (button number, 1-based), primaryOwner (bool).
        """
        data = client.get(
            f"/telephony/config/devices/{device_id}/members",
        )
        return data.get("members", [])

    def update_members(self, device_id: str, members: list[dict]) -> dict:
        """
        Replace the full line layout of a device.

        To remove a member, omit them from the list.
        To add a member, append a dict with at least:
          {"id": "<person/workspace/virtualLine id>", "port": <int>, "lineType": "SHARED_CALL_APPEARANCE"}

        Warning: This replaces ALL members — always fetch get_members() first
        and edit the returned list rather than building from scratch.

        Args:
            device_id: Device unique ID.
            members:   Full list of member dicts to set on the device.

        Returns:
            Empty dict on success (API returns 204).
        """
        return client.put(
            f"/telephony/config/devices/{device_id}/members",
            body={"members": members},
        )


devices = Devices()
