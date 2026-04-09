"""
webex/schedules.py - Webex Calling Location Schedules API

Schedules are required when creating Auto Attendants.
This module verifies that the "Open" business hours schedule
exists at a location before attempting AA creation, and can
create it if missing.

Endpoints:
  GET    /v1/telephony/config/locations/{locationId}/schedules
  GET    /v1/telephony/config/locations/{locationId}/schedules/{type}/{id}
  POST   /v1/telephony/config/locations/{locationId}/schedules

Required scope: spark-admin:telephony_config_read   (GET)
               spark-admin:telephony_config_write  (POST)
"""

from __future__ import annotations
import datetime
from webex.client import client

_BASE = "/telephony/config/locations/{location_id}/schedules"


class Schedules:

    def list(self, location_id: str) -> list[dict]:
        """
        List all schedules (business hours + holidays) for a location.

        Returns:
            List of schedule dicts with id, name, and type
            (BUSINESS_HOURS or HOLIDAY).
        """
        return client.get_all_pages(
            _BASE.format(location_id=location_id),
            items_key="schedules",
        )

    def find_by_name(self, location_id: str, name: str) -> dict | None:
        """
        Find a schedule by exact name (case-insensitive).
        Returns the schedule dict or None if not found.

        Example:
            schedule = schedules.find_by_name(location_id, "Open")
        """
        name_lower = name.lower()
        for s in self.list(location_id=location_id):
            if s.get("name", "").lower() == name_lower:
                return s
        return None

    def business_hours(self, location_id: str) -> list[dict]:
        """Return only business-hours schedules for a location."""
        return [
            s for s in self.list(location_id=location_id)
            if s.get("type", "").upper() == "BUSINESS_HOURS"
        ]

    def holidays(self, location_id: str) -> list[dict]:
        """Return only holiday schedules for a location."""
        return [
            s for s in self.list(location_id=location_id)
            if s.get("type") == "HOLIDAY"
        ]

    def create_business_hours(
        self,
        location_id: str,
        name:        str = "Open",
        start_time:  str = "07:30",
        end_time:    str = "18:00",
    ) -> dict:
        """
        Create a business hours schedule at a location.

        Defaults to a standard Mon–Fri 7:30am–6:00pm "Open" schedule,
        which is required before creating Auto Attendants.

        Args:
            location_id: Location unique ID.
            name:        Schedule name (default: "Open").
            start_time:  HH:MM start (default: "07:30").
            end_time:    HH:MM end (default: "18:00").

        Returns:
            Dict with the new schedule's 'id'.
        """
        # The Webex API requires one event per day.  Each event uses a nested
        # recurrence.recurWeekly object with boolean day flags — NOT the flat
        # recurrenceType / recurrenceByWeekDay fields, which are invalid.
        # startDate for each event is the actual calendar date of that weekday
        # in the current ISO week.
        today  = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())

        _DAYS = [
            ("Monday",    0, {"monday": True,  "tuesday": False, "wednesday": False, "thursday": False, "friday": False, "saturday": False, "sunday": False}),
            ("Tuesday",   1, {"monday": False, "tuesday": True,  "wednesday": False, "thursday": False, "friday": False, "saturday": False, "sunday": False}),
            ("Wednesday", 2, {"monday": False, "tuesday": False, "wednesday": True,  "thursday": False, "friday": False, "saturday": False, "sunday": False}),
            ("Thursday",  3, {"monday": False, "tuesday": False, "wednesday": False, "thursday": True,  "friday": False, "saturday": False, "sunday": False}),
            ("Friday",    4, {"monday": False, "tuesday": False, "wednesday": False, "thursday": False, "friday": True,  "saturday": False, "sunday": False}),
        ]

        events = [
            {
                "name":          day_name,
                "startDate":     (monday + datetime.timedelta(days=offset)).strftime("%Y-%m-%d"),
                "endDate":       (monday + datetime.timedelta(days=offset)).strftime("%Y-%m-%d"),
                "startTime":     start_time,
                "endTime":       end_time,
                "allDayEnabled": False,
                "recurrence": {
                    "recurWeekly": day_flags,
                },
            }
            for day_name, offset, day_flags in _DAYS
        ]

        body = {
            "name":   name,
            "type":   "businessHours",
            "events": events,
        }
        return client.post(_BASE.format(location_id=location_id), body=body)


schedules = Schedules()
