"""
webex/auto_attendants.py - Webex Calling Auto Attendant API

Endpoints used:
  GET    /v1/telephony/config/autoAttendants               - list (org-level, locationId param)
  GET    /v1/telephony/config/autoAttendants/{id}          - get details
  POST   /v1/telephony/config/locations/{locationId}/autoAttendants
  PUT    /v1/telephony/config/locations/{locationId}/autoAttendants/{id}
  DELETE /v1/telephony/config/locations/{locationId}/autoAttendants/{id}

Required scopes:
  spark-admin:telephony_config_read   (GET)
  spark-admin:telephony_config_write  (POST, PUT, DELETE)
"""

from __future__ import annotations
from webex.client import client

_BASE     = "/telephony/config/autoAttendants"
_BASE_LOC = "/telephony/config/locations/{location_id}/autoAttendants"

# ── AA type templates ──────────────────────────────────────────────────────────
AA_TEMPLATES = {
    "Retail": {
        "suffix":          "Retail AA",
        "extension":       "5004",
        "transfer_ext":    "4000",
        "language_code":   "en_us",
    },
    "Priority": {
        "suffix":          "Priority AA",
        "extension":       "5005",
        "transfer_ext":    "4001",
        "language_code":   "en_us",
    },
}

BUSINESS_SCHEDULE_NAME = "Open"


def _build_menu(
    transfer_ext: str,
    audio_file_name: str = None,
    audio_file_id: str = None,
) -> dict:
    """
    Build the business-hours or after-hours menu payload.

    Args:
        transfer_ext:    Extension for key 1 TRANSFER_WITHOUT_PROMPT.
        audio_file_name: Name of an org-level WAV file (CUSTOM greeting).
        audio_file_id:   ID of the org-level announcement — required by Webex
                         API (error 6515 if omitted when greeting=CUSTOM).
    """
    greeting = "CUSTOM" if audio_file_name else "DEFAULT"
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
    if audio_file_name:
        audio_entry: dict = {
            "name":          audio_file_name,
            "mediaType":     "WAV",
            "mediaFileType": "ORGANIZATION",
        }
        if audio_file_id:
            audio_entry["id"] = audio_file_id
        menu["audioFile"] = audio_entry
    return menu


class AutoAttendants:

    def list(self, location_id: str, name: str = None) -> list[dict]:
        """List all auto attendants in a location.

        Uses the org-level endpoint with locationId as a query param —
        the location-path variant returns 404 for some orgs.
        """
        params: dict = {"locationId": location_id}
        if name:
            params["name"] = name
        return client.get_all_pages(
            _BASE,
            params=params,
            items_key="autoAttendants",
        )

    def get(self, location_id: str, auto_attendant_id: str) -> dict:
        """Get full details for one auto attendant.

        Uses the location-path endpoint — the org-level /{id} variant
        returns 404 for some orgs (same issue as list(), but reversed:
        list needs org-level, get needs location-path).
        """
        return client.get(
            f"{_BASE_LOC.format(location_id=location_id)}/{auto_attendant_id}",
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

        extension_dialing: "GROUP" (Location scope) or "ENTERPRISE" (Org scope).
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

        return client.post(_BASE_LOC.format(location_id=location_id), body=body)

    def create_from_template(
        self,
        location_id:       str,
        location_name:     str,
        aa_type:           str,
        time_zone:         str,
        phone_number:      str  = None,
        schedule_ok:       bool = True,
        audio_file_name:   str  = None,
        audio_file_id:     str  = None,
        alternate_numbers: list = None,
        dry_run:           bool = False,
    ) -> dict:
        """
        Create a Retail or Priority AA using the standard template.

        Args:
            audio_file_name: Name of an org-level WAV file to use as the greeting.
            audio_file_id:   ID of that announcement — required by Webex API
                             alongside the name when greeting=CUSTOM.
        """
        if aa_type not in AA_TEMPLATES:
            raise ValueError(f"aa_type must be one of {list(AA_TEMPLATES.keys())}")

        tmpl         = AA_TEMPLATES[aa_type]
        aa_name      = f"{location_name} {tmpl['suffix']}"
        transfer_ext = tmpl["transfer_ext"]
        menu         = _build_menu(transfer_ext, audio_file_name=audio_file_name, audio_file_id=audio_file_id)

        body: dict = {
            "name":              aa_name,
            "extension":         tmpl["extension"],
            "languageCode":      tmpl["language_code"],
            "timeZone":          time_zone,
            "extensionDialing":  "GROUP",
            "businessHoursMenu": menu,
            "afterHoursMenu":    menu,
        }

        if phone_number:
            body["phoneNumber"] = phone_number

        if schedule_ok:
            body["businessSchedule"] = BUSINESS_SCHEDULE_NAME

        if alternate_numbers:
            body["alternateNumbers"] = [
                {"phoneNumber": n["phoneNumber"], "ringPattern": n.get("ringPattern", "NORMAL")}
                for n in alternate_numbers
            ]

        if dry_run:
            return body

        result = self.create(
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

        # POST may silently ignore extensionDialing, noInputGracePeriodSeconds, and
        # noInputRepeatTimes on some org configurations, defaulting to ENTERPRISE/10/0.
        # A follow-up PUT forces all three through reliably.
        new_id = result.get("id", "")
        if new_id:
            try:
                self.update(
                    location_id=location_id,
                    auto_attendant_id=new_id,
                    business_hours_menu=menu,
                    after_hours_menu=menu,
                    extension_dialing="GROUP",
                )
            except Exception:
                pass  # AA was created; settings update is best-effort

        return result

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
        extension_dialing:   str  = None,
    ) -> dict:
        """
        Update an existing auto attendant.

        GETs the current full config first, then merges only the fields you
        pass, and PUTs the complete body back.
        """
        path    = f"{_BASE_LOC.format(location_id=location_id)}/{auto_attendant_id}"
        current = self.get(location_id, auto_attendant_id)

        for field in ("id", "locationId", "locationName"):
            current.pop(field, None)

        if name is not None:               current["name"]               = name
        if phone_number is not None:       current["phoneNumber"]        = phone_number
        if extension is not None:          current["extension"]          = extension
        if language_code is not None:      current["languageCode"]       = language_code
        if time_zone is not None:          current["timeZone"]           = time_zone
        if business_schedule is not None:  current["businessSchedule"]   = business_schedule
        if business_hours_menu is not None: current["businessHoursMenu"] = business_hours_menu
        if after_hours_menu is not None:   current["afterHoursMenu"]     = after_hours_menu
        if alternate_numbers is not None:  current["alternateNumbers"]   = alternate_numbers
        if extension_dialing is not None:  current["extensionDialing"]   = extension_dialing

        return client.put(path, body=current)

    def delete(self, location_id: str, auto_attendant_id: str) -> dict:
        """Delete an auto attendant."""
        path = f"{_BASE_LOC.format(location_id=location_id)}/{auto_attendant_id}"
        return client.delete(path)


auto_attendants = AutoAttendants()
