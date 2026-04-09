"""
webex/client.py - Base HTTP client for the Webex REST API.

Handles authentication, error surfacing, pagination, and 429 retry.
"""

from __future__ import annotations

import time
import requests
from config import BASE_URL, ACCESS_TOKEN


class WebexAPIError(Exception):
    """Raised when the Webex API returns an error response."""
    def __init__(self, status_code: int, message: str, tracking_id: str = ""):
        self.status_code  = status_code
        self.message      = message
        self.tracking_id  = tracking_id
        super().__init__(f"HTTP {status_code}: {message}")


class WebexClient:
    """
    Thin wrapper around requests that handles:
      - Bearer token auth on every request
      - Clear error messages from Webex error payloads
      - Automatic pagination via Link headers
      - 429 rate-limit retry with Retry-After
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept":       "application/json",
        })

    def _get_token(self) -> str:
        """Read token from session state (runtime) or fall back to config."""
        try:
            import streamlit as st
            return st.session_state.get("access_token", "") or ACCESS_TOKEN
        except Exception:
            return ACCESS_TOKEN

    def update_token(self, token: str):
        """Swap in a new access token (called from Settings page)."""
        try:
            import streamlit as st
            st.session_state["access_token"] = token
        except Exception:
            pass

    def _url(self, path: str) -> str:
        return f"{BASE_URL}/{path.lstrip('/')}"

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code == 204:
            return {}
        try:
            response.raise_for_status()
        except requests.HTTPError:
            try:
                body    = response.json()
                message = body.get("message", response.text)
                errors  = body.get("errors", [])
                if errors:
                    message += " — " + errors[0].get("description", "")
                tracking = body.get("trackingId", "")
            except ValueError:
                message  = response.text
                tracking = ""
            raise WebexAPIError(response.status_code, message, tracking)
        return response.json()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute a request with automatic 429 retry."""
        self.session.headers["Authorization"] = f"Bearer {self._get_token()}"
        for attempt in range(1, self.max_retries + 1):
            response = self.session.request(method, url, **kwargs)
            if response.status_code == 429:
                wait = max(60, int(response.headers.get("Retry-After", 60)))
                if attempt < self.max_retries:
                    time.sleep(wait)
                    continue
            return response
        return response  # return final response even if still 429

    def get(self, path: str, params: dict = None) -> dict:
        response = self._request("GET", self._url(path), params=params)
        return self._handle_response(response)

    def get_all_pages(self, path: str, params: dict = None, items_key: str = "items") -> list:
        """Follow Webex Link-header pagination and return all items."""
        params    = params or {}
        all_items = []
        url       = self._url(path)

        while url:
            response  = self._request("GET", url, params=params)
            data      = self._handle_response(response)
            all_items.extend(data.get(items_key, []))
            params    = {}
            url       = self._next_link(response.headers.get("Link", ""))

        return all_items

    def post(self, path: str, body: dict) -> dict:
        response = self._request("POST", self._url(path), json=body)
        return self._handle_response(response)

    def put(self, path: str, body: dict) -> dict:
        response = self._request("PUT", self._url(path), json=body)
        return self._handle_response(response)

    def delete(self, path: str) -> dict:
        response = self._request("DELETE", self._url(path))
        return self._handle_response(response)

    def connection_check(self) -> dict:
        """
        Lightweight call to verify the token is valid.
        Returns: {"ok": True, "name": "...", "email": "...", "org_id": "..."}
                 {"ok": False, "error": "..."}
        """
        try:
            me = self.get("/people/me")
            return {
                "ok":     True,
                "name":   me.get("displayName", ""),
                "email":  me.get("emails", [""])[0],
                "org_id": me.get("orgId", ""),
            }
        except WebexAPIError as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _next_link(link_header: str) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                return part.split(";")[0].strip().strip("<>")
        return None


# Shared singleton — import this everywhere
client = WebexClient()
