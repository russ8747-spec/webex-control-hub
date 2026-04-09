"""
app.py - Webex Control Hub Dashboard
Main entry point. Run with: streamlit run app.py
"""

import streamlit as st
from utils.ui import connection_status_badge

st.set_page_config(
    page_title="Webex Control Hub",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Credential gate ───────────────────────────────────────────────────────────
if "access_token" not in st.session_state:
    st.title("📞 Webex Control Hub")
    st.markdown("Enter your Webex credentials to get started.")
    st.divider()

    with st.form("login_form"):
        token = st.text_input(
            "Access Token",
            type="password",
            placeholder="ZTdj...",
            help="Get yours at developer.webex.com → your profile picture → Copy personal access token",
        )
        org_id = st.text_input(
            "Org ID (optional)",
            placeholder="Y2lzY29zcGFyazov...",
            help="Found in Control Hub → Account. Leave blank if unsure.",
        )
        submitted = st.form_submit_button("Connect", type="primary", use_container_width=True)

    if submitted:
        if not token.strip():
            st.error("Access token is required.")
        else:
            from webex.client import client
            client.update_token(token.strip())
            if org_id.strip():
                st.session_state["org_id"] = org_id.strip()
            check = client.connection_check()
            if check.get("ok"):
                st.session_state["access_token"] = token.strip()
                st.session_state["conn_status"] = check
                st.rerun()
            else:
                st.error(f"Could not connect: {check.get('error', 'Unknown error')}. Check your token and try again.")

    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📞 Control Hub")
    st.caption("Webex Calling Admin Dashboard")
    st.divider()
    connection_status_badge()
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ── Home page ─────────────────────────────────────────────────────────────────
st.title("Webex Control Hub Dashboard")
st.markdown("Use the **sidebar** to navigate between pages.")
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📍 Locations")
    st.markdown("Search and browse all locations in your org.")
    if st.button("Go to Locations", use_container_width=True):
        st.switch_page("pages/1_Locations.py")

with col2:
    st.markdown("### 💻 Devices")
    st.markdown("View device inventory, status, and details.")
    if st.button("Go to Devices", use_container_width=True):
        st.switch_page("pages/2_Devices.py")

with col3:
    st.markdown("### 📱 Line Layout Manager")
    st.markdown("View and edit line button assignments on phones.")
    if st.button("Go to Line Layout Manager", use_container_width=True):
        st.switch_page("pages/3_Line_Layout_Manager.py")

st.divider()
col4, col5, col6 = st.columns(3)

with col4:
    st.markdown("### 📟 Auto Attendants")
    st.markdown("View, create, and edit auto attendants by location.")
    if st.button("Go to Auto Attendants", use_container_width=True):
        st.switch_page("pages/4_Auto_Attendants.py")

with col5:
    st.markdown("### 🔢 Numbers")
    st.markdown("Browse phone number inventory and usage.")
    if st.button("Go to Numbers", use_container_width=True):
        st.switch_page("pages/5_Numbers.py")

with col6:
    st.markdown("### 📊 CDR Reports")
    st.markdown("Pull and analyze call detail records.")
    if st.button("Go to CDR Reports", use_container_width=True):
        st.switch_page("pages/7_CDR_Reports.py")

st.divider()
col7, col8, col9 = st.columns(3)

with col7:
    st.markdown("### 📋 Audit Log")
    st.markdown("Review all actions taken in this dashboard.")
    if st.button("Go to Audit Log", use_container_width=True):
        st.switch_page("pages/8_Audit_Log.py")

with col8:
    st.markdown("### ⚙️ Settings")
    st.markdown("Update your API token and check connectivity.")
    if st.button("Go to Settings", use_container_width=True):
        st.switch_page("pages/9_Settings.py")

with col9:
    st.markdown("### 🔀 Hunt Groups")
    st.markdown("Check AA readiness and unassign HG phone numbers.")
    if st.button("Go to Hunt Groups", use_container_width=True):
        st.switch_page("pages/6_Hunt_Groups.py")
