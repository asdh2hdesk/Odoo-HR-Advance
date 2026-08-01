# Time Office Attendance Sync

Odoo 18 module that integrates a cloud-based **Time Office** attendance
system with **Odoo HR Attendance** over REST APIs. It periodically pulls
attendance punches from the Time Office API and creates/updates
`hr.attendance` records automatically.

**Author:** Balaji Bathini
**Odoo version:** 18.0
**License:** LGPL-3
**Depends on:** `hr`, `hr_attendance`, `base_setup`

---

## 1. What this module does

- Polls a configurable Time Office REST API on a schedule (default:
  every 5 minutes) and imports new/updated attendance punches.
- Maps punches to Odoo employees using a `biometric_code` field added
  to `hr.employee`.
- Creates or updates `hr.attendance` records, handling check-in,
  check-out, overnight shifts, multiple punches per day, missing
  checkouts, and duplicate punches safely.
- Records every processed punch (success, skipped, failed) in an
  `attendance.sync.log` model for full traceability.
- Supports API Key, JWT (bearer token) and Basic Authentication.
- Exposes a **Test Connection** button and a **Sync Now** button.
- Never lets one bad record or a broken connection kill the scheduler.
- Restricts configuration and manual sync to HR Managers; regular HR
  users can view imported attendance and read-only sync logs.

See the other documents in this package for details:

- [`INSTALL.md`](INSTALL.md) — installation instructions
- [`CONFIGURATION.md`](CONFIGURATION.md) — configuring the connection
- [`API_MAPPING.md`](API_MAPPING.md) — expected API payloads & sample
  responses, and how to adapt the module to a different vendor
- [`FLOW_DIAGRAM.md`](FLOW_DIAGRAM.md) — sync flow diagram
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — common errors and fixes

## 2. Module structure

```
timeoffice_attendance_sync/
├── __manifest__.py
├── __init__.py
├── security/
│   ├── security.xml            # Uses hr_attendance's own groups
│   └── ir.model.access.csv
├── data/
│   └── ir_cron.xml             # Scheduled action (every 5 min by default)
├── models/
│   ├── __init__.py
│   ├── hr_employee.py          # biometric_code field
│   ├── sync_log.py             # attendance.sync.log model
│   ├── attendance_sync.py      # TimeOfficeAdapter + sync engine model
│   └── settings.py             # res.config.settings extension (UI + buttons)
├── views/
│   ├── settings_views.xml
│   ├── sync_log_views.xml
│   ├── hr_employee_views.xml
│   └── menus.xml
├── controllers/
│   └── __init__.py             # reserved for a future inbound webhook
├── README.md
├── INSTALL.md
├── CONFIGURATION.md
├── API_MAPPING.md
├── FLOW_DIAGRAM.md
└── TROUBLESHOOTING.md
```

## 3. Architecture notes

- **`TimeOfficeAdapter`** (in `models/attendance_sync.py`) is a plain
  Python class, not an Odoo model. It owns everything vendor-specific:
  authentication, endpoint URLs, and mapping the vendor's JSON shape
  to a normalized punch dict. To support a different Time Office
  vendor later, this is the only class that needs real changes
  (see `API_MAPPING.md` §4).
- **`timeoffice.attendance.sync`** is the Odoo model that owns
  business logic: reading settings, orchestrating a run, matching
  employees, writing `hr.attendance` and `attendance.sync.log`. It
  never needs to know about vendor-specific payloads.
- **`res.config.settings`** extension provides the configuration
  screen; every field is backed by `ir.config_parameter` via the
  `config_parameter` attribute, so no separate settings model was
  needed.
- Security reuses Odoo's existing `hr_attendance.group_hr_attendance_manager`
  and `hr_attendance.group_hr_attendance_officer` groups rather than
  introducing new ones, to stay consistent with the rest of Attendances.

## 4. Third-party dependency

The module uses the Python `requests` library (already an Odoo server
dependency) for HTTP calls, with `urllib3`'s `Retry` for automatic
retries on `5xx`/connection errors and a hard 30-second timeout per
call.
