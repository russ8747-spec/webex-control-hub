"""
pages/8_Audit_Log.py - View all actions taken through the dashboard.
"""

import streamlit as st
import pandas as pd
from utils.ui     import connection_status_badge, empty_state, section
from utils.audit  import get_entries
from utils.export import to_csv_bytes

st.set_page_config(page_title="Audit Log — Control Hub", page_icon="📋", layout="wide")

with st.sidebar:
    st.title("📋 Audit Log")
    connection_status_badge()
    st.divider()
    st.subheader("Filters")
    success_filter = st.selectbox("Status", ["All", "Success only", "Failures only"])
    object_filter  = st.selectbox(
        "Object Type",
        ["All", "location", "device", "auto_attendant", "number", "hunt_group", "schedule"],
    )
    limit = st.slider("Max entries to show", 50, 500, 200, 50)

st.title("📋 Audit Log")
st.caption("All actions taken through this dashboard are recorded here automatically.")

# ── Fetch ─────────────────────────────────────────────────────────────────────
success_map = {"All": None, "Success only": True, "Failures only": False}
entries = get_entries(
    limit=limit,
    object_type=object_filter if object_filter != "All" else None,
    success=success_map[success_filter],
)

if not entries:
    empty_state(
        "No audit log entries yet. Actions you take in this dashboard will appear here.",
        "📋",
    )
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────
total     = len(entries)
successes = sum(1 for e in entries if e["success"])
failures  = total - successes

c1, c2, c3 = st.columns(3)
c1.metric("Total Entries",  f"{total:,}")
c2.metric("✅ Successes",   f"{successes:,}")
c3.metric("❌ Failures",    f"{failures:,}")
st.divider()

# ── Table ─────────────────────────────────────────────────────────────────────
section("Log Entries")

rows = []
for e in entries:
    rows.append({
        "Time":         e["timestamp"],
        "Action":       e["action"],
        "Object Type":  e["object_type"],
        "Object Name":  e["object_name"],
        "Admin":        e["admin_email"],
        "Status":       "✅ Success" if e["success"] else "❌ Failed",
        "Error":        e["error_message"] or "",
        "Tracking ID":  e["tracking_id"] or "",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, height=500)

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()
section("Export")
csv_bytes, filename = to_csv_bytes(entries, "audit_log")
st.download_button(
    label="⬇️ Download Audit Log as CSV",
    data=csv_bytes,
    file_name=filename,
    mime="text/csv",
)
