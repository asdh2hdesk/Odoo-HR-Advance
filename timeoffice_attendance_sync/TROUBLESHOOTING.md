# Troubleshooting Guide

| Symptom | Likely cause | Fix |
|---|---|---|
| Test Connection → "Invalid Credentials" | Wrong API Key / Bearer Token / Username-Password, or wrong Authentication Type selected | Re-check the credentials and that Authentication Type matches how the Time Office API expects to be called |
| Test Connection → "Server Unreachable" | DNS/network issue, firewall blocking outbound HTTPS from the Odoo server, or wrong API Base URL | Confirm the URL is reachable from the Odoo server itself (not just your laptop), check firewall/proxy rules |
| Test Connection → "Server Unreachable (Timeout)" | Time Office server slow or unresponsive; default timeout is 30s | Check Time Office server health; consider whether the endpoint itself is slow |
| Test Connection → "Endpoint Not Found" | Wrong Attendance/Employee Endpoint path | Verify the exact path with your Time Office vendor's API docs |
| Sync Now reports many "Failed" | Employees missing `biometric_code`, or codes don't match what the API sends | Check **Attendance Sync Logs**, filter Status = Failed, read the message; set/correct `biometric_code` on the relevant employees |
| A punch shows as "Skipped" | Expected — the module found a duplicate `check_in` already imported with nothing new to add | No action needed; this is a safety feature to prevent duplicate `hr.attendance` records |
| Attendance record stuck without a check-out | Time Office hasn't sent the checkout punch yet, or it arrived with no matching open attendance (orphan checkout, logged as Failed) | Wait for the next sync; if it never arrives, check the Time Office side for the missing punch, or close the attendance manually in Odoo |
| Scheduled sync doesn't seem to run | Enable Automatic Sync is off, or the `ir.cron` was deactivated externally | Re-open Time Office Settings, verify the toggle, and re-save (this re-applies the interval/active state to the scheduled action) |
| Sync interval change doesn't seem to apply | The `ir.cron` interval is only updated when the Settings page is **saved** | Re-save the Settings page after changing the interval |
| "Could not parse JSON response" | The API returned HTML (e.g. an error page from a proxy/load balancer) instead of JSON | Check the URL and that the API server itself (not a login page) is being hit |
| A user can't see Time Office Settings | They aren't an HR Manager (`hr_attendance.group_hr_attendance_manager`) | Grant the "Administrator" Attendances access level on their user, or accept that this page is manager-only by design |
| Duplicate `hr.attendance` records appear despite the dedup logic | Two check-ins for the same employee at slightly different timestamps from the Time Office side (not a true duplicate from Odoo's point of view) | This is a data-quality issue on the Time Office side; consider normalizing timestamps upstream, or extend `_create_or_update_attendance` with a tolerance window if punches can be a few seconds apart for the same event |

## Where to look for logs

- **Attendances → Attendance Sync Logs**: per-record outcome
  (success/skipped/failed) with the raw API payload and error message.
- **Odoo server log** (`odoo.log` or stdout): technical-level logging
  under the `odoo.addons.timeoffice_attendance_sync.models.attendance_sync`
  logger — authentication attempts, each API call, cron execution
  timing, and unexpected exceptions with full tracebacks.

## Resetting the sync cursor

If you need to re-pull attendance from further back (e.g. after fixing
a batch of `biometric_code`s), clear **Last Sync Time** via
Settings → Technical → System Parameters (search
`timeoffice_attendance_sync.last_sync_time`) and delete that
parameter, then click **Sync Now**. The next fetch will not send a
`since` filter and will pull everything the Time Office API returns.
