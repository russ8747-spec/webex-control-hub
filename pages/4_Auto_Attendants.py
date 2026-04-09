"""
pages/4_Auto_Attendants.py - View and create Auto Attendants.

Supports:
  - Viewing existing AAs by location
  - Creating Retail and/or Priority AAs from the standard template
  - Multi-location bulk creation with dry run
  - Exportable results log

Phone number is intentionally omitted at creation time — add it in Control Hub.
If the 'Open' schedule doesn't exist at a location it is auto-created (Mon–Fri 7:30am–6pm).
"""

from __future__ import annotations

import json
import streamlit as st
import pandas as pd

from utils.ui     import connection_status_badge, empty_state, api_error, section
from utils.cache  import (get_locations, get_hunt_groups,
                          get_schedules, get_auto_attendants, clear_all_caches)
from utils.export import to_csv_bytes
from utils.audit  import log as audit_log
from webex.auto_attendants import auto_attendants, AA_TEMPLATES, BUSINESS_SCHEDULE_NAME
from webex.schedules import schedules as _schedules
from webex.hunt_groups import hunt_groups as _hunt_groups
from webex.client import WebexAPIError

st.set_page_config(
    page_title="Auto Attendants — Control Hub",
    page_icon="📟",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📟 Auto Attendants")
    connection_status_badge()
    st.divider()

    try:
        all_locs    = get_locations()
        loc_map     = {loc["name"]: loc for loc in all_locs}
        loc_names   = list(loc_map.keys())
    except Exception as e:
        st.error("Could not load locations.")
        loc_map, loc_names = {}, []

st.title("📟 Auto Attendants")
tab_view, tab_create = st.tabs(["📋 View Existing", "➕ Create New"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — View existing AAs
# ══════════════════════════════════════════════════════════════════════════════
with tab_view:
    section("Existing Auto Attendants")

    col_loc, col_btn = st.columns([3, 1])
    with col_loc:
        default_name = st.session_state.get("active_location_name", loc_names[0] if loc_names else "")
        default_idx  = loc_names.index(default_name) if default_name in loc_names else 0
        view_loc_name = st.selectbox("📍 Select Location", loc_names, index=default_idx, key="view_loc")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh_view = st.button("🔄 Load", key="refresh_view", use_container_width=True)

    if refresh_view and view_loc_name:
        get_auto_attendants.clear()

    if view_loc_name:
        view_loc = loc_map[view_loc_name]
        try:
            aas = get_auto_attendants(location_id=view_loc["id"])
        except Exception as e:
            api_error(e)
            aas = []

        if not aas:
            empty_state(f"No auto attendants found for {view_loc_name}.", "📟")
        else:
            st.metric("Auto Attendants found", len(aas))

            rows = []
            for aa in aas:
                rows.append({
                    "Name":       aa.get("name", "—"),
                    "Phone":      aa.get("phoneNumber", "—"),
                    "Extension":  aa.get("extension", "—"),
                    "Language":   aa.get("languageCode", "—"),
                    "Enabled":    "✅" if aa.get("enabled", True) else "❌",
                    "ID":         aa.get("id", ""),
                })

            selected = st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                height=400,
                on_select="rerun",
                selection_mode="single-row",
            )

            if selected and selected.get("selection", {}).get("rows"):
                row_idx = selected["selection"]["rows"][0]
                aa      = aas[row_idx]
                aa_id   = aa.get("id", "")

                with st.expander("📋 AA Details", expanded=True):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**Name:** {aa.get('name','—')}")
                    c1.markdown(f"**Phone:** {aa.get('phoneNumber','—')}")
                    c1.markdown(f"**Extension:** {aa.get('extension','—')}")
                    c2.markdown(f"**Language:** {aa.get('languageCode','—')}")
                    c2.markdown(f"**Timezone:** {aa.get('timeZone','—')}")
                    c2.markdown(f"**Schedule:** {aa.get('businessSchedule',{}).get('name','—') if isinstance(aa.get('businessSchedule'), dict) else aa.get('businessSchedule','—')}")
                    st.markdown("**ID:**")
                    st.code(aa_id, language=None)

                    # Show alternate numbers if any
                    alts = aa.get("alternateNumbers", [])
                    if alts:
                        st.markdown("**Alternate Numbers:**")
                        for alt in alts:
                            st.markdown(f"- `{alt.get('phoneNumber','')}` ({alt.get('ringPattern','NORMAL')})")

                # ── Edit form ─────────────────────────────────────────────────
                with st.expander("✏️ Edit This AA", expanded=False):
                    st.caption("Only fill in the fields you want to change. Blank fields are left as-is.")
                    ef1, ef2 = st.columns(2)

                    new_name = ef1.text_input(
                        "New Name",
                        value=aa.get("name", ""),
                        key=f"edit_name_{aa_id}",
                    )
                    new_phone = ef1.text_input(
                        "New Phone Number (E.164)",
                        value=aa.get("phoneNumber", ""),
                        key=f"edit_phone_{aa_id}",
                        placeholder="+12025551234",
                    )
                    new_ext = ef2.text_input(
                        "New Extension",
                        value=str(aa.get("extension", "")),
                        key=f"edit_ext_{aa_id}",
                    )
                    new_tz = ef2.text_input(
                        "Timezone (IANA)",
                        value=aa.get("timeZone", ""),
                        key=f"edit_tz_{aa_id}",
                        placeholder="America/Chicago",
                    )

                    # Schedule selector: list known schedules for this location
                    try:
                        loc_scheds = get_schedules(view_loc["id"])
                        sched_names = [s["name"] for s in loc_scheds if s.get("type", "").upper() == "BUSINESS_HOURS"]
                    except Exception:
                        sched_names = []

                    current_sched = (
                        aa.get("businessSchedule", {}).get("name", "")
                        if isinstance(aa.get("businessSchedule"), dict)
                        else aa.get("businessSchedule", "")
                    )
                    if current_sched and current_sched not in sched_names:
                        sched_names.insert(0, current_sched)

                    new_sched = ef1.selectbox(
                        "Business Schedule",
                        sched_names or ["(no schedules found)"],
                        index=sched_names.index(current_sched) if current_sched in sched_names else 0,
                        key=f"edit_sched_{aa_id}",
                    )

                    save_btn = st.button(
                        "💾 Save Changes",
                        key=f"edit_save_{aa_id}",
                        type="primary",
                    )

                    if save_btn:
                        update_kwargs: dict = {}
                        if new_name != aa.get("name"):
                            update_kwargs["name"] = new_name
                        if new_phone != aa.get("phoneNumber", ""):
                            update_kwargs["phone_number"] = new_phone
                        if new_ext != str(aa.get("extension", "")):
                            update_kwargs["extension"] = new_ext
                        if new_tz != aa.get("timeZone", ""):
                            update_kwargs["time_zone"] = new_tz
                        if new_sched != current_sched and sched_names:
                            update_kwargs["business_schedule"] = new_sched

                        if not update_kwargs:
                            st.info("No changes detected.")
                        else:
                            try:
                                auto_attendants.update(
                                    location_id=view_loc["id"],
                                    auto_attendant_id=aa_id,
                                    **update_kwargs,
                                )
                                audit_log(
                                    action="update_auto_attendant",
                                    object_type="auto_attendant",
                                    object_id=aa_id,
                                    object_name=new_name,
                                    details=update_kwargs,
                                    success=True,
                                )
                                st.success("Auto attendant updated.")
                                get_auto_attendants.clear()
                                st.rerun()
                            except WebexAPIError as e:
                                audit_log(
                                    action="update_auto_attendant",
                                    object_type="auto_attendant",
                                    object_id=aa_id,
                                    object_name=aa.get("name", ""),
                                    details={"error": str(e), "changes": update_kwargs},
                                    success=False,
                                    error_message=str(e),
                                    tracking_id=getattr(e, "tracking_id", ""),
                                )
                                api_error(e)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Create new AAs
# ══════════════════════════════════════════════════════════════════════════════
with tab_create:

    # ── Step 1: Select locations + type ──────────────────────────────────────
    section(
        "Step 1 — Select Locations & Type",
        "Choose one or more locations and which AA type(s) to create.",
    )

    s1c1, s1c2, s1c3 = st.columns([3, 1, 1])
    with s1c1:
        selected_loc_names = st.multiselect(
            "📍 Locations",
            loc_names,
            default=[st.session_state.get("active_location_name", "")] if st.session_state.get("active_location_name") in loc_names else [],
            placeholder="Search and select one or more locations…",
        )
    with s1c2:
        aa_type_choice = st.selectbox(
            "AA Type",
            ["Retail", "Priority", "Both"],
            help="Retail = extension 5004, key 1 → 4000\nPriority = extension 5005, key 1 → 4001",
        )
    with s1c3:
        greeting_choice = st.selectbox(
            "Greeting",
            ["CUSTOM", "DEFAULT"],
            help=(
                "CUSTOM = Napa Auto Attendant Generic v2.wav (must exist in org media library).\n"
                "DEFAULT = Webex built-in greeting. Use DEFAULT if CUSTOM fails, "
                "then set the audio in Control Hub afterward."
            ),
        )

    types_to_create = (
        ["Retail", "Priority"] if aa_type_choice == "Both" else [aa_type_choice]
    )

    load_btn = st.button(
        "🔍 Load Location Data",
        type="primary",
        disabled=not selected_loc_names,
    )

    # Build preview rows on Load — also resets schedule and dry-run state
    if load_btn and selected_loc_names:
        st.session_state.aa_preview_rows  = []
        st.session_state.schedule_results = []
        st.session_state.dry_run_results  = []

        with st.spinner("Loading data for selected locations…"):
            for loc_name in selected_loc_names:
                loc      = loc_map[loc_name]
                loc_id   = loc["id"]
                timezone = loc.get("timeZone", "America/Chicago")

                for aa_type in types_to_create:
                    tmpl = AA_TEMPLATES[aa_type]
                    row  = {
                        "loc_id":      loc_id,
                        "loc_name":    loc_name,
                        "aa_type":     aa_type,
                        "aa_name":     f"{loc_name} {tmpl['suffix']}",
                        "extension":   tmpl["extension"],
                        "transfer_to": tmpl["transfer_ext"],
                        "timezone":    timezone,
                        "greeting":    greeting_choice,
                        "schedule_ok": False,
                        "hg_name":     "",
                        "hg_phone":    "",
                    }

                    try:
                        location_schedules = get_schedules(loc_id)
                        open_sched = next(
                            (s for s in location_schedules
                             if s.get("name", "").lower() == BUSINESS_SCHEDULE_NAME.lower()),
                            None,
                        )
                        row["schedule_ok"] = bool(open_sched)
                    except Exception:
                        row["schedule_ok"] = False

                    try:
                        all_hgs = get_hunt_groups(loc_id)
                        hg = None
                        for h in all_hgs:
                            if str(h.get("extension", "")) == tmpl["transfer_ext"]:
                                hg = h
                                break
                        if not hg:
                            keyword = aa_type.lower()
                            for h in all_hgs:
                                if keyword in h.get("name", "").lower():
                                    hg = h
                                    break
                        if hg:
                            try:
                                hg = _hunt_groups.get(loc_id, hg["id"])
                            except Exception:
                                pass
                            row["hg_name"]  = hg.get("name", "")
                            row["hg_phone"] = hg.get("phoneNumber", "")
                    except Exception:
                        pass

                    st.session_state.aa_preview_rows.append(row)

    # ─────────────────────────────────────────────────────────────────────────
    if st.session_state.get("aa_preview_rows"):
        rows = st.session_state.aa_preview_rows

        # ── Step 2: Review ────────────────────────────────────────────────────
        st.divider()
        section(
            "Step 2 — Review",
            "Verify the details below. Phone number is omitted at creation — add it in Control Hub afterward.",
        )

        for row in rows:
            greeting_label = (
                "CUSTOM — Napa Auto Attendant Generic v2.wav"
                if row.get("greeting") == "CUSTOM"
                else "DEFAULT (Webex built-in)"
            )
            sched_icon = "✅" if row["schedule_ok"] else "⚠️"
            with st.expander(
                f"{sched_icon} **{row['aa_name']}** — {row['loc_name']} ({row['aa_type']})",
                expanded=False,
            ):
                ec1, ec2 = st.columns(2)
                ec1.markdown(f"**AA Name:** {row['aa_name']}")
                ec1.markdown(f"**Extension:** {row['extension']}")
                ec1.markdown(f"**Key 1 → extension:** {row['transfer_to']}")
                ec1.markdown(f"**Phone Number:** *(none — add manually in Control Hub)*")
                ec2.markdown(f"**Timezone:** {row['timezone']}")
                sched_label = (
                    "✅ Exists"
                    if row["schedule_ok"]
                    else "⚠️ Missing — will be created in Step 3"
                )
                ec2.markdown(f"**Schedule '{BUSINESS_SCHEDULE_NAME}':** {sched_label}")
                ec2.markdown(f"**Greeting:** {greeting_label}")
                if row["hg_name"]:
                    st.caption(
                        f"Hunt group reference: **{row['hg_name']}** "
                        f"(ext {row['transfer_to']}"
                        + (f", {row['hg_phone']}" if row["hg_phone"] else "")
                        + ") — Key 1 on the AA will forward here."
                    )

        # ── Step 3: Schedule Setup ─────────────────────────────────────────────
        st.divider()

        # Collect unique locations that are still missing the schedule
        missing_locs = {}
        for row in rows:
            if not row["schedule_ok"] and row["loc_id"] not in missing_locs:
                missing_locs[row["loc_id"]] = row["loc_name"]

        all_schedules_ok = len(missing_locs) == 0

        if all_schedules_ok:
            section("Step 3 — Schedule Setup", "")
            st.success(
                f"✅ All locations have the **'{BUSINESS_SCHEDULE_NAME}'** "
                "business hours schedule. Ready to proceed."
            )
        else:
            section(
                "Step 3 — Schedule Setup",
                f"**{len(missing_locs)} location(s)** are missing the "
                f"**'{BUSINESS_SCHEDULE_NAME}'** schedule (Mon–Fri 7:30am–6pm). "
                "Create and verify them here before building the Auto Attendants.",
            )

            # Show a status table of what's missing
            st.dataframe(
                pd.DataFrame([
                    {"Location": loc_name, "Schedule": BUSINESS_SCHEDULE_NAME, "Status": "⚠️ Missing"}
                    for loc_name in missing_locs.values()
                ]),
                use_container_width=True,
                hide_index=True,
            )

            create_scheds_btn = st.button(
                f"📅 Create '{BUSINESS_SCHEDULE_NAME}' for {len(missing_locs)} Location(s)",
                type="primary",
            )

            if create_scheds_btn:
                sched_log = []
                s_prog    = st.progress(0)
                total     = len(missing_locs)

                for i, (loc_id, loc_name) in enumerate(missing_locs.items()):
                    try:
                        _schedules.create_business_hours(
                            location_id=loc_id,
                            name=BUSINESS_SCHEDULE_NAME,
                        )
                        # Verify via a fresh API call — don't trust the POST alone
                        get_schedules.clear()
                        fresh_scheds = _schedules.list(loc_id)
                        verified = any(
                            s.get("name", "").lower() == BUSINESS_SCHEDULE_NAME.lower()
                            for s in fresh_scheds
                        )
                        if verified:
                            for row in st.session_state.aa_preview_rows:
                                if row["loc_id"] == loc_id:
                                    row["schedule_ok"] = True
                            sched_log.append({
                                "Location": loc_name,
                                "Status":   "✅ Created & verified",
                                "Detail":   "",
                            })
                            audit_log(
                                action="create_schedule",
                                object_type="schedule",
                                object_id="",
                                object_name=BUSINESS_SCHEDULE_NAME,
                                details={"location": loc_name, "hours": "Mon–Fri 07:30–18:00"},
                                success=True,
                            )
                        else:
                            sched_log.append({
                                "Location": loc_name,
                                "Status":   "⚠️ Created but not confirmed on re-check",
                                "Detail":   "Schedule may take a moment — try reloading.",
                            })
                    except WebexAPIError as sched_err:
                        sched_log.append({
                            "Location": loc_name,
                            "Status":   "❌ Failed",
                            "Detail":   str(sched_err),
                        })
                        audit_log(
                            action="create_schedule",
                            object_type="schedule",
                            object_id="",
                            object_name=BUSINESS_SCHEDULE_NAME,
                            details={"location": loc_name, "error": str(sched_err)},
                            success=False,
                            error_message=str(sched_err),
                            tracking_id=getattr(sched_err, "tracking_id", ""),
                        )
                    s_prog.progress((i + 1) / total)

                st.session_state.schedule_results = sched_log
                st.rerun()

            # Show schedule creation results from a previous run
            if st.session_state.get("schedule_results"):
                st.markdown("**Schedule creation results:**")
                for r in st.session_state.schedule_results:
                    if "✅" in r["Status"]:
                        st.success(f"**{r['Location']}** — {r['Status']}")
                    elif "⚠️" in r["Status"]:
                        st.warning(f"**{r['Location']}** — {r['Status']}. {r['Detail']}")
                    else:
                        st.error(f"**{r['Location']}** — {r['Status']}: {r['Detail']}")

        # Steps 4 and 5 are locked until all schedules are confirmed
        if not all_schedules_ok:
            st.divider()
            st.info(
                "Complete **Step 3** above — create all missing schedules — "
                "before proceeding to the dry run and creation steps.",
                icon="🔒",
            )

        else:
            # ── Step 4: Dry Run ───────────────────────────────────────────────
            st.divider()
            section(
                "Step 4 — Dry Run",
                "See exactly what will be sent to the Webex API before committing.",
            )

            dry_run_btn = st.button("🧪 Run Dry Run", use_container_width=False)

            if dry_run_btn:
                dry_results = []
                for row in rows:
                    try:
                        payload = auto_attendants.create_from_template(
                            location_id=row["loc_id"],
                            location_name=row["loc_name"],
                            aa_type=row["aa_type"],
                            time_zone=row["timezone"],
                            phone_number=None,
                            schedule_ok=True,   # confirmed in Step 3
                            greeting=row.get("greeting", "DEFAULT"),
                            dry_run=True,
                        )
                        dry_results.append({
                            "AA Name":  row["aa_name"],
                            "Status":   "✅ Ready",
                            "Payload":  json.dumps(payload, indent=2),
                        })
                    except Exception as ex:
                        dry_results.append({
                            "AA Name":  row["aa_name"],
                            "Status":   f"⛔ Error: {ex}",
                            "Payload":  "—",
                        })
                st.session_state.dry_run_results = dry_results

            if st.session_state.get("dry_run_results"):
                for result in st.session_state.dry_run_results:
                    color = "green" if "✅" in result["Status"] else "red"
                    st.markdown(f"**{result['AA Name']}** — :{color}[{result['Status']}]")
                    if result["Payload"] != "—":
                        with st.expander("View API payload"):
                            st.code(result["Payload"], language="json")

            # ── Step 5: Create Auto Attendants ────────────────────────────────
            st.divider()
            section(
                "Step 5 — Create Auto Attendants",
                "Schedules are confirmed. Click to create the auto attendants in Webex.",
            )

            st.info(
                f"**{len(rows)} Auto Attendant(s)** ready — extension only, no phone number. "
                "Add phone numbers in Control Hub after creation.",
                icon="ℹ️",
            )

            create_btn = st.button(
                f"🚀 Create {len(rows)} Auto Attendant(s)",
                type="primary",
                disabled=len(rows) == 0,
            )

            if create_btn:
                results_log = []
                progress    = st.progress(0)
                status_box  = st.empty()

                for idx, row in enumerate(rows):
                    status_box.info(f"Creating **{row['aa_name']}**…")
                    try:
                        result = auto_attendants.create_from_template(
                            location_id=row["loc_id"],
                            location_name=row["loc_name"],
                            aa_type=row["aa_type"],
                            time_zone=row["timezone"],
                            phone_number=None,
                            schedule_ok=True,   # confirmed in Step 3
                            greeting=row.get("greeting", "DEFAULT"),
                            dry_run=False,
                        )
                        new_id = result.get("id", "")
                        results_log.append({
                            "AA Name":   row["aa_name"],
                            "Location":  row["loc_name"],
                            "Type":      row["aa_type"],
                            "Extension": row["extension"],
                            "Phone":     "(none)",
                            "Schedule":  "✅ Confirmed",
                            "Status":    "✅ Created",
                            "AA ID":     new_id,
                            "Error":     "",
                        })
                        audit_log(
                            action="create_auto_attendant",
                            object_type="auto_attendant",
                            object_id=new_id,
                            object_name=row["aa_name"],
                            details={
                                "location":  row["loc_name"],
                                "type":      row["aa_type"],
                                "extension": row["extension"],
                                "phone":     "none",
                            },
                            success=True,
                        )
                    except WebexAPIError as ex:
                        results_log.append({
                            "AA Name":   row["aa_name"],
                            "Location":  row["loc_name"],
                            "Type":      row["aa_type"],
                            "Extension": row["extension"],
                            "Phone":     "(none)",
                            "Schedule":  "✅ Confirmed",
                            "Status":    "❌ Failed",
                            "AA ID":     "",
                            "Error":     str(ex),
                        })
                        audit_log(
                            action="create_auto_attendant",
                            object_type="auto_attendant",
                            object_id="",
                            object_name=row["aa_name"],
                            details={"error": str(ex)},
                            success=False,
                            error_message=str(ex),
                            tracking_id=getattr(ex, "tracking_id", ""),
                        )
                    progress.progress((idx + 1) / len(rows))

                status_box.empty()
                clear_all_caches()

                created = sum(1 for r in results_log if "✅ Created" in r["Status"])
                failed  = sum(1 for r in results_log if "❌" in r["Status"])

                if created:
                    st.success(f"✅ {created} auto attendant(s) created. Add phone numbers in Control Hub.")
                if failed:
                    st.error(f"❌ {failed} failed. See details below.")

                st.dataframe(pd.DataFrame(results_log), use_container_width=True)

                csv_bytes, filename = to_csv_bytes(results_log, "aa_creation_results")
                st.download_button(
                    label="⬇️ Download Results Log (CSV)",
                    data=csv_bytes,
                    file_name=filename,
                    mime="text/csv",
                )

                # Reset so the user starts fresh for the next batch
                st.session_state.aa_preview_rows  = []
                st.session_state.schedule_results = []
                st.session_state.dry_run_results  = []

    else:
        if not load_btn:
            st.info("Select locations above and click **Load Location Data** to begin.")
