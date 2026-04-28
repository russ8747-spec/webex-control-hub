"""
pages/12_Music_On_Hold.py - Music on Hold viewer across all locations.

Fetches MOH settings for every location in parallel and displays
them in a single sortable table — no clicking into each location.
"""

import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.ui    import connection_status_badge, api_error, section
from utils.cache import get_locations
from utils.export import to_csv_bytes
from webex.music_on_hold import music_on_hold as moh_api
from webex.client import WebexAPIError

st.set_page_config(
    page_title="Music on Hold — Control Hub",
    page_icon="🎵",
    layout="wide",
)

MAX_WORKERS = 20  # concurrent API calls

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎵 Music on Hold")
    connection_status_badge()
    st.divider()
    refresh = st.button("🔄 Refresh", use_container_width=True)

# ── Page header ───────────────────────────────────────────────────────────────
st.title("🎵 Music on Hold — All Locations")
st.caption("Shows the MOH file configured for every location in one table.")
st.divider()

# ── Load locations ────────────────────────────────────────────────────────────
try:
    all_locs = get_locations()
except Exception as e:
    api_error(e)
    st.stop()

if not all_locs:
    st.warning("No locations found.")
    st.stop()

# ── Fetch MOH for all locations in parallel ───────────────────────────────────
if refresh:
    st.cache_data.clear()

if "moh_rows" not in st.session_state or refresh:
    rows    = []
    errors  = []
    total   = len(all_locs)
    bar     = st.progress(0, text="Fetching Music on Hold settings…")
    done    = 0

    def _fetch(loc: dict) -> dict:
        try:
            moh = moh_api.get(loc["id"])
            audio = moh.get("audioFile") or {}
            return {
                "Location":        loc["name"],
                "Greeting":        moh.get("greeting", "DEFAULT"),
                "Audio File":      audio.get("name", "—") if moh.get("greeting") == "CUSTOM" else "Default",
                "File Scope":      audio.get("mediaFileType", "—") if moh.get("greeting") == "CUSTOM" else "—",
                "Call Hold MOH":   "✅" if moh.get("callHoldEnabled", False) else "❌",
                "Call Park MOH":   "✅" if moh.get("callParkEnabled", False) else "❌",
                "_loc_id":         loc["id"],
                "_error":          "",
            }
        except WebexAPIError as e:
            return {
                "Location":       loc["name"],
                "Greeting":       "—",
                "Audio File":     f"Error: {e.message}",
                "File Scope":     "—",
                "Call Hold MOH":  "—",
                "Call Park MOH":  "—",
                "_loc_id":        loc["id"],
                "_error":         str(e),
            }

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch, loc): loc for loc in all_locs}
        for future in as_completed(futures):
            rows.append(future.result())
            done += 1
            bar.progress(done / total, text=f"Fetched {done} / {total} locations…")

    bar.empty()
    rows.sort(key=lambda r: r["Location"])
    st.session_state.moh_rows = rows

rows = st.session_state.moh_rows

# ── Summary metrics ───────────────────────────────────────────────────────────
custom_count  = sum(1 for r in rows if r["Greeting"] == "CUSTOM")
default_count = sum(1 for r in rows if r["Greeting"] == "DEFAULT")
error_count   = sum(1 for r in rows if r["_error"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Locations", len(rows))
m2.metric("Using Custom File", custom_count)
m3.metric("Using Default",    default_count)
m4.metric("Errors",           error_count)

st.divider()

# ── Filter ────────────────────────────────────────────────────────────────────
col_filter, col_greeting = st.columns([3, 1])
search = col_filter.text_input("🔍 Filter by location name or file name", key="moh_search")
greeting_filter = col_greeting.selectbox(
    "Greeting Type",
    ["All", "CUSTOM", "DEFAULT"],
    key="moh_greeting_filter",
)

display_rows = rows
if search:
    s = search.lower()
    display_rows = [r for r in display_rows if s in r["Location"].lower() or s in r["Audio File"].lower()]
if greeting_filter != "All":
    display_rows = [r for r in display_rows if r["Greeting"] == greeting_filter]

# ── Table ─────────────────────────────────────────────────────────────────────
section(f"Results — {len(display_rows)} location(s)")

table_cols = ["Location", "Greeting", "Audio File", "File Scope", "Call Hold MOH", "Call Park MOH"]
df = pd.DataFrame(display_rows)[table_cols]

st.dataframe(df, use_container_width=True, hide_index=True, height=600)

# ── Export ────────────────────────────────────────────────────────────────────
if rows:
    export_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    csv_bytes, csv_filename = to_csv_bytes(export_rows, "music_on_hold_all_locations")
    st.download_button(
        "⬇️ Export to CSV",
        data=csv_bytes,
        file_name=csv_filename,
        mime="text/csv",
    )

if error_count:
    with st.expander(f"⚠️ {error_count} location(s) returned errors"):
        err_rows = [{"Location": r["Location"], "Error": r["_error"]} for r in rows if r["_error"]]
        st.dataframe(pd.DataFrame(err_rows), use_container_width=True, hide_index=True)
