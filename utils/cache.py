"""
utils/cache.py - Cached wrappers for expensive Webex API list calls.

Uses Streamlit's st.cache_data with short TTLs so the UI stays
responsive without hammering the API on every page load.

TTLs:
  Locations  → 5 min  (rarely change)
  Devices    → 2 min  (status changes more often)
  Numbers    → 5 min  (assignments change infrequently)
"""

import streamlit as st
from webex.locations       import locations       as _locations
from webex.devices         import devices         as _devices
from webex.numbers         import numbers         as _numbers
from webex.hunt_groups     import hunt_groups     as _hunt_groups
from webex.schedules       import schedules       as _schedules
from webex.auto_attendants import auto_attendants as _auto_attendants
from webex.announcements   import announcements   as _announcements
from webex.people          import people          as _people
from webex.virtual_lines   import virtual_lines   as _virtual_lines
from webex.paging_groups   import paging_groups   as _paging_groups


@st.cache_data(ttl=300, show_spinner="Loading locations…")
def get_locations(name: str = None) -> list[dict]:
    return _locations.list(name=name)


@st.cache_data(ttl=120, show_spinner="Loading devices…")
def get_devices(
    location_id:       str  = None,
    model:             str  = None,
    connection_status: str  = None,
) -> list[dict]:
    return _devices.list(
        location_id=location_id,
        model=model,
        connection_status=connection_status,
    )


@st.cache_data(ttl=300, show_spinner="Loading numbers…")
def get_numbers(location_id: str = None) -> list[dict]:
    return _numbers.list(location_id=location_id)


@st.cache_data(ttl=120, show_spinner="Loading hunt groups…")
def get_hunt_groups(location_id: str) -> list[dict]:
    return _hunt_groups.list(location_id=location_id)


@st.cache_data(ttl=300, show_spinner="Loading schedules…")
def get_schedules(location_id: str) -> list[dict]:
    return _schedules.list(location_id=location_id)


@st.cache_data(ttl=120, show_spinner="Loading auto attendants…")
def get_auto_attendants(location_id: str) -> list[dict]:
    return _auto_attendants.list(location_id=location_id)


@st.cache_data(ttl=300, show_spinner="Loading announcements…")
def get_announcements() -> list[dict]:
    return _announcements.list()


@st.cache_data(ttl=120, show_spinner="Loading people…")
def get_people(location_id: str) -> list[dict]:
    return _people.list(location_id=location_id)


@st.cache_data(ttl=120, show_spinner="Loading virtual lines…")
def get_virtual_lines(location_id: str) -> list[dict]:
    return _virtual_lines.list(location_id=location_id)


@st.cache_data(ttl=120, show_spinner="Loading paging groups…")
def get_paging_groups(location_id: str) -> list[dict]:
    return _paging_groups.list(location_id=location_id)


def clear_all_caches():
    """Call this after any write operation to force fresh data."""
    get_locations.clear()
    get_devices.clear()
    get_numbers.clear()
    get_hunt_groups.clear()
    get_schedules.clear()
    get_auto_attendants.clear()
    get_people.clear()
    get_virtual_lines.clear()
    get_paging_groups.clear()
    get_announcements.clear()
