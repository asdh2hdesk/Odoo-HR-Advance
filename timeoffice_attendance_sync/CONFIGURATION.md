# Configuration Guide

Navigate to **Attendances → Configuration → Time Office Settings**
(HR Manager access required).

## 1. Connection fields

| Field | Description |
|---|---|
| API Base URL | Root URL of the Time Office API, e.g. `https://timeoffice.example.com` |
| Authentication Type | `API Key`, `JWT`, or `Basic Authentication` |
| Username / Password | Used only when Authentication Type = Basic Authentication |
| API Key | Used only when Authentication Type = API Key. Sent as the `X-API-Key` header |
| Bearer Token | Used only when Authentication Type = JWT. Sent as `Authorization: Bearer <token>` |
| Attendance Endpoint | Path (relative to API Base URL) that returns attendance punches, default `/api/attendance` |
| Employee Endpoint | Path used by "Test Connection" and optional employee lookups, default `/api/employees` |
| Company Code | Optional; sent as `X-Company-Code` header and `company_code` query param, useful for multi-tenant Time Office setups |

## 2. Scheduling

| Field | Description |
|---|---|
| Enable Automatic Sync | Turns the scheduled action on/off |
| Sync Interval (minutes) | How often the scheduler runs; saved to the underlying `ir.cron` record whenever you save this page |
| Last Sync Time | Read-only; timestamp of the last successful fetch, used as the `since` cursor for the next run |

## 3. Testing the connection

Click **Test Connection**. The module authenticates and makes one
lightweight call to the Employee Endpoint. You'll see one of:

- ✅ *Connection Successful*
- ❌ *Invalid Credentials* (HTTP 401)
- ❌ *Access Forbidden* (HTTP 403)
- ❌ *Endpoint Not Found* (HTTP 404)
- ❌ *Server Unreachable (Timeout)*
- ❌ *Server Unreachable* (DNS/connection failure)
- ❌ *Time Office Server Error* (HTTP 5xx)

## 4. Manual synchronization

Click **Sync Now** to run a sync immediately, outside the schedule.
A notification reports Imported / Skipped / Failed counts and the run
duration. Details for every record are in **Attendances → Attendance
Sync Logs**.

## 5. Mapping employees

Every employee that should receive automatic attendance must have
their **Biometric Code** set on the Employee form (HR Manager access),
matching the `employee_code` value the Time Office system reports for
that person. Employees without a matching code are skipped and logged
as failed with a clear error message — the sync itself keeps running.

## 6. Security

- HR Managers (`hr_attendance.group_hr_attendance_manager`): can
  change all settings above, click Test Connection / Sync Now, and
  see all sync logs.
- HR Attendance Users (`hr_attendance.group_hr_attendance_officer`): can
  view imported attendance and sync logs, read-only. They cannot open
  the Time Office Settings page.
