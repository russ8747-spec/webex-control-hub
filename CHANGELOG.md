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

## Deployment Status
- [x] Code pushed to GitHub (`russ8747-spec/webex-control-hub`, branch `main`)
- [x] GitHub repo is public
- [x] Deployed to Streamlit Cloud — auto-deploys on every push to `main`
