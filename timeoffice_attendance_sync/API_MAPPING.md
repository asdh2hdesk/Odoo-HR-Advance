# API Mapping Guide

## 1. Expected attendance endpoint

`GET {api_base_url}{attendance_endpoint}?since=YYYY-MM-DDTHH:MM:SS[&company_code=...]`

The `since` parameter is the value of **Last Sync Time**; omitted on
the very first run so the whole history available from the vendor is
pulled once.

### Sample response (bare list)

```json
[
  {
    "employee_code": "EMP001",
    "check_in": "2026-08-01T09:12:30",
    "check_out": "2026-08-01T18:05:12"
  },
  {
    "employee_code": "EMP002",
    "check_in": "2026-08-01T09:05:00",
    "check_out": null
  }
]
```

### Sample response (wrapped)

The adapter also accepts a wrapped shape, trying `data`, `results`,
`records`, or `attendance` keys in that order:

```json
{
  "status": "ok",
  "data": [
    {"employee_code": "EMP001", "check_in": "2026-08-01T09:12:30", "check_out": "2026-08-01T18:05:12"}
  ]
}
```

## 2. Expected employee endpoint

Used by **Test Connection** (`GET {employee_endpoint}?limit=1&page=1`)
and available for optional per-employee lookups
(`GET {employee_endpoint}?employee_code=EMP001`):

```json
{
  "employee_code": "EMP001",
  "name": "Jane Doe",
  "department": "Engineering"
}
```

Only the connectivity/authentication result of this call matters for
Test Connection — its body isn't otherwise processed by this module.

## 3. Field mapping

| Time Office field | Odoo field | Notes |
|---|---|---|
| `employee_code` | `hr.employee.biometric_code` | Used to find the employee via `search([('biometric_code', '=', employee_code)])` |
| `check_in` | `hr.attendance.check_in` | Parsed as `YYYY-MM-DDTHH:MM:SS` (a trailing `Z` is stripped; space-separated datetimes also accepted) |
| `check_out` | `hr.attendance.check_out` | Same parsing; may be `null`/absent for an open shift |

## 4. Adapting to a different Time Office vendor

Everything vendor-specific lives in `TimeOfficeAdapter`
(`models/attendance_sync.py`). To support a new vendor:

1. Point **Attendance Endpoint** / **Employee Endpoint** at the new
   API's paths from the Settings page — no code change needed if the
   payload shape already matches §1–§2 above.
2. If the JSON shape differs, override `_normalize_record()` (and, if
   the list is wrapped differently, `_extract_records()`) in a small
   subclass of `TimeOfficeAdapter`, and return it from
   `TimeOfficeAttendanceSync._build_adapter()` based on a new "Vendor"
   selection field if you need to support several vendors at once.
3. If authentication differs (e.g. a login call that returns a
   short-lived token instead of a static Bearer Token), extend
   `authenticate()` in the subclass; the rest of the sync engine is
   unaffected.

No changes to `timeoffice.attendance.sync`, `attendance.sync.log`, the
views, or the cron are required for a new vendor.

## 5. Error responses

Any non-2xx response is mapped to a specific error code
(`unauthorized`, `forbidden`, `not_found`, `timeout`, `server_error`,
`network_error`, `invalid_json`) and surfaced as a human-readable
message in Test Connection results, Sync Now notifications, and
`attendance.sync.log` entries when the whole run fails to start. See
`TROUBLESHOOTING.md`.
