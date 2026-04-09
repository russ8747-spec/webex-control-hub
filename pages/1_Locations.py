"""
pages/1_Locations.py - Browse and search all Webex locations.
"""

import streamlit as st
import pandas as pd
from utils.ui     import connection_status_badge, empty_state, api_error, section
from utils.cache  import get_locations
from utils.export import records_to_csv_bytes

st.set_page_config(page_title="Locations — Control Hub", page_icon="📍", layout="wide")

with st.sidebar:
    st.title("📍 Locations")
    connection_status_badge()
    st.divider()
    name_filter = st.text_input("🔍 Search by name", placeholder="e.g. ATL, Chicago…")
    st.caption("Searches live against the Webex API.")

# ── Fetch ─────────────────────────────────────────────────────────────────────
st.title("📍 Locations")
st.caption("All locations in your Webex organization. Click a row to set it as the active location.")

try:
    all_locations = get_locations(name=name_filter if name_filter else None)
except Exception as e:
    api_error(e)
    st.stop()

if not all_locations:
    empty_state("No locations found. Try a different search term.")
    st.stop()

# ── Summary ───────────────────────────────────────────────────────────────────
st.metric("Locations found", f"{len(all_locations):,}")
st.divider()

# ── Build display table ───────────────────────────────────────────────────────
rows = []
for loc in all_locations:
    address = loc.get("address", {})
    street  = address.get("address1", "")
    city    = address.get("city", "")
    state   = address.get("state", "")
    zip_code = address.get("postalCode", "")
    parts   = [p for p in [street, city, state, zip_code] if p]
    rows.append({
        "Name":         loc.get("name", ""),
        "Address":      ", ".join(parts) if parts else "—",
        "Time Zone":    loc.get("timeZone", ""),
        "Language":     loc.get("preferredLanguage", ""),
        "Country":      address.get("country", ""),
    })

df = pd.DataFrame(rows)

# ── Interactive table ──────────────────────────────────────────────────────────
section("All Locations")

# Let user pick a row to set as active location
selected = st.dataframe(
    df,
    use_container_width=True,
    height=500,
    on_select="rerun",
    selection_mode="single-row",
)

# Handle row selection
if selected and selected.get("selection", {}).get("rows"):
    row_idx  = selected["selection"]["rows"][0]
    chosen   = all_locations[row_idx]
    loc_id   = chosen.get("id", "")
    loc_name = chosen.get("name", "")

    st.session_state.active_location_id   = loc_id
    st.session_state.active_location_name = loc_name

    st.success(f"✅ Active location set to **{loc_name}**")

    with st.expander("📋 Location Details", expanded=True):
        address = chosen.get("address", {})
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Name:** {loc_name}")
        c1.markdown(f"**Time Zone:** {chosen.get('timeZone', '—')}")
        c1.markdown(f"**Language:** {chosen.get('preferredLanguage', '—')}")
        c2.markdown(f"**Address:** {address.get('address1', '—')}")
        c2.markdown(f"**City/State:** {address.get('city', '')} {address.get('state', '')}")
        c2.markdown(f"**Country:** {address.get('country', '—')}")
        c3.markdown(f"**Location ID:**")
        c3.code(loc_id, language=None)

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col2:
            if st.button("💻 View Devices for this Location", use_container_width=True):
                st.switch_page("pages/2_Devices.py")
        with btn_col3:
            if st.button("🔢 View Numbers for this Location", use_container_width=True):
                st.switch_page("pages/5_Numbers.py")

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()
section("Export")
csv_bytes, filename = records_to_csv_bytes(all_locations, "locations")
st.download_button(
    label="⬇️ Export Locations to CSV",
    data=csv_bytes,
    file_name=filename,
    mime="text/csv",
    use_container_width=False,
)
