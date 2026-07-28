# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AttendanceDailySummary(models.Model):
    _name = 'attendance.daily.summary'
    _description = 'Daily Attendance Summary (Factory HR)'
    _order = 'date desc, employee_id asc'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        compute='_compute_contract_id',
        store=True,
        readonly=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        index=True,
    )
    first_in = fields.Datetime(
        string='First Check In',
        help='Earliest check-in timestamp of the day.',
    )
    last_out = fields.Datetime(
        string='Last Check Out',
        help='Latest check-out timestamp of the day.',
    )
    worked_hours = fields.Float(
        string='Worked Hours',
        digits=(16, 2),
        help='Total hours worked calculated by summing all attendance intervals.',
    )
    expected_hours = fields.Float(
        string='Expected Hours',
        digits=(16, 2),
        help='Standard daily hours defined in employee working schedule.',
    )
    regular_hours = fields.Float(
        string='Regular Hours',
        digits=(16, 2),
        help='Hours allocated to regular attendance work entry.',
    )
    ot_hours = fields.Float(
        string='Overtime Hours',
        digits=(16, 2),
        help='Hours allocated to overtime work entry.',
    )
    shortage_hours = fields.Float(
        string='Shortage Hours',
        digits=(16, 2),
        help='Shortage between expected hours and actual worked hours.',
    )
    day_type = fields.Selection(
        selection=[
            ('working_day', 'Normal Working Day'),
            ('weekoff', 'Weekly Off'),
            ('public_holiday', 'Public Holiday'),
            ('leave', 'Approved Leave'),
            ('half_day', 'Half Day Leave'),
            ('absent', 'Absent / LOP'),
        ],
        string='Day Classification',
        default='working_day',
        required=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('approved', 'Approved'),
            ('locked', 'Locked'),
        ],
        string='Status',
        default='draft',
        required=True,
        index=True,
        tracking=True,
    )
    attendance_ids = fields.Many2many(
        'hr.attendance',
        'attendance_daily_summary_rel',
        'summary_id',
        'attendance_id',
        string='Attendance Records',
    )
    work_entry_ids = fields.One2many(
        'hr.work.entry',
        'daily_summary_id',
        string='Generated Work Entries',
    )
    work_entry_count = fields.Integer(
        string='Work Entry Count',
        compute='_compute_work_entry_count',
    )
    notes = fields.Text(
        string='HR Notes',
    )

    _sql_constraints = [
        (
            'employee_date_uniq',
            'unique(employee_id, date)',
            'A daily attendance summary already exists for this employee on this date!'
        )
    ]

    @api.depends('employee_id', 'date', 'day_type')
    def _compute_name(self):
        day_type_labels = dict(self._fields['day_type'].selection)
        for record in self:
            emp_name = record.employee_id.name or 'Unknown Employee'
            date_str = fields.Date.to_string(record.date) if record.date else ''
            label = day_type_labels.get(record.day_type, '')
            record.name = f"{emp_name} - {date_str}"
            record.display_name = f"{emp_name} ({date_str}) [{label}]"

    @api.depends('employee_id', 'date')
    def _compute_contract_id(self):
        for record in self:
            if record.employee_id and record.date:
                contracts = self.env['hr.contract'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', 'in', ['open', 'close']),
                    ('date_start', '<=', record.date),
                    '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', record.date),
                ], limit=1, order='date_start desc')
                record.contract_id = contracts.id if contracts else False
            else:
                record.contract_id = False

    @api.depends('work_entry_ids')
    def _compute_work_entry_count(self):
        for record in self:
            record.work_entry_count = len(record.work_entry_ids)

    def action_approve(self):
        for record in self:
            if record.state in ['locked']:
                continue
            record.write({'state': 'approved'})
            if record.company_id.factory_auto_generate_work_entries:
                record.action_lock_and_generate_work_entries()

    def action_lock_and_generate_work_entries(self):
        service = self.env['attendance.processor.service']
        for record in self:
            if record.state == 'locked':
                continue
            service._generate_work_entries_for_summary(record)
            record.write({'state': 'locked'})

    def action_reset_to_draft(self):
        for record in self:
            if record.state == 'locked':
                # Delete generated work entries if unlocking
                record.work_entry_ids.unlink()
            record.write({'state': 'draft'})

    def action_recalculate(self):
        service = self.env['attendance.processor.service']
        for record in self:
            if record.state == 'locked':
                raise UserError(_("Cannot recalculate a locked summary. Unlock/reset to draft first."))
            service._process_single_employee_date(record.employee_id, record.date)

    def action_view_work_entries(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_work_entry.hr_work_entry_action")
        action['domain'] = [('id', 'in', self.work_entry_ids.ids)]
        return action
