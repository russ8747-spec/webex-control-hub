"""
pages/2_Devices.py - Device inventory viewer.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.ui     import connection_status_badge, empty_state, api_error, section
from utils.cache  import get_devices, get_locations
from utils.export import records_to_csv_bytes

st.set_page_config(page_title="Devices — Control Hub", page_icon="💻", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💻 Devices")
    connection_status_badge()
    st.divider()

    # Location selector
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
    status_filter = st.selectbox(
        "Connection Status",
        ["All", "CONNECTED", "DISCONNECTED", "CONNECTED_WITH_ISSUES"],
    )
    search_text = st.text_input("🔍 Search name / MAC / serial", "")

# ── Fetch ─────────────────────────────────────────────────────────────────────
st.title("💻 Devices")
st.caption(f"Showing devices for: **{selected_loc}**")

try:
    raw_devices = get_devices(
        location_id=location_id,
        connection_status=status_filter if status_filter != "All" else None,
    )
except Exception as e:
    api_error(e)
    st.stop()

if not raw_devices:
    empty_state("No devices found for the selected filters.", "💻")
    st.stop()

# ── Filter by search text ──────────────────────────────────────────────────────
if search_text:
    term = search_text.lower()
    raw_devices = [
        d for d in raw_devices
        if term in d.get("displayName", "").lower()
        or term in d.get("mac", "").lower()
        or term in d.get("serial", "").lower()
    ]

# ── Summary metrics ───────────────────────────────────────────────────────────
total       = len(raw_devices)
connected   = sum(1 for d in raw_devices if d.get("connectionStatus") == "CONNECTED")
disconnected = sum(1 for d in raw_devices if d.get("connectionStatus") == "DISCONNECTED")
issues      = sum(1 for d in raw_devices if d.get("connectionStatus") == "CONNECTED_WITH_ISSUES")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Devices",    f"{total:,}")
c2.metric("🟢 Connected",     f"{connected:,}")
c3.metric("🔴 Disconnected",  f"{disconnected:,}")
c4.metric("🟡 Issues",        f"{issues:,}")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
if total > 0:
    ch1, ch2 = st.columns(2)

    with ch1:
        status_counts = pd.DataFrame(raw_devices)["connectionStatus"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        color_map = {
            "CONNECTED":               "#2ecc71",
            "DISCONNECTED":            "#e74c3c",
            "CONNECTED_WITH_ISSUES":   "#f39c12",
        }
        fig = px.pie(
            status_counts, values="Count", names="Status",
            title="Devices by Status",
            color="Status", color_discrete_map=color_map,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        model_col = next((c for c in ["product", "model"] if c in pd.DataFrame(raw_devices).columns), None)
        if model_col:
            model_counts = pd.DataFrame(raw_devices)[model_col].value_counts().head(10).reset_index()
            model_counts.columns = ["Model", "Count"]
            fig2 = px.bar(
                model_counts, x="Count", y="Model", orientation="h",
                title="Top 10 Device Models",
                color="Count", color_continuous_scale="Blues",
            )
            fig2.update_layout(showlegend=False, coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig2, use_container_width=True)

# ── Device table ──────────────────────────────────────────────────────────────
section("Device Inventory", f"{total:,} devices")

STATUS_ICONS = {
    "CONNECTED":             "🟢",
    "DISCONNECTED":          "🔴",
    "CONNECTED_WITH_ISSUES": "🟡",
}

rows = []
for d in raw_devices:
    status = d.get("connectionStatus", "UNKNOWN")
    rows.append({
        "Status":       STATUS_ICONS.get(status, "⚪") + " " + status.replace("_", " ").title(),
        "Display Name": d.get("displayName", "—"),
        "Model":        d.get("product") or d.get("model", "—"),
        "MAC":          d.get("mac", "—"),
        "Serial":       d.get("serial", "—"),
        "IP Address":   d.get("ip", "—"),
        "Assigned To":  d.get("personDisplayName") or d.get("workspaceDisplayName") or "—",
        "Device ID":    d.get("id", ""),
    })

df = pd.DataFrame(rows)

selected = st.dataframe(
    df,
    use_container_width=True,
    height=450,
    on_select="rerun",
    selection_mode="single-row",
)

# ── Device detail panel ───────────────────────────────────────────────────────
if selected and selected.get("selection", {}).get("rows"):
    row_idx = selected["selection"]["rows"][0]
    dev     = raw_devices[row_idx]

    with st.expander("📋 Device Details", expanded=True):
        dc1, dc2, dc3 = st.columns(3)
        dc1.markdown(f"**Name:** {dev.get('displayName', '—')}")
        dc1.markdown(f"**Model:** {dev.get('product') or dev.get('model', '—')}")
        dc1.markdown(f"**Status:** {STATUS_ICONS.get(dev.get('connectionStatus',''), '⚪')} {dev.get('connectionStatus','—')}")
        dc2.markdown(f"**MAC:** `{dev.get('mac', '—')}`")
        dc2.markdown(f"**Serial:** `{dev.get('serial', '—')}`")
        dc2.markdown(f"**IP:** {dev.get('ip', '—')}")
        dc3.markdown(f"**Assigned to:** {dev.get('personDisplayName') or dev.get('workspaceDisplayName', '—')}")
        dc3.markdown(f"**Created:** {dev.get('created', '—')}")
        dc3.markdown("**Device ID:**")
        dc3.code(dev.get("id", ""), language=None)

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()
section("Export")
csv_bytes, filename = records_to_csv_bytes(raw_devices, f"devices_{selected_loc.replace(' ','_')}")
st.download_button(
    label="⬇️ Export Device List to CSV",
    data=csv_bytes,
    file_name=filename,
    mime="text/csv",
)
