"""
pages/3_Line_Layout_Manager.py - View and edit device line configurations.

Shows what user/workspace is assigned to each button on a Webex phone,
and lets you remove lines or reassign a shared line appearance.

Endpoint used:
  GET /v1/telephony/config/devices/{id}/members   - read line layout
  PUT /v1/telephony/config/devices/{id}/members   - write line layout
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from utils.ui     import connection_status_badge, empty_state, api_error, section
from utils.audit  import log as audit_log
from webex.devices import devices as _devices
from webex.client  import WebexAPIError

st.set_page_config(
    page_title="Line Layout Manager — Control Hub",
    page_icon="📱",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📱 Line Layout Manager")
    connection_status_badge()
    st.divider()
    st.caption(
        "Search for a phone by MAC address, serial number, or display name "
        "to view and manage its line button layout."
    )

st.title("📱 Line Layout Manager")
st.caption(
    "View and edit which users or workspaces are assigned to each button on a "
    "Webex desk phone. Changes take effect after the phone reboots."
)
st.divider()

# ── Search bar ────────────────────────────────────────────────────────────────
section("Find a Device", "Search by MAC address, serial number, or display name.")

col_search, col_type, col_btn = st.columns([3, 2, 1])

with col_search:
    search_val = st.text_input(
        "Search value",
        placeholder="e.g. 00:50:56:AB:CD:EF  or  FHH12345678  or  Reception Phone",
        label_visibility="collapsed",
    )

with col_type:
    search_type = st.selectbox(
        "Search by",
        ["Display Name", "MAC Address", "Serial Number"],
        label_visibility="collapsed",
    )

with col_btn:
    search_btn = st.button("🔍 Search", use_container_width=True, type="primary")


# ── Search results ────────────────────────────────────────────────────────────
if search_btn and search_val:
    with st.spinner("Searching devices…"):
        try:
            kwargs: dict = {}
            if search_type == "MAC Address":
                kwargs["mac"] = search_val.replace(":", "").replace("-", "").upper()
            elif search_type == "Serial Number":
                kwargs["serial"] = search_val
            else:
                kwargs["display_name"] = search_val

            found_devices = _devices.list(**kwargs)
        except WebexAPIError as e:
            api_error(e)
            found_devices = []

    if not found_devices:
        empty_state("No devices found. Try a different search term.", "📱")
    else:
        st.success(f"Found **{len(found_devices)}** device(s).")
        st.session_state["llm_devices"] = found_devices

# ── Device picker ─────────────────────────────────────────────────────────────
if st.session_state.get("llm_devices"):
    found_devices = st.session_state["llm_devices"]

    device_options = {
        f"{d.get('displayName','(unnamed)')}  [{d.get('mac', d.get('serial',''))}]": d
        for d in found_devices
    }
    chosen_label = st.selectbox(
        "Select device",
        list(device_options.keys()),
        key="llm_device_select",
    )
    chosen_device = device_options[chosen_label]
    device_id     = chosen_device["id"]

    # ── Device summary ─────────────────────────────────────────────────────────
    with st.expander("Device Info", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Name:** {chosen_device.get('displayName','—')}")
        c1.markdown(f"**Model:** {chosen_device.get('product', chosen_device.get('model','—'))}")
        c2.markdown(f"**MAC:** {chosen_device.get('mac','—')}")
        c2.markdown(f"**Serial:** {chosen_device.get('serial','—')}")
        c3.markdown(
            f"**Status:** {'🟢 Connected' if chosen_device.get('connectionStatus') == 'CONNECTED' else '🔴 ' + str(chosen_device.get('connectionStatus','Unknown'))}"
        )
        c3.markdown(f"**ID:** `{device_id}`")

    st.divider()

    # ── Load line layout ──────────────────────────────────────────────────────
    col_hdr, col_refresh = st.columns([4, 1])
    with col_hdr:
        section("Line Layout", "Each row is one button on the phone.")
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Lines", use_container_width=True):
            st.session_state.pop("llm_members", None)

    if "llm_members" not in st.session_state or st.session_state.get("llm_device_id") != device_id:
        with st.spinner("Loading line layout…"):
            try:
                members = _devices.get_members(device_id)
                st.session_state["llm_members"]   = members
                st.session_state["llm_device_id"] = device_id
            except WebexAPIError as e:
                api_error(e)
                members = []
    else:
        members = st.session_state.get("llm_members", [])

    if not members:
        empty_state("No lines configured on this device.", "📵")
    else:
        # Build display table
        rows = []
        for m in members:
            line_type = m.get("lineType", "")
            rows.append({
                "Port":        m.get("port", "—"),
                "Line Type":   "🔵 Primary" if line_type == "PRIMARY" else "⚪ Shared",
                "Name":        f"{m.get('firstName','')} {m.get('lastName','')}".strip() or m.get("displayName","—"),
                "Extension":   m.get("extension", "—"),
                "Type":        m.get("type", "—"),
                "Primary Owner": "✅" if m.get("primaryOwner") else "",
                "Member ID":   m.get("id", ""),
            })

        df = pd.DataFrame(rows).sort_values("Port")

        st.dataframe(df, use_container_width=True, height=min(400, 60 + 35 * len(rows)))

        st.caption(
            f"**{len(members)} line(s)** configured. "
            "Primary lines cannot be removed from here — manage them in Control Hub."
        )

        # ── Remove a shared line ──────────────────────────────────────────────
        st.divider()
        section(
            "Remove a Shared Line Appearance",
            "Select a shared line to remove. Primary lines cannot be removed this way.",
        )

        shared_lines = [m for m in members if m.get("lineType") != "PRIMARY"]

        if not shared_lines:
            st.info("No shared line appearances on this device.")
        else:
            # Nicer labels
            remove_labels = []
            for m in shared_lines:
                name = f"{m.get('firstName','')} {m.get('lastName','')}".strip() or m.get("displayName", "?")
                remove_labels.append(
                    f"Port {m.get('port','?')} — {name} (ext {m.get('extension','?')})"
                )
            remove_map = dict(zip(remove_labels, shared_lines))

            selected_label = st.selectbox(
                "Shared line to remove",
                remove_labels,
                key="llm_remove_select",
            )
            selected_member = remove_map[selected_label]

            st.warning(
                f"This will remove **{selected_label}** from the device. "
                "The phone will need to reboot to apply the change."
            )

            if st.button("🗑️ Remove This Line", type="primary"):
                new_members = [m for m in members if m.get("id") != selected_member["id"]]
                try:
                    _devices.update_members(device_id, new_members)
                    audit_log(
                        action="remove_device_line",
                        object_type="device",
                        object_id=device_id,
                        object_name=chosen_device.get("displayName", ""),
                        details={
                            "removed_member_id":   selected_member.get("id"),
                            "removed_member_name": selected_label,
                            "port":                selected_member.get("port"),
                        },
                        success=True,
                    )
                    st.success(f"Removed **{selected_label}** from the device.")
                    # Refresh member list
                    st.session_state["llm_members"] = new_members
                    st.rerun()
                except WebexAPIError as e:
                    audit_log(
                        action="remove_device_line",
                        object_type="device",
                        object_id=device_id,
                        object_name=chosen_device.get("displayName", ""),
                        details={"error": str(e)},
                        success=False,
                        error_message=str(e),
                        tracking_id=getattr(e, "tracking_id", ""),
                    )
                    api_error(e)

else:
    if not search_btn:
        st.info("Use the search box above to find a device by MAC address, serial number, or name.")
