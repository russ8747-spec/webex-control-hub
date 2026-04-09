"""
pages/6_Hunt_Groups.py - Hunt Group inventory and AA readiness checker.

Two tabs:
  1. Single Location  — browse all HGs for one location; unassign phone number
                        to prep for AA creation; see which AAs already exist.
  2. Readiness Scan   — bulk-scan multiple locations and produce a table showing
                        whether each location has Retail/Priority HGs at ext
                        4000/4001 and matching AAs at ext 5004/5005.

Why this page exists:
  Before creating Auto Attendants the phone number held by the Retail (4000)
  or Priority (4001) hunt group must be freed.  This page is the companion
  to pages/4_Auto_Attendants.py for diagnosing exactly which locations still
  need AA creation work.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from utils.ui          import connection_status_badge, empty_state, api_error, section
from utils.cache       import get_locations, get_hunt_groups, get_auto_attendants
from utils.export      import to_csv_bytes
from utils.audit       import log as audit_log
from webex.hunt_groups import hunt_groups as _hunt_groups
from webex.client      import WebexAPIError
from webex.auto_attendants import AA_TEMPLATES

# Extension constants derived from the shared AA template config
_RETAIL_EXT      = AA_TEMPLATES["Retail"]["transfer_ext"]   # "4000"
_PRIORITY_EXT    = AA_TEMPLATES["Priority"]["transfer_ext"]  # "4001"
_RETAIL_AA_EXT   = AA_TEMPLATES["Retail"]["extension"]       # "5004"
_PRIORITY_AA_EXT = AA_TEMPLATES["Priority"]["extension"]     # "5005"

# Status strings used in the scan table (must match filter options below)
_S_BOTH     = "✅ Both AAs exist"
_S_NEEDED   = "🔶 HGs exist, AAs needed"
_S_PARTIAL  = "⚠️ Partial — 1 AA missing"
_S_NO_HG    = "❌ No HGs at 4000/4001"

st.set_page_config(
    page_title="Hunt Groups — Control Hub",
    page_icon="🔀",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔀 Hunt Groups")
    connection_status_badge()
    st.divider()

    try:
        all_locs  = get_locations()
        loc_map   = {loc["name"]: loc for loc in all_locs}
        loc_names = list(loc_map.keys())
    except Exception as e:
        st.error("Could not load locations.")
        loc_map, loc_names = {}, []

    st.caption(f"{len(loc_names):,} total locations loaded")

st.title("🔀 Hunt Groups & AA Readiness")
st.caption(
    "Browse hunt groups by location and check whether the standard Retail (4000) "
    "and Priority (4001) hunt groups exist, and whether the matching Auto Attendants "
    "(5004/5005) have already been created."
)
st.divider()

tab_single, tab_scan = st.tabs(["📍 Single Location", "🔍 Readiness Scan"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Single location HG browser
# ══════════════════════════════════════════════════════════════════════════════
with tab_single:
    section(
        "Hunt Groups by Location",
        "View all hunt groups for one location. Retail (4000) and Priority (4001) "
        "rows show whether the corresponding Auto Attendant already exists.",
    )

    col_loc, col_btn = st.columns([3, 1])
    with col_loc:
        default_name = st.session_state.get("active_location_name", loc_names[0] if loc_names else "")
        default_idx  = loc_names.index(default_name) if default_name in loc_names else 0
        single_loc_name = st.selectbox(
            "📍 Select Location", loc_names, index=default_idx, key="hg_single_loc"
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        load_single = st.button("🔄 Load", key="hg_single_load", use_container_width=True)

    if load_single:
        get_hunt_groups.clear()
        get_auto_attendants.clear()

    if single_loc_name:
        loc    = loc_map[single_loc_name]
        loc_id = loc["id"]

        try:
            hgs = get_hunt_groups(location_id=loc_id)
        except Exception as e:
            api_error(e)
            hgs = []

        try:
            aas = get_auto_attendants(location_id=loc_id)
        except Exception as e:
            aas = []

        aa_exts = {str(aa.get("extension", "")) for aa in aas}

        if not hgs:
            empty_state(f"No hunt groups found for {single_loc_name}.", "🔀")
        else:
            c_metric1, c_metric2, c_metric3 = st.columns(3)
            c_metric1.metric("Total Hunt Groups", len(hgs))
            c_metric2.metric(
                "Retail HG (4000)",
                "✅ Found" if any(str(h.get("extension","")) == _RETAIL_EXT for h in hgs) else "—",
            )
            c_metric3.metric(
                "Priority HG (4001)",
                "✅ Found" if any(str(h.get("extension","")) == _PRIORITY_EXT for h in hgs) else "—",
            )

            st.divider()

            rows = []
            for hg in hgs:
                ext = str(hg.get("extension", ""))
                if ext == _RETAIL_EXT:
                    hg_type = f"Retail ({_RETAIL_EXT})"
                    aa_ext  = _RETAIL_AA_EXT
                elif ext == _PRIORITY_EXT:
                    hg_type = f"Priority ({_PRIORITY_EXT})"
                    aa_ext  = _PRIORITY_AA_EXT
                else:
                    hg_type = "—"
                    aa_ext  = ""

                aa_status = ""
                if aa_ext:
                    aa_status = "✅ AA exists" if aa_ext in aa_exts else "⚠️ No AA yet"

                rows.append({
                    "Name":       hg.get("name", "—"),
                    "Extension":  ext,
                    "Type":       hg_type,
                    "Phone":      hg.get("phoneNumber", "—"),
                    "Enabled":    "✅" if hg.get("enabled", True) else "❌",
                    "AA Status":  aa_status,
                    "ID":         hg.get("id", ""),
                })

            selected = st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                height=min(500, 80 + 35 * len(rows)),
                on_select="rerun",
                selection_mode="single-row",
            )

            # ── Detail + unassign for selected HG ─────────────────────────────
            if selected and selected.get("selection", {}).get("rows"):
                row_idx = selected["selection"]["rows"][0]
                hg_row  = hgs[row_idx]
                hg_id   = hg_row.get("id", "")

                # Fetch full detail to ensure we have the phoneNumber field
                try:
                    hg_row = _hunt_groups.get(loc_id, hg_id)
                except Exception:
                    pass

                with st.expander("📋 Hunt Group Details", expanded=True):
                    d1, d2 = st.columns(2)
                    d1.markdown(f"**Name:** {hg_row.get('name','—')}")
                    d1.markdown(f"**Extension:** {hg_row.get('extension','—')}")
                    d1.markdown(f"**Phone Number:** {hg_row.get('phoneNumber','—')}")
                    d1.markdown(f"**Policy:** {hg_row.get('policy','—')}")
                    d2.markdown(f"**Enabled:** {'✅' if hg_row.get('enabled', True) else '❌'}")
                    d2.markdown(f"**Language:** {hg_row.get('languageCode','—')}")
                    d2.markdown(f"**Timezone:** {hg_row.get('timeZone','—')}")
                    st.markdown("**ID:**")
                    st.code(hg_id, language=None)

                    if hg_row.get("phoneNumber"):
                        st.warning(
                            f"**{hg_row['phoneNumber']}** is currently assigned to this hunt group. "
                            "To move this number to an Auto Attendant, unassign it here first."
                        )

                        if st.button(
                            f"🔓 Unassign {hg_row['phoneNumber']} from Hunt Group",
                            key=f"hg_unassign_{hg_id}",
                            type="primary",
                        ):
                            with st.spinner("Unassigning phone number…"):
                                try:
                                    _hunt_groups.clear_phone_number(
                                        location_id=loc_id,
                                        hunt_group_id=hg_id,
                                    )
                                    audit_log(
                                        action="unassign_hg_phone_number",
                                        object_type="hunt_group",
                                        object_id=hg_id,
                                        object_name=hg_row.get("name", ""),
                                        details={
                                            "location":     single_loc_name,
                                            "phone_number": hg_row["phoneNumber"],
                                        },
                                        success=True,
                                    )
                                    st.success(
                                        f"✅ **{hg_row['phoneNumber']}** unassigned from "
                                        f"**{hg_row.get('name','')}**. "
                                        "You can now create the Auto Attendant."
                                    )
                                    get_hunt_groups.clear()
                                    st.rerun()
                                except WebexAPIError as e:
                                    audit_log(
                                        action="unassign_hg_phone_number",
                                        object_type="hunt_group",
                                        object_id=hg_id,
                                        object_name=hg_row.get("name", ""),
                                        details={"error": str(e)},
                                        success=False,
                                        error_message=str(e),
                                        tracking_id=getattr(e, "tracking_id", ""),
                                    )
                                    api_error(e)
                    else:
                        st.success("No phone number assigned — this hunt group is ready.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Multi-location readiness scan
# ══════════════════════════════════════════════════════════════════════════════
with tab_scan:
    section(
        "AA Readiness Scan",
        "Select locations and scan to see which ones have Retail/Priority hunt groups "
        "and whether Auto Attendants have already been created at those locations.",
    )

    s1c1, s1c2 = st.columns([4, 1])
    with s1c1:
        scan_locs = st.multiselect(
            "📍 Locations to scan",
            loc_names,
            placeholder="Search and select locations…",
            key="hg_scan_locs",
        )
    with s1c2:
        st.markdown("<br>", unsafe_allow_html=True)
        scan_btn = st.button(
            "🔍 Run Scan",
            type="primary",
            disabled=not scan_locs,
            use_container_width=True,
            key="hg_scan_btn",
        )

    if scan_btn and scan_locs:
        scan_results = []
        progress     = st.progress(0)
        status_box   = st.empty()

        for idx, loc_name in enumerate(scan_locs):
            status_box.info(f"Scanning **{loc_name}** ({idx + 1}/{len(scan_locs)})…")
            loc    = loc_map[loc_name]
            loc_id = loc["id"]

            try:
                hgs = get_hunt_groups(location_id=loc_id)
            except Exception:
                hgs = []

            try:
                aas = get_auto_attendants(location_id=loc_id)
            except Exception:
                aas = []

            aa_exts = {str(aa.get("extension", "")) for aa in aas}

            # Find the retail and priority hunt groups by extension
            retail_hg   = next((h for h in hgs if str(h.get("extension", "")) == _RETAIL_EXT),   None)
            priority_hg = next((h for h in hgs if str(h.get("extension", "")) == _PRIORITY_EXT), None)

            # The list endpoint often omits phoneNumber — fetch full detail when needed
            if retail_hg and not retail_hg.get("phoneNumber"):
                try:
                    retail_hg = _hunt_groups.get(loc_id, retail_hg["id"])
                except Exception:
                    pass
            if priority_hg and not priority_hg.get("phoneNumber"):
                try:
                    priority_hg = _hunt_groups.get(loc_id, priority_hg["id"])
                except Exception:
                    pass

            retail_aa_ok   = _RETAIL_AA_EXT in aa_exts
            priority_aa_ok = _PRIORITY_AA_EXT in aa_exts

            # Determine overall readiness status
            if retail_aa_ok and priority_aa_ok:
                status = _S_BOTH
            elif not retail_hg and not priority_hg:
                status = _S_NO_HG
            elif retail_aa_ok or priority_aa_ok:
                status = _S_PARTIAL
            else:
                status = _S_NEEDED

            scan_results.append({
                "Location":           loc_name,
                "Retail HG (4000)":   retail_hg.get("name", "—")          if retail_hg   else "—",
                "Retail Phone":       retail_hg.get("phoneNumber", "—")    if retail_hg   else "—",
                "Retail AA (5004)":   "✅" if retail_aa_ok   else "—",
                "Priority HG (4001)": priority_hg.get("name", "—")         if priority_hg else "—",
                "Priority Phone":     priority_hg.get("phoneNumber", "—")  if priority_hg else "—",
                "Priority AA (5005)": "✅" if priority_aa_ok else "—",
                "Status":             status,
            })

            progress.progress((idx + 1) / len(scan_locs))

        status_box.empty()
        progress.empty()
        st.session_state["hg_scan_results"] = scan_results

    # ── Show scan results ─────────────────────────────────────────────────────
    if st.session_state.get("hg_scan_results"):
        results = st.session_state["hg_scan_results"]
        df_full = pd.DataFrame(results)

        st.divider()

        # Summary metrics
        total       = len(results)
        both_aa     = sum(1 for r in results if r["Status"] == _S_BOTH)
        hgs_no_aa   = sum(1 for r in results if r["Status"] == _S_NEEDED)
        partial     = sum(1 for r in results if r["Status"] == _S_PARTIAL)
        no_hg       = sum(1 for r in results if r["Status"] == _S_NO_HG)

        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Locations Scanned",  total)
        mc2.metric("✅ Both AAs exist",  both_aa)
        mc3.metric("🔶 AAs needed",      hgs_no_aa)
        mc4.metric("⚠️ Partial",         partial)
        mc5.metric("❌ No HGs",          no_hg)

        st.divider()

        # Filter
        filter_opts = [
            "All",
            _S_BOTH,
            _S_NEEDED,
            _S_PARTIAL,
            _S_NO_HG,
        ]
        filter_status = st.selectbox(
            "Filter by status",
            filter_opts,
            key="hg_scan_filter",
        )

        df_display = df_full if filter_status == "All" else df_full[df_full["Status"] == filter_status]

        st.caption(f"Showing {len(df_display):,} of {total:,} locations")
        st.dataframe(df_display, use_container_width=True, height=500)

        st.divider()
        csv_bytes, filename = to_csv_bytes(results, "hg_readiness_scan")
        st.download_button(
            label="⬇️ Export Scan Results (CSV)",
            data=csv_bytes,
            file_name=filename,
            mime="text/csv",
        )

    else:
        if not scan_btn:
            st.info(
                "Select one or more locations above and click **Run Scan** to check "
                "which locations have Retail/Priority hunt groups and AA readiness."
            )
