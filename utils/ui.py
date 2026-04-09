"""
utils/ui.py - Shared Streamlit UI components used across all pages.
"""

import streamlit as st
from webex.client import client


# ── Connection status ─────────────────────────────────────────────────────────

def connection_status_badge():
    """
    Show a green/red badge in the sidebar with token validity.
    Caches the result in session_state so we only call the API once per session.
    """
    if "conn_status" not in st.session_state:
        st.session_state.conn_status = client.connection_check()

    status = st.session_state.conn_status

    if status.get("ok"):
        st.sidebar.success(f"🟢 Connected as {status.get('name', '')}")
    else:
        error = status.get("error", "Unknown error")
        if "401" in error or "403" in error:
            st.sidebar.error("🔴 Token expired or invalid — go to **Settings** to update it.")
        else:
            st.sidebar.error(f"🔴 Connection error: {error}")


def recheck_connection():
    """Force a fresh connection check (call after token update)."""
    if "conn_status" in st.session_state:
        del st.session_state["conn_status"]


# ── Location selector ─────────────────────────────────────────────────────────

def location_selector(label: str = "Location", key: str = "loc_select") -> tuple[str, str]:
    """
    Render a searchable location selector in the sidebar.
    Returns (location_id, location_name).
    Sets st.session_state.active_location_id automatically.
    """
    from utils.cache import get_locations
    all_locs = get_locations()

    if not all_locs:
        st.sidebar.warning("No locations found.")
        return "", ""

    options = {f"{loc['name']}": loc["id"] for loc in all_locs}
    names   = list(options.keys())

    # Default to previously selected location if available
    default_name = st.session_state.get("active_location_name", names[0])
    default_idx  = names.index(default_name) if default_name in names else 0

    selected_name = st.sidebar.selectbox(label, names, index=default_idx, key=key)
    selected_id   = options[selected_name]

    st.session_state.active_location_id   = selected_id
    st.session_state.active_location_name = selected_name

    return selected_id, selected_name


# ── Empty / error states ──────────────────────────────────────────────────────

def empty_state(message: str, icon: str = "📭"):
    st.markdown(
        f"""
        <div style="text-align:center; padding:3rem; color:#888;">
            <div style="font-size:3rem;">{icon}</div>
            <div style="margin-top:0.5rem;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def api_error(e: Exception):
    """Show a user-friendly error for API failures."""
    from webex.client import WebexAPIError
    if isinstance(e, WebexAPIError):
        if e.status_code == 401:
            st.error("**Token expired.** Go to ⚙️ Settings and paste a new token.")
        elif e.status_code == 403:
            st.error("**Permission denied.** Your token may be missing a required scope.")
        elif e.status_code == 429:
            st.error("**Rate limited.** Wait a moment and try again.")
        else:
            st.error(f"**API Error {e.status_code}:** {e.message}")
            if e.tracking_id:
                st.caption(f"Tracking ID: `{e.tracking_id}`")
    else:
        st.error(f"Unexpected error: {e}")


# ── Metric row ────────────────────────────────────────────────────────────────

def metric_row(metrics: list[tuple[str, str]]):
    """
    Render a row of st.metric cards.
    metrics = [("Label", "Value"), ...]
    """
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)


# ── Section header ────────────────────────────────────────────────────────────

def section(title: str, help_text: str = ""):
    st.markdown(f"### {title}")
    if help_text:
        st.caption(help_text)
