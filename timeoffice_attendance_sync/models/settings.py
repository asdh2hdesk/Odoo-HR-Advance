# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    """Time Office Settings page (Attendances > Configuration > Time
    Office Settings). Every field uses ``config_parameter`` so Odoo's
    settings framework reads/writes ir.config_parameter automatically.
    """

    _inherit = "res.config.settings"

    timeoffice_api_base_url = fields.Char(
        string="API Base URL",
        config_parameter="timeoffice_attendance_sync.api_base_url",
        help="Root URL of the Time Office REST API, e.g. "
        "https://timeoffice.example.com",
    )
    timeoffice_auth_type = fields.Selection(
        [
            ("api_key", "API Key"),
            ("jwt", "JWT"),
            ("basic", "Basic Authentication"),
        ],
        string="Authentication Type",
        config_parameter="timeoffice_attendance_sync.auth_type",
        default="api_key",
    )
    timeoffice_username = fields.Char(
        string="Username",
        config_parameter="timeoffice_attendance_sync.username",
    )
    timeoffice_password = fields.Char(
        string="Password",
        config_parameter="timeoffice_attendance_sync.password",
    )
    timeoffice_api_key = fields.Char(
        string="API Key",
        config_parameter="timeoffice_attendance_sync.api_key",
    )
    timeoffice_bearer_token = fields.Char(
        string="Bearer Token",
        config_parameter="timeoffice_attendance_sync.bearer_token",
    )
    timeoffice_attendance_endpoint = fields.Char(
        string="Attendance Endpoint",
        config_parameter="timeoffice_attendance_sync.attendance_endpoint",
        default="/api/attendance",
    )
    timeoffice_employee_endpoint = fields.Char(
        string="Employee Endpoint",
        config_parameter="timeoffice_attendance_sync.employee_endpoint",
        default="/api/employees",
    )
    timeoffice_sync_interval = fields.Integer(
        string="Sync Interval (minutes)",
        config_parameter="timeoffice_attendance_sync.sync_interval",
        default=5,
        help="How often the scheduled sync runs. Changing this updates "
        "the underlying scheduled action.",
    )
    timeoffice_company_code = fields.Char(
        string="Company Code",
        config_parameter="timeoffice_attendance_sync.company_code",
    )
    timeoffice_enable_auto_sync = fields.Boolean(
        string="Enable Automatic Sync",
        config_parameter="timeoffice_attendance_sync.enable_auto_sync",
        default=True,
    )
    timeoffice_last_sync_time = fields.Char(
        string="Last Sync Time",
        compute="_compute_timeoffice_dashboard",
    )

    # Dashboard (read-only, computed on open)
    timeoffice_imported_today = fields.Integer(
        string="Total Imported Today", compute="_compute_timeoffice_dashboard"
    )
    timeoffice_failed_records = fields.Integer(
        string="Failed Records", compute="_compute_timeoffice_dashboard"
    )
    timeoffice_pending_records = fields.Integer(
        string="Pending Records", compute="_compute_timeoffice_dashboard"
    )
    timeoffice_api_status = fields.Char(
        string="API Status", compute="_compute_timeoffice_dashboard"
    )

    def _compute_timeoffice_dashboard(self):
        data = self.env["timeoffice.attendance.sync"].get_dashboard_data()
        for record in self:
            record.timeoffice_imported_today = data["imported_today"]
            record.timeoffice_failed_records = data["failed_records"]
            record.timeoffice_pending_records = data["pending_records"]
            record.timeoffice_last_sync_time = data["last_sync_time"]
            record.timeoffice_api_status = _("Unknown - use Test Connection")

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_timeoffice_test_connection(self):
        self.ensure_one()
        success, message = self.env["timeoffice.attendance.sync"].test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection Successful") if success else _("Connection Failed"),
                "message": message,
                "type": "success" if success else "danger",
                "sticky": False,
            },
        }

    def action_timeoffice_sync_now(self):
        self.ensure_one()
        summary = self.env["timeoffice.attendance.sync"].sync_attendance(manual=True)
        if summary.get("error"):
            message = _("Sync failed: %s") % summary["error"]
            notif_type = "danger"
        else:
            message = _(
                "Imported: %(imported)s | Skipped: %(skipped)s | "
                "Failed: %(failed)s | Duration: %(duration)ss"
            ) % summary
            notif_type = "success" if not summary.get("failed") else "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Time Office Sync Result"),
                "message": message,
                "type": notif_type,
                "sticky": True,
            },
        }

    def set_values(self):
        super().set_values()
        # Keep the scheduled action's interval in sync with the
        # configured value so the cron actually runs at the requested
        # cadence.
        cron = self.env.ref(
            "timeoffice_attendance_sync.ir_cron_sync_attendance",
            raise_if_not_found=False,
        )
        if cron and self.timeoffice_sync_interval:
            cron.sudo().write(
                {
                    "interval_number": self.timeoffice_sync_interval,
                    "interval_type": "minutes",
                    "active": bool(self.timeoffice_enable_auto_sync),
                }
            )
