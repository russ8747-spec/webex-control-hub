"""
pages/5_Numbers.py - Phone number inventory and usage lookup.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.ui     import connection_status_badge, empty_state, api_error, section
from utils.cache  import get_numbers, get_locations
from utils.export import records_to_csv_bytes
from webex.numbers import numbers as numbers_api

st.set_page_config(page_title="Numbers — Control Hub", page_icon="🔢", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔢 Numbers")
    connection_status_badge()
    st.divider()

    try:
        all_locs     = get_locations()
        loc_options  = {"All Locations": None} | {loc["name"]: loc["id"] for loc in all_locs}
        default_name = st.session_state.get("active_location_name", "All Locations")
        default_idx  = list(loc_options.keys()).index(default_name) if default_name in loc_options else 0
        selected_loc = st.selectbox("📍 Location", list(loc_options.keys()), index=default_idx)
        location_id  = loc_options[selected_loc]
    except Exception as e:
        st.error("Could not load locations.")
        location_id  = None
        selected_loc = "All Locations"

    st.divider()
    st.subheader("Filters")
    owner_filter = st.selectbox(
        "Filter by assignment",
        ["All", "Unassigned", "User", "Auto Attendant", "Hunt Group",
         "Call Queue", "Workspace", "Virtual Line"],
    )
    search_num = st.text_input("🔍 Search number or extension", "")

# ── Find a number ─────────────────────────────────────────────────────────────
st.title("🔢 Numbers & Phone Inventory")

with st.expander("🔍 Find Where a Number Is Used", expanded=False):
    lookup_num = st.text_input("Enter a phone number to look up", placeholder="+13125551234")
    if st.button("Look Up", type="primary") and lookup_num:
        with st.spinner("Searching…"):
            try:
                result = numbers_api.find_usage(lookup_num)
                if result["found"]:
                    st.success(f"**{lookup_num}** is assigned.")
                    r1, r2, r3 = st.columns(3)
                    r1.markdown(f"**Owner Type:** {result['owner_type']}")
                    r1.markdown(f"**Owner:** {result['owner_name'] or '—'}")
                    r2.markdown(f"**Location:** {result['location']}")
                    r2.markdown(f"**Extension:** {result['extension'] or '—'}")
                    r3.markdown(f"**State:** {result['state']}")
                    r3.markdown(f"**Main Number:** {'Yes' if result['main_number'] else 'No'}")
                else:
                    st.warning(f"**{lookup_num}** was not found in this org.")
            except Exception as e:
                api_error(e)

st.divider()

# ── Fetch inventory ───────────────────────────────────────────────────────────
st.caption(f"Showing numbers for: **{selected_loc}**")

try:
    raw_numbers = get_numbers(location_id=location_id)
except Exception as e:
    api_error(e)
    st.stop()

if not raw_numbers:
    empty_state("No numbers found for the selected location.", "🔢")
    st.stop()

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = raw_numbers

if owner_filter == "Unassigned":
    filtered = [n for n in filtered if not n.get("owner")]
elif owner_filter != "All":
    filtered = [n for n in filtered if n.get("ownerTypeLabel") == owner_filter]

if search_num:
    term = search_num.lower()
    filtered = [
        n for n in filtered
        if term in n.get("phoneNumber", "").lower()
        or term in str(n.get("extension", "")).lower()
    ]

# ── Summary ───────────────────────────────────────────────────────────────────
summary  = numbers_api.summary(raw_numbers)
c1, c2, c3 = st.columns(3)
c1.metric("Total Numbers",  f"{summary['total']:,}")
c2.metric("Assigned",       f"{summary['assigned']:,}")
c3.metric("Unassigned",     f"{summary['unassigned']:,}")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
if raw_numbers:
    ch1, ch2 = st.columns(2)

    with ch1:
        owner_counts = pd.DataFrame([
            {"Type": n.get("ownerTypeLabel", "Unassigned")} for n in raw_numbers
        ])["Type"].value_counts().reset_index()
        owner_counts.columns = ["Owner Type", "Count"]
        fig = px.pie(
            owner_counts, values="Count", names="Owner Type",
            title="Numbers by Assignment Type",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        if "location" in pd.DataFrame(raw_numbers).columns:
            loc_df = pd.json_normalize(raw_numbers)
            if "location.name" in loc_df.columns:
                loc_counts = loc_df["location.name"].value_counts().head(10).reset_index()
                loc_counts.columns = ["Location", "Count"]
                fig2 = px.bar(
                    loc_counts, x="Count", y="Location", orientation="h",
                    title="Top 10 Locations by Number Count",
                    color="Count", color_continuous_scale="Teal",
                )
                fig2.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig2, use_container_width=True)

# ── Number table ──────────────────────────────────────────────────────────────
section("Number Inventory", f"Showing {len(filtered):,} of {len(raw_numbers):,} numbers")

def _owner_name(owner: dict) -> str:
    """
    Return the best human-readable name for a number's owner.
    Hunt groups store the actual name in 'lastName' (firstName is the
    generic string 'Hunt Group'). Users/workspaces use displayName.
    """
    if not owner:
        return "—"
    owner_type = owner.get("type") or owner.get("ownerType", "")
    if owner_type == "HUNT_GROUP":
        return owner.get("lastName") or owner.get("displayName") or "—"
    return (
        owner.get("displayName")
        or f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip()
        or "—"
    )

rows = []
for n in filtered:
    owner    = n.get("owner", {})
    location = n.get("location", {})
    rows.append({
        "Phone Number": n.get("phoneNumber", "—"),
        "Extension":    n.get("extension", "—"),
        "Assignment":   n.get("ownerTypeLabel", "Unassigned"),
        "Assigned To":  _owner_name(owner),
        "Location":     location.get("name", "—"),
        "State":        n.get("state", "—"),
        "Main Number":  "✅" if n.get("mainNumber") else "",
        "Toll-Free":    "✅" if n.get("tollFreeNumber") else "",
    })

df = pd.DataFrame(rows) if rows else pd.DataFrame()
if not df.empty:
    st.dataframe(df, use_container_width=True, height=450)
else:
    empty_state("No numbers match the current filters.")

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()
section("Export")
csv_bytes, filename = records_to_csv_bytes(
    filtered, f"numbers_{selected_loc.replace(' ', '_')}"
)
st.download_button(
    label="⬇️ Export Number List to CSV",
    data=csv_bytes,
    file_name=filename,
    mime="text/csv",
)
