"""
pages/9_Settings.py - Token management and connection info.
"""

import os
import streamlit as st
from utils.ui    import connection_status_badge, recheck_connection, section
from utils.audit import log as audit_log
from webex.client import client

st.set_page_config(page_title="Settings — Control Hub", page_icon="⚙️", layout="wide")

with st.sidebar:
    st.title("⚙️ Settings")
    connection_status_badge()

st.title("⚙️ Settings")

# ── Connection status ─────────────────────────────────────────────────────────
section("Connection Status")

status = client.connection_check()

if status.get("ok"):
    st.success(f"🟢 **Connected** — Signed in as **{status['name']}** ({status['email']})")
    c1, c2 = st.columns(2)
    c1.markdown(f"**Name:** {status['name']}")
    c1.markdown(f"**Email:** {status['email']}")
    c2.markdown("**Org ID:**")
    c2.code(status["org_id"], language=None)
else:
    st.error(f"🔴 **Not connected** — {status.get('error', 'Unknown error')}")

if st.button("🔄 Re-check Connection"):
    recheck_connection()
    st.rerun()

st.divider()

# ── Token update ──────────────────────────────────────────────────────────────
section(
    "Update Access Token",
    "Webex personal access tokens expire every 12 hours. "
    "Get a fresh one at developer.webex.com → your profile picture → Copy.",
)

with st.form("token_form"):
    new_token = st.text_input(
        "Paste new token here",
        type="password",
        placeholder="ZTdjO…",
        help="Your token is stored only in memory and your local .env file — never sent anywhere else.",
    )
    save_btn = st.form_submit_button("💾 Save Token", type="primary")

if save_btn:
    if not new_token.strip():
        st.warning("Token cannot be empty.")
    else:
        # Update the live client
        client.update_token(new_token.strip())

        # Verify it works
        recheck_connection()
        check = client.connection_check()
        st.session_state.conn_status = check

        if check.get("ok"):
            # Persist to .env file
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            env_path = os.path.normpath(env_path)
            try:
                with open(env_path, "r") as f:
                    lines = f.readlines()
                with open(env_path, "w") as f:
                    for line in lines:
                        if line.startswith("WEBEX_ACCESS_TOKEN="):
                            f.write(f"WEBEX_ACCESS_TOKEN={new_token.strip()}\n")
                        else:
                            f.write(line)
                st.success(
                    f"✅ Token updated and saved. "
                    f"Connected as **{check['name']}** ({check['email']})."
                )
                audit_log(
                    action="token_updated",
                    object_type="settings",
                    object_id=check.get("org_id", ""),
                    object_name="WEBEX_ACCESS_TOKEN",
                    admin_email=check.get("email", ""),
                    success=True,
                )
            except Exception as e:
                st.warning(
                    f"Token is valid and working in memory, "
                    f"but could not save to .env file: {e}. "
                    f"You'll need to paste it again after restarting."
                )
        else:
            st.error(
                f"❌ That token didn't work: {check.get('error', 'Unknown error')}. "
                "Double-check you copied the full token from developer.webex.com."
            )

st.divider()

# ── Required scopes reference ─────────────────────────────────────────────────
section("Required API Scopes", "Your token must have these scopes for full functionality.")

scope_data = [
    ("spark-admin:calling_cdr_read",         "CDR Reports",           "✅ Required"),
    ("spark-admin:locations_read",            "Locations",             "✅ Required"),
    ("spark-admin:locations_write",           "Create/Edit Locations", "Milestone 2+"),
    ("spark-admin:telephony_config_read",     "Numbers, Auto Attendants, Devices", "✅ Required"),
    ("spark-admin:telephony_config_write",    "Create/Edit AAs, Schedules", "Milestone 2+"),
    ("spark:devices_read",                    "Device Inventory",      "✅ Required"),
    ("spark:devices_write",                   "Configure Devices",     "Milestone 2+"),
]

import pandas as pd
st.dataframe(
    pd.DataFrame(scope_data, columns=["Scope", "Used For", "Status"]),
    use_container_width=True,
    hide_index=True,
)

st.divider()
section(
    "Required Admin Roles",
    "Set these in Control Hub → Users → your account → Administrator Roles."
)
st.markdown("""
- **Full Administrator** — required for Locations, Numbers, Auto Attendants
- **Webex Calling Detailed Call History API access** — required for CDR Reports
""")
