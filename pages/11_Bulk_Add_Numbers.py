"""
pages/11_Bulk_Add_Numbers.py - Bulk add DIDs / phone numbers to locations.

Upload a CSV with phone_number + location_name columns.
The page validates every row, previews the batches grouped by location,
then POSTs to the Webex Numbers API in one call per location.
"""

import re
import streamlit as st
import pandas as pd

from utils.ui     import connection_status_badge, api_error, section, empty_state
from utils.cache  import get_locations, clear_all_caches
from utils.audit  import log as audit_log
from utils.export import to_csv_bytes
from webex.client import WebexAPIError
from webex.numbers import numbers as numbers_api

# E.164: + followed by 7–15 digits, first digit not 0
E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def normalize_e164(raw: str) -> str:
    """
    Convert common US number formats to E.164.

    Handles:
      xxxxxxxxxx       → +1xxxxxxxxxx
      xxx-xxx-xxxx     → +1xxxxxxxxxx
      +1xxxxxxxxxx     → +1xxxxxxxxxx  (unchanged)
      1xxxxxxxxxx      → +1xxxxxxxxxx
    """
    digits_only = re.sub(r"[^\d]", "", raw)

    if len(digits_only) == 10:
        return f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"
    elif raw.strip().startswith("+") and len(digits_only) >= 7:
        return f"+{digits_only}"

    return raw.strip()

st.set_page_config(
    page_title="Bulk Add Numbers — Control Hub",
    page_icon="📲",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📲 Bulk Add Numbers")
    connection_status_badge()
    st.divider()

    number_type = st.selectbox(
        "Number Type",
        ["DID", "TOLLFREE", "MOBILE"],
        index=0,
        help="Applied to every number in this upload.",
    )

# ── Page header ───────────────────────────────────────────────────────────────
st.title("📲 Bulk Add Phone Numbers")
st.caption(
    "Add DIDs to one or more locations in a single upload. "
    "Required columns: `phone_number` (E.164) and `location_name` (must match Control Hub exactly)."
)
st.divider()

# ── Load locations for validation ─────────────────────────────────────────────
try:
    all_locs    = get_locations()
    loc_by_name = {loc["name"]: loc["id"] for loc in all_locs}
except Exception as e:
    api_error(e)
    st.stop()

# ── Step 1: template download ─────────────────────────────────────────────────
section("Step 1 — Download the Template")
st.caption(
    "Phone numbers must be in **E.164 format** (e.g. `+17705551234`).  \n"
    "Location names must match Control Hub **exactly** — copy them from the Locations page."
)

template_rows = [
    {"phone_number": "+17705551001", "location_name": "Your Location Name Here"},
    {"phone_number": "+17705551002", "location_name": "Your Location Name Here"},
    {"phone_number": "+17705551003", "location_name": "Another Location Name"},
]
template_csv, _ = to_csv_bytes(template_rows, "bulk_add_numbers_template")
st.download_button(
    "⬇️ Download CSV Template",
    data=template_csv,
    file_name="bulk_add_numbers_template.csv",
    mime="text/csv",
)

st.divider()

# ── Step 2: upload ────────────────────────────────────────────────────────────
section("Step 2 — Upload Your CSV")
uploaded = st.file_uploader("Choose your filled-in CSV", type=["csv"])

if not uploaded:
    st.stop()

# ── Parse ─────────────────────────────────────────────────────────────────────
try:
    df = pd.read_csv(uploaded, dtype=str).fillna("")
except Exception as e:
    st.error(f"Could not parse CSV: {e}")
    st.stop()

required_cols = {"phone_number", "location_name"}
if not required_cols.issubset(set(df.columns)):
    missing = required_cols - set(df.columns)
    st.error(f"CSV is missing required column(s): {', '.join(f'`{c}`' for c in missing)}")
    st.stop()

# ── Validate each row ─────────────────────────────────────────────────────────
errors     = []
valid_rows = []

for i, row in df.iterrows():
    raw_num  = row["phone_number"].strip()
    num      = normalize_e164(raw_num)
    loc_name = row["location_name"].strip()
    row_errs = []

    if not E164_RE.match(num):
        row_errs.append(f"Could not convert '{raw_num}' to E.164 — expected 10 digits, xxx-xxx-xxxx, or +1xxxxxxxxxx")
    if loc_name not in loc_by_name:
        row_errs.append("Location not found in Control Hub")

    if row_errs:
        errors.append({
            "Row":          i + 2,
            "Original":     raw_num,
            "Phone Number": num,
            "Location":     loc_name,
            "Issue":        "; ".join(row_errs),
        })
    else:
        valid_rows.append({
            "phone_number":  num,
            "original":      raw_num,
            "location_name": loc_name,
            "location_id":   loc_by_name[loc_name],
        })

# ── Step 3: review ────────────────────────────────────────────────────────────
st.divider()
section("Step 3 — Review & Execute")

c1, c2, c3 = st.columns(3)
c1.metric("Total Rows",  len(df))
c2.metric("Valid",       len(valid_rows))
c3.metric("Errors",      len(errors))

if errors:
    with st.expander(f"⚠️ {len(errors)} row(s) with issues (will be skipped)", expanded=True):
        st.dataframe(
            pd.DataFrame(errors),
            use_container_width=True,
            hide_index=True,
        )

if not valid_rows:
    st.warning("No valid rows to add. Fix the issues above and re-upload.")
    st.stop()

# ── Preview grouped by location ───────────────────────────────────────────────
valid_df = pd.DataFrame(valid_rows)
grouped  = (
    valid_df
    .groupby(["location_name", "location_id"])["phone_number"]
    .apply(list)
    .reset_index()
)

st.markdown(
    f"**{len(valid_rows)} number(s)** ready to add across **{len(grouped)} location(s)** "
    f"as type `{number_type}`:"
)

for _, grp in grouped.iterrows():
    with st.expander(f"📍 {grp['location_name']} — {len(grp['phone_number'])} number(s)"):
        preview_rows = []
        for vr in valid_rows:
            if vr["location_name"] == grp["location_name"]:
                converted = vr["original"] != vr["phone_number"]
                preview_rows.append({
                    "E.164 Number": vr["phone_number"],
                    "Original":     vr["original"],
                    "Converted":    "✅" if converted else "",
                })
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

st.divider()

# ── Execute ───────────────────────────────────────────────────────────────────
if "ban_results" not in st.session_state:
    st.session_state.ban_results = None

if st.button("➕ Add Numbers Now", type="primary", use_container_width=True):
    results  = []
    progress = st.progress(0, text="Starting…")
    total    = len(grouped)

    for idx, (_, grp) in enumerate(grouped.iterrows()):
        loc_id   = grp["location_id"]
        loc_name = grp["location_name"]
        nums     = grp["phone_number"]
        progress.progress((idx) / total, text=f"Adding to {loc_name}…")

        try:
            numbers_api.add(
                location_id=loc_id,
                phone_numbers=nums,
                number_type=number_type,
            )
            for num in nums:
                results.append({"Location": loc_name, "Phone Number": num, "Status": "✅ Added"})
            audit_log(
                action="bulk_add_numbers",
                object_type="location",
                object_id=loc_id,
                object_name=loc_name,
                details={"phoneNumbers": nums, "numberType": number_type, "count": len(nums)},
                success=True,
            )
        except WebexAPIError as e:
            for num in nums:
                results.append({"Location": loc_name, "Phone Number": num, "Status": f"❌ {e.message}"})
            audit_log(
                action="bulk_add_numbers",
                object_type="location",
                object_id=loc_id,
                object_name=loc_name,
                details={"phoneNumbers": nums, "numberType": number_type, "count": len(nums)},
                success=False,
                error_message=str(e),
                tracking_id=getattr(e, "tracking_id", ""),
            )

        progress.progress((idx + 1) / total, text=f"Done with {loc_name}")

    progress.empty()
    clear_all_caches()
    st.session_state.ban_results = results
    st.rerun()

# ── Results (persisted across rerun) ─────────────────────────────────────────
if st.session_state.ban_results:
    results    = st.session_state.ban_results
    results_df = pd.DataFrame(results)
    added  = results_df["Status"].str.startswith("✅").sum()
    failed = results_df["Status"].str.startswith("❌").sum()

    section("Results")
    ra, rf = st.columns(2)
    ra.metric("✅ Added",  added)
    rf.metric("❌ Failed", failed)

    st.dataframe(results_df, use_container_width=True, hide_index=True, height=400)

    csv_bytes, csv_filename = to_csv_bytes(results, "bulk_add_numbers_results")
    st.download_button(
        "⬇️ Download Results CSV",
        data=csv_bytes,
        file_name=csv_filename,
        mime="text/csv",
    )
