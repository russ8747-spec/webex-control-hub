# Webex Control Hub — Changelog

All notable changes to this project are documented here.
Use commit hashes below to roll back to any specific version.

---

## [v1.0.0] — 2026-04-09
**Commit:** `5474020`
**Changed by:** Claude

### Added
- Login gate on app launch — users enter their own Webex Access Token + optional Org ID
- Token validated against Webex API before access is granted
- Sign Out button in sidebar clears the session
- `.gitignore` created — blocks `.env`, `audit.db`, `Errors/`, `example/`, `.claude/` from being committed

### Changed
- `config.py` — removed hard crash on missing `.env`; app starts without credentials
- `webex/client.py` — token now read from `st.session_state` on every API call (multi-user safe)

### Security
- Full git history wiped and replaced with a single clean commit
- Removed from history: `Errors/` CSVs (real location codes), `example/` CSVs (real phone numbers, brand references), `.claude/settings.local.json` (local machine paths)
- Commit identity set to `Webex Admin <noreply@github.com>` — no personal info in git history

### Known Open Issues
- Numbers page is missing "Add Phone Numbers" feature that existed in v3 (pre-history wipe) — needs to be rebuilt
- CSV export bug in `utils/export.py` line 21: `data[0].keys()` crashes if later records have extra fields (e.g. `notes`). Fix: collect all keys across all records before writing.

### Rollback
This is the initial clean commit. No previous version to roll back to.

---

## [v1.1.0] — 2026-04-27
**Commit:** `2d09085`
**Changed by:** Claude

### Added
- `pages/11_Bulk_Add_Numbers.py` — new Bulk Add Numbers page ported from v3
  - CSV upload with `phone_number` + `location_name` columns
  - Auto-normalizes US formats (10-digit, xxx-xxx-xxxx, 1xxxxxxxxxx) to E.164
  - Validates every row against live Control Hub locations before execution
  - Previews batches grouped by location before the user commits
  - Progress bar per location; results table with pass/fail per number
  - Downloadable results CSV; all actions written to audit log
  - Number type selector (DID / TOLLFREE / MOBILE) in sidebar
- `webex/numbers.py` — added `Numbers.add()` method
  - POSTs to `/telephony/config/locations/{id}/numbers`
  - Requires `spark-admin:telephony_config_write` scope

### Notes
- Snapshot tag `v1.0.0-pre-bulk-numbers` created before this change
- No hardcoded org IDs, location names, or phone numbers anywhere in the new code
- Template CSV ships with placeholder values only (`Your Location Name Here`)
- To roll back: `git checkout v1.0.0-pre-bulk-numbers -- pages/11_Bulk_Add_Numbers.py webex/numbers.py`

---

## [v1.1.1] — 2026-04-27
**Commit:** `ce7fa58`
**Changed by:** Claude

### Fixed
- `app.py` — added home-page buttons for Bulk Add Numbers and Rename Store, which were missing from the dashboard grid (pages 10 and 11 were never wired up)

---

## [v1.2.0] — 2026-04-27
**Commit:** `c6e9114`
**Changed by:** Claude

### Added
- `pages/11_Bulk_Add_Numbers.py` — Type/Paste tab alongside the existing CSV Upload tab
  - Text area accepts one number per line in any common US format
  - Location dropdown populated live from Control Hub locations
  - Same E.164 normalization, validation, preview, and execute flow as CSV mode
  - Shared `validate_rows()` and `render_review_and_execute()` helpers eliminate duplication between tabs

---

## [v1.2.1] — 2026-04-27
**Commit:** `62cf6ea`
**Changed by:** Claude

### Fixed
- `webex/auto_attendants.py` — `list()` and `get()` now use the org-level endpoint (`/telephony/config/autoAttendants?locationId=...`) instead of the location-path variant (`/telephony/config/locations/{id}/autoAttendants`). The location-path variant returns `404: No static resource` for some orgs. This matches the same fix already applied to hunt groups.
- `create()`, `update()`, `delete()` continue to use the location-path as required by the Webex API for write operations.

---

## [v1.3.0] — 2026-04-28
**Commit:** `5b9f0fa`
**Changed by:** Claude

### Added
- `webex/music_on_hold.py` — new API module for `GET/PUT /telephony/config/locations/{id}/musicOnHold`
- `pages/12_Music_On_Hold.py` — new page showing MOH settings for all locations in one table
  - Fetches all locations in parallel (up to 20 concurrent calls) via `ThreadPoolExecutor`
  - Columns: Location, Greeting Type, Audio File, File Scope, Call Hold MOH, Call Park MOH
  - Filter by location name, file name, or greeting type (Custom / Default)
  - Summary metrics: total locations, custom files, default, errors
  - Export to CSV
  - Errors per location shown in collapsible expander
- `app.py` — added Music on Hold button to home page grid (row 4, col 3)

---

## [v1.3.1] — 2026-04-30
**Commit:** `b5ea3ea`
**Changed by:** Claude

### Fixed
- `webex/auto_attendants.py` — three AA create issues:
  1. **Dialing Options**: Changed `extensionDialing` from `"GROUP"` to `"ENTERPRISE"` — `"GROUP"` was resolving to "Organization" in Control Hub; `"ENTERPRISE"` gives "Location"
  2. **No input timer**: `noInputGracePeriodSeconds: 5` was already correct in `_build_menu` but POST was silently ignoring it (defaulting to 10). Fixed by adding a follow-up PUT via `update()` immediately after `create()` to force the value through.
  3. **Repeat on no input**: Same root cause as #2 — `noInputRepeatTimes: 2` was in the code but not applied by POST. Resolved by same follow-up PUT.
- The follow-up `update()` is best-effort (failure does not fail the creation — AA is already created).

---

## [v1.4.0] — 2026-04-30
**Commit:** `59b3c4a`
**Changed by:** Claude

### Fixed
- `webex/auto_attendants.py` — corrected `extensionDialing` back to `"GROUP"` (= Location).
  CSV analysis of ATL028 (bad) vs ATL050/ATL080 (target) confirmed GROUP=Location, ENTERPRISE=Organization.
  v1.3.1 incorrectly changed this to ENTERPRISE. Now also forces `extensionDialing="GROUP"` through the
  follow-up PUT so POST-level defaults can't override it.
- `update()` — added `extension_dialing` parameter so it can be set via PUT as well as POST.

### Changed
- `_build_menu()` — signature changed from `greeting: str` to `audio_file_name: str = None`.
  Pass a WAV filename for CUSTOM, or None for DEFAULT. Removes the hardcoded `GREETING_FILE` constant.
- `create_from_template()` — `greeting` parameter replaced with `audio_file_name: str = None`.

### Added
- `webex/announcements.py` — new module for `GET /telephony/config/announcements` (org-level WAV library)
- `utils/cache.py` — `get_announcements()` cached wrapper (5 min TTL)
- `pages/4_Auto_Attendants.py` — greeting selector now shows a live dropdown of existing org audio files
  instead of hardcoded DEFAULT/CUSTOM options. Selecting a file uses it as CUSTOM greeting;
  selecting "Default (Webex built-in)" uses DEFAULT.

---

## Deployment Status
- [x] Code pushed to GitHub (`russ8747-spec/webex-control-hub`, branch `main`)
- [x] GitHub repo is public
- [x] Deployed to Streamlit Cloud — auto-deploys on every push to `main`
