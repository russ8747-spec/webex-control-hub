"""
webex/auto_attendants.py - Webex Calling Auto Attendant API

Endpoints used:
  GET    /v1/telephony/config/locations/{locationId}/autoAttendants
  POST   /v1/telephony/config/locations/{locationId}/autoAttendants
  GET    /v1/telephony/config/locations/{locationId}/autoAttendants/{id}
  PUT    /v1/telephony/config/locations/{locationId}/autoAttendants/{id}
  DELETE /v1/telephony/config/locations/{locationId}/autoAttendants/{id}

Required scopes:
  spark-admin:telephony_config_read   (GET)
  spark-admin:telephony_config_write  (POST, PUT, DELETE)
"""

from __future__ import annotations
from webex.client import client

_BASE = "/telephony/config/locations/{location_id}/autoAttendants"

# ── AA type templates ──────────────────────────────────────────────────────────
# These match the exact configuration from the Auto Attendant_example.csv.
# Key 0 transfers to the corresponding hunt group extension.
AA_TEMPLATES = {
    "Retail": {
        "suffix":          "Retail AA",   # appended to location name
        "extension":       "5004",
        "transfer_ext":    "4000",         # hunt group extension — key 1 transfers here
        "language_code":   "en_us",
    },
    "Priority": {
        "suffix":          "Priority",
        "extension":       "5005",
        "transfer_ext":    "4001",         # hunt group extension — key 1 transfers here
        "language_code":   "en_us",
    },
}

# Audio greeting used for all AAs (must exist in org media library)
GREETING_FILE = "Napa Auto Attendant Generic v2.wav"
BUSINESS_SCHEDULE_NAME = "Open"

# audioFile object to include when greeting = "CUSTOM"
_GREETING_AUDIO = {
    "name":          GREETING_FILE,
    "mediaType":     "WAV",
    "mediaFileType": "ORGANIZATION",
}


def _build_menu(transfer_ext: str, greeting: str = "CUSTOM") -> dict:
    """
    Build the business-hours or after-hours menu payload.

    Matches the CSV template:
      - Greeting: CUSTOM (Napa Auto Attendant Generic v2.wav, org-level)
      - No-input: TWO_TIMES retry, 5 sec, PLAY_MESSAGE_AND_DISCONNECT
      - Key 0: TRANSFER_WITHOUT_PROMPT to the hunt group extension

    Field names match the Webex Calling API spec (confirmed against CSV export).
    """
    menu: dict = {
        "greeting":                  greeting,
        "extensionEnabled":          False,
        "noInputRepeatTimes":        2,
        "noInputGracePeriodSeconds": 5,
        "noInputAction":             "PLAY_MESSAGE_AND_DISCONNECT",
        "keyConfigurations": [
            {
                "key":         "1",
                "action":      "TRANSFER_WITHOUT_PROMPT",
                "description": "",
                "value":       transfer_ext,
            }
        ],
    }
    if greeting == "CUSTOM":
        menu["audioFile"] = _GREETING_AUDIO
    return menu


class AutoAttendants:

    def list(self, location_id: str, name: str = None) -> list[dict]:
        """List all auto attendants in a location."""
        params: dict = {}
        if name:
            params["name"] = name
        return client.get_all_pages(
            _BASE.format(location_id=location_id),
            params=params,
            items_key="autoAttendants",
        )

    def get(self, location_id: str, auto_attendant_id: str) -> dict:
        """Get full details for one auto attendant."""
        return client.get(
            f"{_BASE.format(location_id=location_id)}/{auto_attendant_id}"
        )

    def create(
        self,
        location_id:         str,
        name:                str,
        phone_number:        str  = None,
        extension:           str  = None,
        language_code:       str  = "en_us",
        time_zone:           str  = None,
        business_schedule:   str  = None,
        business_hours_menu: dict = None,
        after_hours_menu:    dict = None,
        alternate_numbers:   list = None,
        extension_dialing:   str  = None,
    ) -> dict:
        """
        Create a new auto attendant.

        Args:
            location_id:         The location's unique ID.
            name:                Display name.
            phone_number:        E.164 phone number, e.g. "+13125551234".
            extension:           Extension string, e.g. "5004".
            language_code:       Language code, e.g. "en_us".
            time_zone:           IANA timezone, e.g. "America/Chicago".
            business_schedule:   Name of the business hours schedule, e.g. "Open".
            business_hours_menu: Menu dict (use _build_menu() helper).
            after_hours_menu:    Menu dict for after hours.
            alternate_numbers:   List of dicts: [{"phoneNumber": "+1...", "ringPattern": "NORMAL"}]
            extension_dialing:   "GROUP" or "ENTERPRISE" — dialing scope (top-level AA field).

        Returns:
            Dict with the new AA's 'id'.
        """
        if not phone_number and not extension:
            raise ValueError("At least one of phone_number or extension is required.")

        body: dict = {"name": name, "languageCode": language_code}

        if phone_number:
            body["phoneNumber"] = phone_number
        if extension:
            body["extension"] = extension
        if time_zone:
            body["timeZone"] = time_zone
        if business_schedule:
            body["businessSchedule"] = business_schedule
        if business_hours_menu:
            body["businessHoursMenu"] = business_hours_menu
        if after_hours_menu:
            body["afterHoursMenu"] = after_hours_menu
        if alternate_numbers:
            body["alternateNumbers"] = alternate_numbers
        if extension_dialing:
            body["extensionDialing"] = extension_dialing

        return client.post(_BASE.format(location_id=location_id), body=body)

    def create_from_template(
        self,
        location_id:       str,
        location_name:     str,
        aa_type:           str,
        time_zone:         str,
        phone_number:      str  = None,
        schedule_ok:       bool = True,
        greeting:          str  = "CUSTOM",
        alternate_numbers: list = None,
        dry_run:           bool = False,
    ) -> dict:
        """
        Create a Retail or Priority AA using the standard template.

        Args:
            location_id:       Location unique ID.
            location_name:     Human-readable location name (e.g. "ATL123 7001123").
            aa_type:           "Retail" or "Priority".
            time_zone:         IANA timezone from the location.
            phone_number:      E.164 phone number to assign (optional — omitted when None).
            schedule_ok:       Pass False if the "Open" schedule doesn't exist at this
                               location — the businessHours field will be omitted so
                               the API doesn't reject the whole request.
            alternate_numbers: List of alternate number dicts (optional).
            dry_run:           If True, return the payload without calling the API.

        Returns:
            On dry_run=True:  the request body dict that would be sent.
            On dry_run=False: the API response dict (contains 'id').

        Raises:
            ValueError: if aa_type is not "Retail" or "Priority".
        """
        if aa_type not in AA_TEMPLATES:
            raise ValueError(f"aa_type must be one of {list(AA_TEMPLATES.keys())}")

        tmpl         = AA_TEMPLATES[aa_type]
        aa_name      = f"{location_name} {tmpl['suffix']}"
        transfer_ext = tmpl["transfer_ext"]
        menu         = _build_menu(transfer_ext, greeting=greeting)

        body: dict = {
            "name":              aa_name,
            "extension":         tmpl["extension"],
            "languageCode":      tmpl["language_code"],
            "timeZone":          time_zone,
            "extensionDialing":  "GROUP",
            "businessHoursMenu": menu,
            "afterHoursMenu":    menu,
        }

        # Only include phoneNumber when one was provided
        if phone_number:
            body["phoneNumber"] = phone_number

        # Only attach the schedule if it's confirmed to exist at this location.
        # Sending a non-existent schedule name causes a 400 from the API.
        # The correct POST body field name is "businessSchedule" (plain string).
        if schedule_ok:
            body["businessSchedule"] = BUSINESS_SCHEDULE_NAME

        if alternate_numbers:
            body["alternateNumbers"] = [
                {"phoneNumber": n["phoneNumber"], "ringPattern": n.get("ringPattern", "NORMAL")}
                for n in alternate_numbers
            ]

        if dry_run:
            return body

        return self.create(
            location_id=location_id,
            name=aa_name,
            phone_number=phone_number or None,
            extension=tmpl["extension"],
            language_code=tmpl["language_code"],
            time_zone=time_zone,
            business_schedule=BUSINESS_SCHEDULE_NAME if schedule_ok else None,
            business_hours_menu=menu,
            after_hours_menu=menu,
            alternate_numbers=alternate_numbers,
            extension_dialing="GROUP",
        )

    def update(
        self,
        location_id:         str,
        auto_attendant_id:   str,
        name:                str  = None,
        phone_number:        str  = None,
        extension:           str  = None,
        language_code:       str  = None,
        time_zone:           str  = None,
        business_schedule:   str  = None,
        business_hours_menu: dict = None,
        after_hours_menu:    dict = None,
        alternate_numbers:   list = None,
    ) -> dict:
        """
        Update an existing auto attendant.

        GETs the current full config first, then merges only the fields you
        pass, and PUTs the complete body back. This prevents partial PUTs from
        silently wiping menus, alternate numbers, or other unspecified fields.
        """
        path    = f"{_BASE.format(location_id=location_id)}/{auto_attendant_id}"
        current = self.get(location_id, auto_attendant_id)

        # Strip read-only / server-generated fields that the PUT rejects
        for field in ("id", "locationId", "locationName"):
            current.pop(field, None)

        # The GET response returns "businessSchedule"; PUT also uses "businessSchedule".
        # No renaming needed — pass it through unchanged.

        # Merge only the provided changes
        if name is not None:               current["name"]               = name
        if phone_number is not None:       current["phoneNumber"]        = phone_number
        if extension is not None:          current["extension"]          = extension
        if language_code is not None:      current["languageCode"]       = language_code
        if time_zone is not None:          current["timeZone"]           = time_zone
        if business_schedule is not None:  current["businessSchedule"]   = business_schedule
        if business_hours_menu is not None: current["businessHoursMenu"] = business_hours_menu
        if after_hours_menu is not None:   current["afterHoursMenu"]     = after_hours_menu
        if alternate_numbers is not None:  current["alternateNumbers"]   = alternate_numbers

        return client.put(path, body=current)

    def delete(self, location_id: str, auto_attendant_id: str) -> dict:
        """Delete an auto attendant."""
        path = f"{_BASE.format(location_id=location_id)}/{auto_attendant_id}"
        return client.delete(path)


auto_attendants = AutoAttendants()
