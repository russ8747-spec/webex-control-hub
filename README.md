# Webex Control Hub API Client

A Python client for automating Webex Control Hub via the Webex REST API.

**Capabilities:**
- Pull Call Detail Records (CDR) for reporting and analysis
- List, create, and update Locations
- List, create, update, and delete Auto Attendants

---

## Prerequisites

- Python 3.10+
- A Webex organization with **Webex Calling** enabled
- A Webex admin account with the right roles (see below)

---

## Setup

### 1. Install dependencies

```bash
cd webex-control-hub
pip3 install -r requirements.txt
```

### 2. Get your access token

1. Go to [developer.webex.com](https://developer.webex.com) and sign in with your admin account.
2. Click your avatar (top right) → **Copy personal access token**.
   - This token is valid for **12 hours** and is perfect for testing.
   - For production use you'll need an OAuth integration (ask when you're ready).

### 3. Get your Org ID

1. Log in to [Control Hub](https://admin.webex.com).
2. Go to **Account** → your Org ID is displayed there.
   - It can also be found at: developer.webex.com → your avatar → `orgId` in the token payload.

### 4. Configure your credentials

```bash
cp .env.example .env
```

Open `.env` and fill in:
```
WEBEX_ACCESS_TOKEN=your_token_here
WEBEX_ORG_ID=your_org_id_here
```

> **Never commit your `.env` file.** It contains secrets.

---

## Admin Roles Required

Before using certain APIs, your admin account needs specific roles enabled in Control Hub:

| Feature | Role needed in Control Hub |
|---|---|
| CDR (call records) | **Webex Calling Detailed Call History API access** |
| Locations | Full Administrator |
| Auto Attendants | Full Administrator |

To enable the CDR role: Control Hub → **Users** → your account → **Administrator Roles**.

---

## Required API Scopes

| Scope | Used for |
|---|---|
| `spark-admin:calling_cdr_read` | Reading call detail records |
| `spark-admin:locations_read` | Listing/reading locations |
| `spark-admin:locations_write` | Creating/updating locations |
| `spark-admin:telephony_config_read` | Reading auto attendants |
| `spark-admin:telephony_config_write` | Creating/updating/deleting auto attendants |

Personal access tokens automatically include all scopes your account has permission for.

---

## Project Structure

```
webex-control-hub/
├── .env.example          # Template for credentials
├── .env                  # Your credentials (DO NOT commit)
├── requirements.txt      # Python dependencies
├── config.py             # Loads .env and sets BASE_URL
├── webex_client.py       # Base HTTP client (auth, errors, pagination)
├── modules/
│   ├── cdr.py            # Call Detail Records
│   ├── locations.py      # Locations
│   └── auto_attendants.py# Auto Attendants
└── examples/
    ├── 01_get_call_records.py
    ├── 02_manage_locations.py
    └── 03_manage_auto_attendants.py
```

---

## Running the Examples

```bash
# Pull call records from the last 6 hours
python examples/01_get_call_records.py

# List locations (and optionally create/update)
python examples/02_manage_locations.py

# List auto attendants (and optionally create/update/delete)
python examples/03_manage_auto_attendants.py
```

---

## Using the Modules in Your Own Scripts

```python
from modules.cdr import cdr
from modules.locations import locations
from modules.auto_attendants import auto_attendants
from datetime import datetime, timedelta, timezone

# --- CDR ---
records = cdr.get_feed(
    start_time=datetime.now(timezone.utc) - timedelta(hours=12),
    end_time=datetime.now(timezone.utc),
)
summary = cdr.summarize(records)
print(summary)

# --- Locations ---
all_locs = locations.list()
new_loc  = locations.create(
    name="Boston Office",
    time_zone="America/New_York",
    preferred_language="en_us",
    address={"address1": "1 Main St", "city": "Boston", "state": "MA",
             "postalCode": "02101", "country": "US"},
)

# --- Auto Attendants ---
menu = auto_attendants.build_menu(
    greeting="DEFAULT",
    keys={"0": {"action": "TRANSFER_TO_OPERATOR"}, "9": {"action": "REPEAT_MENU"}},
)
aa = auto_attendants.create(
    location_id=new_loc["id"],
    name="Boston Reception",
    extension="2000",
    business_hours_menu=menu,
)
```

---

## API Reference

- [CDR Feed / Stream](https://developer.webex.com/blog/understanding-the-webex-calling-cdr-apis)
- [Locations API](https://developer.webex.com/docs/api/v1/locations)
- [Auto Attendant API](https://developer.webex.com/docs/api/v1/features-auto-attendant)
- [Webex REST API Basics](https://developer.webex.com/docs/basics)
