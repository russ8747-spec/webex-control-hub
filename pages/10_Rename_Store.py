"""
pages/10_Rename_Store.py - Store Rename Workflow

When a store's number changes (e.g. ATL123 7001123 → ATL388 7001388),
every asset at that location embeds the old name — user display names,
emails, virtual lines, hunt groups, auto attendants, and paging groups.

This page provides a scan → preview → execute workflow that renames
all affected assets in one operation.

Naming conventions understood:
  Location name (spaces):   "ATL123 7001123"
  Display names:            "ATL123 7001123 Retail" / "ATL123 7001123 Priority"
  Emails (underscores):     "ATL123_7001123_retail@napa.store"
  HGs, AAs, VLs, PGs all embed the location name in their name field.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from collections import defaultdict

from utils.ui          import connection_status_badge, api_error, empty_state
from utils.cache       import get_locations, clear_all_caches
from utils.audit       import log as audit_log
from utils.export      import to_csv_bytes
from webex.client      import WebexAPIError
from webex.people      import people as _people
from webex.virtual_lines   import virtual_lines   as _virtual_lines
from webex.paging_groups   import paging_groups   as _paging_groups
from webex.hunt_groups     import hunt_groups     as _hunt_groups
from webex.auto_attendants import auto_attendants as _auto_attendants
from webex.devices         import devices         as _devices

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rename Store — Control Hub",
    page_icon="✏️",
    layout="wide",
)

# ── Session state helpers ─────────────────────────────────────────────────────
_RS_KEYS = (
    "rs_location_id", "rs_location_name", "rs_new_name",
    "rs_scan_results", "rs_execute_results",
    "rs_scan_done", "rs_execute_done",
)


def _clear_rs():
    """Clear all rename-store session state keys."""
    for k in _RS_KEYS:
        st.session_state.pop(k, None)


def _init_rs():
    """Ensure all rename-store keys have a default value."""
    defaults = {
        "rs_location_id":   "",
        "rs_location_name": "",
        "rs_new_name":      "",
        "rs_scan_results":  [],
        "rs_execute_results": [],
        "rs_scan_done":     False,
        "rs_execute_done":  False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


_init_rs()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("✏️ Rename Store")
    connection_status_badge()
    st.divider()

    try:
        all_locs = get_locations()
        loc_map  = {loc["name"]: loc for loc in all_locs}
        loc_names = list(loc_map.keys())
    except Exception as e:
        st.error("Could not load locations.")
        loc_map, loc_names = {}, []

    st.caption(f"{len(loc_names):,} locations loaded")

    selected_loc_name = st.selectbox(
        "📍 Location to rename",
        loc_names,
        index=0,
        key="rs_loc_select",
        placeholder="Search locations…",
    )

    # When the user picks a different location, reset workflow state
    if selected_loc_name and selected_loc_name != st.session_state.get("rs_location_name"):
        _clear_rs()
        _init_rs()
        st.session_state["rs_location_name"] = selected_loc_name
        st.session_state["rs_location_id"]   = loc_map[selected_loc_name]["id"]

# ── Main layout ───────────────────────────────────────────────────────────────
st.title("✏️ Rename Store")
st.caption(
    "Scan all assets that embed the current store name, preview every field "
    "that will change, then execute the renames in one operation."
)
st.divider()

location_id   = st.session_state.get("rs_location_id", "")
location_name = st.session_state.get("rs_location_name", "")

if not location_id:
    empty_state("Select a location in the sidebar to begin.", "✏️")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Input (always visible)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Step 1 — Enter New Store Name")
st.markdown(f"**Current name:** `{location_name}`")

new_name_input = st.text_input(
    "New store name",
    value=st.session_state.get("rs_new_name", ""),
    placeholder="e.g. ATL388 7001388",
    key="rs_new_name_input",
    help="Enter the new location name exactly as it should appear (spaces, not underscores).",
)
st.session_state["rs_new_name"] = new_name_input.strip()

scan_btn = st.button(
    "🔍 Scan for Affected Assets",
    type="primary",
    disabled=not new_name_input.strip(),
)


# ── Scan logic ────────────────────────────────────────────────────────────────
def _scan(loc_id: str, old_name: str, new_name: str) -> list[dict]:
    """
    Scan all asset types for fields containing old_name or old_prefix.
    Returns one dict per affected field (multiple rows per asset possible).
    """
    old_prefix = old_name.replace(" ", "_")
    new_prefix = new_name.replace(" ", "_")
    rows: list[dict] = []

    # ── People ────────────────────────────────────────────────────────────────
    try:
        person_list = _people.list(loc_id)
        for p in person_list:
            pid          = p.get("id", "")
            display_name = p.get("displayName", "")
            first_name   = p.get("firstName",   "")
            last_name    = p.get("lastName",    "")
            asset_label  = display_name or f"{first_name} {last_name}".strip()

            for field, val in [
                ("displayName", display_name),
                ("firstName",   first_name),
                ("lastName",    last_name),
            ]:
                if val and old_name in val:
                    rows.append({
                        "asset_type": "Person",
                        "asset_id":   pid,
                        "asset_name": asset_label,
                        "field":      field,
                        "old_value":  val,
                        "new_value":  val.replace(old_name, new_name),
                        "_location_id": loc_id,
                    })

            for email in p.get("emails", []):
                if old_prefix in email:
                    rows.append({
                        "asset_type": "Person",
                        "asset_id":   pid,
                        "asset_name": asset_label,
                        "field":      "email",
                        "old_value":  email,
                        "new_value":  email.replace(old_prefix, new_prefix),
                        "_location_id": loc_id,
                    })

    except WebexAPIError:
        pass

    # ── Virtual Lines ─────────────────────────────────────────────────────────
    try:
        vl_list = _virtual_lines.list(loc_id)
        for vl in vl_list:
            vl_id        = vl.get("id", "")
            display_name = vl.get("displayName", "")
            first_name   = vl.get("firstName",   "")
            last_name    = vl.get("lastName",    "")
            asset_label  = display_name or f"{first_name} {last_name}".strip()

            for field, val in [
                ("displayName", display_name),
                ("firstName",   first_name),
                ("lastName",    last_name),
            ]:
                if val and old_name in val:
                    rows.append({
                        "asset_type": "Virtual Line",
                        "asset_id":   vl_id,
                        "asset_name": asset_label,
                        "field":      field,
                        "old_value":  val,
                        "new_value":  val.replace(old_name, new_name),
                        "_location_id": loc_id,
                    })

    except WebexAPIError:
        pass

    # ── Hunt Groups ───────────────────────────────────────────────────────────
    try:
        hg_list = _hunt_groups.list(loc_id)
        for hg in hg_list:
            name = hg.get("name", "")
            if old_name in name:
                rows.append({
                    "asset_type": "Hunt Group",
                    "asset_id":   hg.get("id", ""),
                    "asset_name": name,
                    "field":      "name",
                    "old_value":  name,
                    "new_value":  name.replace(old_name, new_name),
                    "_location_id": loc_id,
                })

    except WebexAPIError:
        pass

    # ── Auto Attendants ───────────────────────────────────────────────────────
    try:
        aa_list = _auto_attendants.list(loc_id)
        for aa in aa_list:
            name = aa.get("name", "")
            if old_name in name:
                rows.append({
                    "asset_type": "Auto Attendant",
                    "asset_id":   aa.get("id", ""),
                    "asset_name": name,
                    "field":      "name",
                    "old_value":  name,
                    "new_value":  name.replace(old_name, new_name),
                    "_location_id": loc_id,
                })

    except WebexAPIError:
        pass

    # ── Paging Groups ─────────────────────────────────────────────────────────
    try:
        pg_list = _paging_groups.list(loc_id)
        for pg in pg_list:
            name = pg.get("name", "")
            if old_name in name:
                rows.append({
                    "asset_type": "Paging Group",
                    "asset_id":   pg.get("id", ""),
                    "asset_name": name,
                    "field":      "name",
                    "old_value":  name,
                    "new_value":  name.replace(old_name, new_name),
                    "_location_id": loc_id,
                })

    except WebexAPIError:
        pass

    # ── Devices (manual only — displayName not writable via API) ──────────────
    try:
        device_list = _devices.list(location_id=loc_id)
        for d in device_list:
            display_name = d.get("displayName", "")
            if display_name and old_name in display_name:
                rows.append({
                    "asset_type": "Device",
                    "asset_id":   d.get("id", ""),
                    "asset_name": display_name,
                    "field":      "displayName",
                    "old_value":  display_name,
                    "new_value":  "Manual — Control Hub",
                    "_location_id": loc_id,
                })

    except WebexAPIError:
        pass

    return rows


if scan_btn:
    new_name = st.session_state["rs_new_name"]
    if new_name == location_name:
        st.error("New name must be different from the current name.")
    else:
        with st.spinner("Scanning assets…"):
            scan_rows = _scan(location_id, location_name, new_name)
        st.session_state["rs_scan_results"]  = scan_rows
        st.session_state["rs_scan_done"]     = True
        st.session_state["rs_execute_done"]  = False
        st.session_state["rs_execute_results"] = []
        st.rerun()

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Preview
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["rs_scan_done"] and not st.session_state["rs_execute_done"]:
    new_name   = st.session_state["rs_new_name"]
    scan_rows  = st.session_state["rs_scan_results"]

    st.subheader("Step 2 — Preview Changes")

    if not scan_rows:
        empty_state(
            f"No assets found with '{location_name}' in their name or email. "
            "Nothing to rename.",
            "🔍",
        )
        st.stop()

    # ── Metrics per asset type ────────────────────────────────────────────────
    type_counts: dict[str, set] = defaultdict(set)
    for row in scan_rows:
        type_counts[row["asset_type"]].add(row["asset_id"])

    metric_types = [
        ("People",         "👤"),
        ("Virtual Line",   "📞"),
        ("Hunt Group",     "🔀"),
        ("Auto Attendant", "📟"),
        ("Paging Group",   "📢"),
        ("Device",         "💻"),
    ]
    cols = st.columns(len(metric_types))
    for col, (atype, icon) in zip(cols, metric_types):
        count = len(type_counts.get(atype, set()))
        col.metric(f"{icon} {atype}s", count)

    st.divider()

    # ── Preview dataframe ─────────────────────────────────────────────────────
    preview_df = pd.DataFrame([
        {
            "Asset Type": r["asset_type"],
            "Asset Name": r["asset_name"],
            "Field":      r["field"],
            "Old Value":  r["old_value"],
            "New Value":  r["new_value"],
        }
        for r in scan_rows
    ])
    st.dataframe(preview_df, use_container_width=True, height=400)

    st.info(
        "**Device display names** cannot be updated via API and are marked "
        "'Manual — Control Hub'. Update those directly in Webex Control Hub "
        "after this operation completes.",
        icon="ℹ️",
    )

    # ── Execute button inside confirmation expander ───────────────────────────
    with st.expander("⚠️ Confirm and Execute Renames", expanded=False):
        st.warning(
            f"This will rename **{len(set((r['asset_type'], r['asset_id']) for r in scan_rows))} assets** "
            f"from **{location_name}** → **{new_name}**. "
            "This action cannot be automatically undone.",
        )
        execute_btn = st.button(
            "✅ Execute Renames",
            type="primary",
            key="rs_execute_btn",
        )

    if execute_btn:
        # ── Execute logic ─────────────────────────────────────────────────────
        old_name   = location_name
        old_prefix = old_name.replace(" ", "_")
        new_prefix = new_name.replace(" ", "_")

        # Group rows by (asset_type, asset_id)
        groups: dict[tuple, list] = defaultdict(list)
        for row in scan_rows:
            groups[(row["asset_type"], row["asset_id"])].append(row)

        results: list[dict] = []
        total = len(groups)
        progress_bar = st.progress(0, text="Executing renames…")

        for i, ((asset_type, asset_id), group_rows) in enumerate(groups.items()):
            loc_id     = group_rows[0]["_location_id"]
            asset_name = group_rows[0]["asset_name"]

            # Devices are manual — skip
            if asset_type == "Device":
                for row in group_rows:
                    results.append({**row, "result_status": "⏭️ Skipped", "error": ""})
                progress_bar.progress((i + 1) / total, text=f"Skipping device: {asset_name}")
                continue

            progress_bar.progress((i + 1) / total, text=f"Updating {asset_type}: {asset_name}")

            try:
                if asset_type == "Person":
                    name_kwargs: dict = {}
                    email_repl:  dict = {}
                    for row in group_rows:
                        if row["field"] == "email":
                            email_repl[row["old_value"]] = row["new_value"]
                        else:
                            field_map = {
                                "displayName": "display_name",
                                "firstName":   "first_name",
                                "lastName":    "last_name",
                            }
                            if row["field"] in field_map:
                                name_kwargs[field_map[row["field"]]] = row["new_value"]
                    _people.update(
                        person_id=asset_id,
                        email_replacements=email_repl or None,
                        **name_kwargs,
                    )

                elif asset_type == "Virtual Line":
                    vl_kwargs: dict = {}
                    for row in group_rows:
                        field_map = {
                            "displayName": "display_name",
                            "firstName":   "first_name",
                            "lastName":    "last_name",
                        }
                        if row["field"] in field_map:
                            vl_kwargs[field_map[row["field"]]] = row["new_value"]
                    _virtual_lines.update(virtual_line_id=asset_id, **vl_kwargs)

                elif asset_type == "Hunt Group":
                    new_hg_name = next(
                        r["new_value"] for r in group_rows if r["field"] == "name"
                    )
                    _hunt_groups.update(loc_id, asset_id, name=new_hg_name)

                elif asset_type == "Auto Attendant":
                    new_aa_name = next(
                        r["new_value"] for r in group_rows if r["field"] == "name"
                    )
                    _auto_attendants.update(loc_id, asset_id, name=new_aa_name)

                elif asset_type == "Paging Group":
                    new_pg_name = next(
                        r["new_value"] for r in group_rows if r["field"] == "name"
                    )
                    _paging_groups.update(loc_id, asset_id, name=new_pg_name)

                audit_log(
                    action="rename_store_asset",
                    object_type=asset_type.lower().replace(" ", "_"),
                    object_id=asset_id,
                    object_name=asset_name,
                    details={
                        "old_store_name": old_name,
                        "new_store_name": new_name,
                        "location_id":    loc_id,
                        "changes": [
                            {"field": r["field"], "old": r["old_value"], "new": r["new_value"]}
                            for r in group_rows
                        ],
                    },
                    success=True,
                )
                for row in group_rows:
                    results.append({**row, "result_status": "✅ Updated", "error": ""})

            except WebexAPIError as e:
                audit_log(
                    action="rename_store_asset",
                    object_type=asset_type.lower().replace(" ", "_"),
                    object_id=asset_id,
                    object_name=asset_name,
                    details={
                        "old_store_name": old_name,
                        "new_store_name": new_name,
                        "location_id":    loc_id,
                        "error":          str(e),
                    },
                    success=False,
                    error_message=str(e),
                    tracking_id=getattr(e, "tracking_id", ""),
                )
                for row in group_rows:
                    results.append({**row, "result_status": "❌ Failed", "error": str(e)})

        progress_bar.empty()
        clear_all_caches()
        st.session_state["rs_execute_results"] = results
        st.session_state["rs_execute_done"]    = True
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Results
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["rs_execute_done"]:
    results   = st.session_state["rs_execute_results"]
    new_name  = st.session_state["rs_new_name"]

    st.subheader("Step 3 — Results")

    # ── Summary metrics ───────────────────────────────────────────────────────
    n_updated = sum(1 for r in results if r["result_status"] == "✅ Updated")
    n_failed  = sum(1 for r in results if r["result_status"] == "❌ Failed")
    n_skipped = sum(1 for r in results if r["result_status"] == "⏭️ Skipped")

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("✅ Updated", n_updated)
    mc2.metric("❌ Failed",  n_failed)
    mc3.metric("⏭️ Skipped (manual)", n_skipped)

    st.divider()

    # ── Results dataframe ─────────────────────────────────────────────────────
    results_df = pd.DataFrame([
        {
            "Status":     r["result_status"],
            "Asset Type": r["asset_type"],
            "Asset Name": r["asset_name"],
            "Field":      r["field"],
            "Old Value":  r["old_value"],
            "New Value":  r["new_value"],
            "Error":      r.get("error", ""),
        }
        for r in results
    ])
    st.dataframe(results_df, use_container_width=True, height=400)

    # ── Failure details ───────────────────────────────────────────────────────
    failures = [r for r in results if r["result_status"] == "❌ Failed"]
    if failures:
        with st.expander(f"❌ {len(failures)} failure(s) — details", expanded=True):
            for f in failures:
                st.error(
                    f"**{f['asset_type']}** `{f['asset_name']}` — field `{f['field']}`\n\n"
                    f"{f.get('error', 'Unknown error')}  \n"
                    f"Asset ID: `{f['asset_id']}`"
                )

    # ── CSV export ────────────────────────────────────────────────────────────
    export_data = [
        {
            "status":     r["result_status"],
            "asset_type": r["asset_type"],
            "asset_id":   r["asset_id"],
            "asset_name": r["asset_name"],
            "field":      r["field"],
            "old_value":  r["old_value"],
            "new_value":  r["new_value"],
            "error":      r.get("error", ""),
        }
        for r in results
    ]
    csv_bytes, filename = to_csv_bytes(export_data, "rename_store_results")
    st.download_button(
        label="⬇️ Download Results (CSV)",
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
    )

    st.divider()

    # ── Start Over ────────────────────────────────────────────────────────────
    if st.button("🔄 Start Over", key="rs_start_over"):
        _clear_rs()
        st.rerun()
