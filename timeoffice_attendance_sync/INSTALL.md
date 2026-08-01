# Installation Guide

## Prerequisites

- Odoo 18.0 (Community or Enterprise)
- The `hr` and `hr_attendance` apps installed
- Server access to install/copy custom modules (or an Odoo.sh /
  supported hosting account with custom module support)
- Network access from the Odoo server to your Time Office API host
  (outbound HTTPS)

## Steps

1. **Copy the module** into your custom addons path:

   ```bash
   cp -r timeoffice_attendance_sync /path/to/your/addons/
   ```

2. **Update the apps list** (Settings → General Settings → activate
   developer mode if not already, then Apps → Update Apps List), or
   from the command line:

   ```bash
   ./odoo-bin -u base -d your_database --stop-after-init
   ```

3. **Install the module**:
   - Via UI: Apps → remove the "Apps" filter → search
     "Time Office Attendance Sync" → Install.
   - Via CLI:

     ```bash
     ./odoo-bin -i timeoffice_attendance_sync -d your_database --stop-after-init
     ```

4. **Assign HR Attendance groups** to the relevant users
   (Settings → Users & Companies → Users → Attendances field):
   - **Administrator** → can configure the API connection and run
     manual syncs.
   - **Officer** (`hr_attendance.group_hr_attendance_officer`) → can view
     imported attendance and sync logs, read-only.

5. Continue with [`CONFIGURATION.md`](CONFIGURATION.md) to connect the
   module to your Time Office API.

## Upgrading

```bash
./odoo-bin -u timeoffice_attendance_sync -d your_database --stop-after-init
```

Upgrading preserves all `ir.config_parameter` values (API URL,
credentials, endpoints) and the sync log history. The scheduled
action's interval is re-applied from the stored "Sync Interval"
setting on every save of the settings page.

## Uninstalling

Uninstalling removes the `attendance.sync.log` records, the
`biometric_code` field, and the scheduled action. Imported
`hr.attendance` records are **not** deleted, since they belong to the
standard `hr_attendance` module.
