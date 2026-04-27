"""
pages/11_Bulk_Add_Numbers.py - Bulk add DIDs / phone numbers to locations.

Two input modes:
  CSV Upload  — upload a file with phone_number + location_name columns
  Type/Paste  — paste numbers into a text area and pick a location from a dropdown

Both modes share the same validate → preview → execute → results flow.
"""

import re
import streamlit as st
import pandas as pd

from utils.ui     import connection_status_badge, api_error, section
from utils.cache  import get_locations, clear_all_caches
from utils.audit  import log as audit_log
from utils.export import to_csv_bytes
from webex.client import WebexAPIError
from webex.numbers import numbers as numbers_api

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def normalize_e164(raw: str) -> str:
    digits_only = re.sub(r"[^\d]", "", raw)
    if len(digits_only) == 10:
        return f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"
    elif raw.strip().startswith("+") and len(digits_only) >= 7:
        return f"+{digits_only}"
    return raw.strip()


def validate_rows(raw_pairs: list[tuple[str, str, str]], loc_by_name: dict) -> tuple[list, list]:
    """
    Validate a list of (raw_num, loc_name, loc_id) tuples.
    Returns (valid_rows, errors).
    raw_pairs items: (original_number_string, location_name, location_id_or_empty)
    """
    errors     = []
    valid_rows = []

    for i, (raw_num, loc_name, loc_id) in enumerate(raw_pairs):
        num      = normalize_e164(raw_num)
        row_errs = []

        if not E164_RE.match(num):
            row_errs.append(
                f"Could not convert '{raw_num}' to E.164 — "
                "expected 10 digits, xxx-xxx-xxxx, or +1xxxxxxxxxx"
            )
        if not loc_id:
            row_errs.append("Location not found in Control Hub")

        if row_errs:
            errors.append({
                "Row":          i + 1,
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
                "location_id":   loc_id,
            })

    return valid_rows, errors


def render_review_and_execute(valid_rows: list, errors: list, total: int, number_type: str):
    """Shared review, preview, execute, and results section."""
    st.divider()
    section("Review & Execute")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total",   total)
    c2.metric("Valid",   len(valid_rows))
    c3.metric("Errors",  len(errors))

    if errors:
        with st.expander(f"⚠️ {len(errors)} row(s) with issues (will be skipped)", expanded=True):
            st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

    if not valid_rows:
        st.warning("No valid numbers to add. Fix the issues above and try again.")
        return

    valid_df = pd.DataFrame(valid_rows)
    grouped  = (
        valid_df
        .groupby(["location_name", "location_id"])["phone_number"]
        .apply(list)
        .reset_index()
    )

    st.markdown(
        f"**{len(valid_rows)} number(s)** ready to add across "
        f"**{len(grouped)} location(s)** as type `{number_type}`:"
    )

    for _, grp in grouped.iterrows():
        with st.expander(f"📍 {grp['location_name']} — {len(grp['phone_number'])} number(s)"):
            preview_rows = [
                {
                    "E.164 Number": vr["phone_number"],
                    "Original":     vr["original"],
                    "Converted":    "✅" if vr["original"] != vr["phone_number"] else "",
                }
                for vr in valid_rows
                if vr["location_name"] == grp["location_name"]
            ]
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    st.divider()

    if "ban_results" not in st.session_state:
        st.session_state.ban_results = None

    if st.button("➕ Add Numbers Now", type="primary", use_container_width=True):
        results  = []
        progress = st.progress(0, text="Starting…")
        n_locs   = len(grouped)

        for idx, (_, grp) in enumerate(grouped.iterrows()):
            loc_id   = grp["location_id"]
            loc_name = grp["location_name"]
            nums     = grp["phone_number"]
            progress.progress(idx / n_locs, text=f"Adding to {loc_name}…")

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

            progress.progress((idx + 1) / n_locs, text=f"Done with {loc_name}")

        progress.empty()
        clear_all_caches()
        st.session_state.ban_results = results
        st.rerun()

    if st.session_state.ban_results:
        results_df = pd.DataFrame(st.session_state.ban_results)
        added  = results_df["Status"].str.startswith("✅").sum()
        failed = results_df["Status"].str.startswith("❌").sum()

        section("Results")
        ra, rf = st.columns(2)
        ra.metric("✅ Added",  added)
        rf.metric("❌ Failed", failed)

        st.dataframe(results_df, use_container_width=True, hide_index=True, height=400)

        csv_bytes, csv_filename = to_csv_bytes(st.session_state.ban_results, "bulk_add_numbers_results")
        st.download_button(
            "⬇️ Download Results CSV",
            data=csv_bytes,
            file_name=csv_filename,
            mime="text/csv",
        )


# ── Page config ───────────────────────────────────────────────────────────────
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
st.caption("Add phone numbers to one or more locations. Choose your input method below.")
st.divider()

# ── Load locations ────────────────────────────────────────────────────────────
try:
    all_locs    = get_locations()
    loc_by_name = {loc["name"]: loc["id"] for loc in all_locs}
    loc_names   = sorted(loc_by_name.keys())
except Exception as e:
    api_error(e)
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_csv, tab_paste = st.tabs(["📄 CSV Upload", "✏️ Type or Paste"])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — CSV Upload
# ════════════════════════════════════════════════════════════════════════════════
with tab_csv:
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
    section("Step 2 — Upload Your CSV")
    uploaded = st.file_uploader("Choose your filled-in CSV", type=["csv"], key="csv_upload")

    if uploaded:
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

        raw_pairs = [
            (
                str(row["phone_number"]).strip(),
                str(row["location_name"]).strip(),
                loc_by_name.get(str(row["location_name"]).strip(), ""),
            )
            for _, row in df.iterrows()
        ]

        valid_rows, errors = validate_rows(raw_pairs, loc_by_name)
        render_review_and_execute(valid_rows, errors, len(df), number_type)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — Type or Paste
# ════════════════════════════════════════════════════════════════════════════════
with tab_paste:
    section("Enter Numbers")
    st.caption(
        "One number per line. Accepts 10-digit, `xxx-xxx-xxxx`, `1xxxxxxxxxx`, or `+1xxxxxxxxxx` format."
    )

    pasted = st.text_area(
        "Phone numbers (one per line)",
        height=200,
        placeholder="7705551001\n770-555-1002\n+17705551003",
        key="paste_input",
    )

    loc_choice = st.selectbox(
        "Location",
        options=loc_names,
        index=0 if loc_names else None,
        help="All numbers above will be added to this location.",
        key="paste_location",
    )

    if pasted.strip() and loc_choice:
        lines = [ln.strip() for ln in pasted.strip().splitlines() if ln.strip()]
        loc_id = loc_by_name.get(loc_choice, "")

        raw_pairs = [(ln, loc_choice, loc_id) for ln in lines]
        valid_rows, errors = validate_rows(raw_pairs, loc_by_name)
        render_review_and_execute(valid_rows, errors, len(lines), number_type)
