"""
config.py - Central configuration for the Webex Control Hub client.
Credentials are entered by the user at login and stored in session state.
A local .env file is still supported for development convenience.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://webexapis.com/v1"

# Optional fallback for local dev — not required in production
ACCESS_TOKEN = os.getenv("WEBEX_ACCESS_TOKEN", "")
ORG_ID       = os.getenv("WEBEX_ORG_ID", "")
