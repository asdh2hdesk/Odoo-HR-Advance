# -*- coding: utf-8 -*-
from odoo import fields, models


class AttendanceSyncLog(models.Model):
    """One row per attendance record processed by a sync run (success,
    skip or failure). Gives HR full traceability of what the Time
    Office integration did on every cron / manual run."""

    _name = "attendance.sync.log"
    _description = "Time Office Attendance Sync Log"
    _order = "sync_time desc, id desc"
    _rec_name = "employee_code"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        index=True,
        help="Odoo employee matched by biometric_code, if found.",
    )
    employee_code = fields.Char(
        string="Employee Code",
        index=True,
        help="Raw employee_code as received from the Time Office API.",
    )
    check_in = fields.Datetime(string="Check In")
    check_out = fields.Datetime(string="Check Out")
    attendance_id = fields.Many2one(
        "hr.attendance",
        string="Attendance Record",
        help="The hr.attendance record created/updated by this entry, "
        "if any.",
    )
    api_response = fields.Text(
        string="API Response",
        help="Raw JSON payload for this record, kept for troubleshooting.",
    )
    status = fields.Selection(
        [
            ("success", "Success"),
            ("skipped", "Skipped (Duplicate)"),
            ("failed", "Failed"),
        ],
        string="Status",
        required=True,
        default="success",
        index=True,
    )
    error_message = fields.Text(string="Error Message")
    sync_time = fields.Datetime(
        string="Sync Time",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
