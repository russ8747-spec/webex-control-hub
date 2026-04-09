"""
pages/7_CDR_Reports.py - Call Detail Records dashboard.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.express as px
import streamlit as st
from utils.ui     import connection_status_badge, api_error, section
from utils.cache  import get_locations
from utils.export import to_csv_bytes
from webex.cdr    import cdr

st.set_page_config(page_title="CDR Reports — Control Hub", page_icon="📊", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 CDR Reports")
    connection_status_badge()
    st.divider()

    st.subheader("Location")
    use_specific_loc = st.checkbox("Filter by a specific location", value=True)
    location_id_filter = None

    if use_specific_loc:
        try:
            all_locs    = get_locations()
            loc_options = {loc["name"]: loc["id"] for loc in all_locs}
            default_name = st.session_state.get("active_location_name", list(loc_options.keys())[0])
            default_idx  = list(loc_options.keys()).index(default_name) if default_name in loc_options else 0
            selected_loc = st.selectbox("📍 Location", list(loc_options.keys()), index=default_idx)
            location_id_filter = loc_options[selected_loc]
        except Exception as e:
            st.error("Could not load locations.")

    st.divider()
    st.subheader("Time Range")
    hours_back = st.slider("Hours to look back", 1, 24, 24, 1)
    st.divider()
    fetch_btn = st.button("🔄 Fetch / Refresh Data", type="primary", use_container_width=True)
    st.caption("CDR data is available after a ~5-10 minute delay.")

# ── Session state ─────────────────────────────────────────────────────────────
if "cdr_df"         not in st.session_state: st.session_state.cdr_df         = None
if "cdr_fetched_at" not in st.session_state: st.session_state.cdr_fetched_at = None
if "cdr_location"   not in st.session_state: st.session_state.cdr_location   = None

# ── Fetch ─────────────────────────────────────────────────────────────────────
if fetch_btn:
    end_time   = datetime.now(timezone.utc) - timedelta(minutes=10)
    start_time = end_time - timedelta(hours=hours_back)

    loc_label = selected_loc if use_specific_loc else "All Locations"
    with st.spinner(f"Fetching {hours_back}h of CDR for {loc_label}…"):
        try:
            records = cdr.get_feed(
                start_time=start_time,
                end_time=end_time,
                locations=[location_id_filter] if location_id_filter else None,
            )
            st.session_state.cdr_df         = pd.DataFrame(records) if records else pd.DataFrame()
            st.session_state.cdr_fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.cdr_location   = loc_label

            if records:
                st.success(f"Loaded {len(records):,} record(s).")
            else:
                st.warning("No records found. Try widening the time range or check the CDR admin role.")
        except Exception as e:
            api_error(e)

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("📊 CDR Reports")

if st.session_state.cdr_fetched_at:
    st.caption(
        f"Data for **{st.session_state.cdr_location}** | "
        f"Last fetched: {st.session_state.cdr_fetched_at}"
    )

df = st.session_state.cdr_df

if df is None:
    st.info("Select a location and time range in the sidebar, then click **Fetch / Refresh Data**.")
    st.stop()

if df.empty:
    st.warning("No records found for the selected filters.")
    st.stop()

# ── Normalize ─────────────────────────────────────────────────────────────────
if "answered" in df.columns:
    df["answered"] = df["answered"].apply(
        lambda x: x if isinstance(x, bool) else str(x).lower() == "true"
    )
if "duration" in df.columns:
    df["duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0).astype(int)
if "startTime" in df.columns:
    df["startTime"] = pd.to_datetime(df["startTime"], errors="coerce", utc=True)
    df["Hour"]      = df["startTime"].dt.strftime("%Y-%m-%d %H:00")

# ── Metrics ───────────────────────────────────────────────────────────────────
section("Summary")
total      = len(df)
answered   = int(df["answered"].sum()) if "answered" in df.columns else 0
unanswered = total - answered
avg_dur    = int(df.loc[df["answered"] == True, "duration"].mean()) if "duration" in df.columns and answered > 0 else 0
total_dur  = int(df["duration"].sum()) if "duration" in df.columns else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Calls",      f"{total:,}")
c2.metric("Answered",         f"{answered:,}")
c3.metric("Unanswered",       f"{unanswered:,}")
c4.metric("Avg Duration",     f"{avg_dur}s")
c5.metric("Total Talk Time",  f"{total_dur // 60}m {total_dur % 60}s")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
section("Call Breakdown")
ch1, ch2, ch3 = st.columns(3)

with ch1:
    if "direction" in df.columns:
        dir_counts = df["direction"].value_counts().reset_index()
        dir_counts.columns = ["Direction", "Count"]
        fig = px.pie(dir_counts, values="Count", names="Direction",
                     title="Inbound vs Outbound",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

with ch2:
    if "answered" in df.columns:
        ans_counts = df["answered"].map({True: "Answered", False: "Unanswered"}).value_counts().reset_index()
        ans_counts.columns = ["Status", "Count"]
        fig2 = px.pie(ans_counts, values="Count", names="Status",
                      title="Answered vs Unanswered",
                      color_discrete_map={"Answered": "#2ecc71", "Unanswered": "#e74c3c"})
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)

with ch3:
    if "callType" in df.columns:
        type_counts = df["callType"].value_counts().reset_index()
        type_counts.columns = ["Call Type", "Count"]
        fig3 = px.bar(type_counts, x="Call Type", y="Count",
                      title="Calls by Type",
                      color="Count", color_continuous_scale="Blues")
        fig3.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)

if "Hour" in df.columns:
    section("Volume Over Time")
    hourly = df.groupby("Hour").size().reset_index(name="Calls").sort_values("Hour")
    fig4   = px.bar(hourly, x="Hour", y="Calls", title="Call Volume by Hour",
                    color_discrete_sequence=["#3498db"])
    fig4.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Records table ─────────────────────────────────────────────────────────────
section("Call Records")
search = st.text_input("🔍 Filter by number or user", "")

display_cols = [c for c in [
    "startTime", "callingNumber", "calledNumber", "direction",
    "callType", "answered", "duration", "userId", "location",
] if c in df.columns]
display_df = df[display_cols] if display_cols else df

if search:
    mask       = display_df.apply(lambda col: col.astype(str).str.contains(search, case=False, na=False)).any(axis=1)
    display_df = display_df[mask]

st.dataframe(display_df, use_container_width=True, height=400)
st.caption(f"Showing {len(display_df):,} of {total:,} records")

st.divider()

# ── Export ────────────────────────────────────────────────────────────────────
section("Export")
ec1, ec2 = st.columns(2)

with ec1:
    csv_bytes, _ = to_csv_bytes(df.to_dict(orient="records"), "cdr_records")
    st.download_button("⬇️ Download All Records (CSV)", csv_bytes,
                       file_name=f"cdr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                       mime="text/csv", use_container_width=True)
with ec2:
    summary_rows = [
        {"Metric": "Total Calls",       "Value": total},
        {"Metric": "Answered",          "Value": answered},
        {"Metric": "Unanswered",        "Value": unanswered},
        {"Metric": "Avg Duration (s)",  "Value": avg_dur},
        {"Metric": "Total Talk Time (s)", "Value": total_dur},
    ]
    sum_csv, _ = to_csv_bytes(summary_rows, "cdr_summary")
    st.download_button("⬇️ Download Summary (CSV)", sum_csv,
                       file_name=f"cdr_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                       mime="text/csv", use_container_width=True)
