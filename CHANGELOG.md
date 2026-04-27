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

## Deployment Status
- [x] Code pushed to GitHub (`russ8747-spec/webex-control-hub`, branch `main`)
- [ ] GitHub repo made public
- [ ] Deployed to Streamlit Cloud (`share.streamlit.io`)
