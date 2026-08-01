# -*- coding: utf-8 -*-
{
    "name": "Time Office Attendance Sync",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Attendances",
    "summary": "Sync attendance logs from a cloud Time Office system into Odoo HR Attendance",
    "description": """
Time Office Attendance Sync
============================
Integrates a cloud-based Time Office attendance system with Odoo HR
Attendance using REST APIs.

Features
--------
* Configurable REST API connection (API Key / JWT / Basic Auth)
* Scheduled synchronization (ir.cron, configurable interval)
* Manual "Sync Now" action with live result summary
* Employee mapping via biometric_code
* Duplicate-safe attendance creation, overnight shift and
  missing-checkout handling
* Full sync log (attendance.sync.log) with search/filter
* Robust error handling (HTTP errors, timeouts, network failures,
  malformed JSON, unmapped employees, duplicates)
* Role-based security (HR Manager vs HR User)
* Extensible adapter/service layer for future Time Office vendors
""",
    "author": "Balaji Bathini",
    "website": "",
    "license": "LGPL-3",
    "depends": ["hr_attendance", "hr", "base"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/settings_views.xml",
        "views/sync_log_views.xml",
        "views/hr_employee_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
