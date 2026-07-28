# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta


class AttendanceProcessorWizard(models.TransientModel):
    _name = 'attendance.processor.wizard'
    _description = 'Batch Attendance Processing Wizard'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string='Start Date',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='End Date',
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('company_id', '=', company_id)]",
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        domain="[('company_id', '=', company_id)]",
    )
    auto_approve = fields.Boolean(
        string='Auto-Approve Summaries',
        default=False,
    )
    auto_generate_work_entries = fields.Boolean(
        string='Auto-Generate Work Entries',
        default=False,
    )

    def action_process(self):
        self.ensure_one()
        domain = [('active', '=', True), ('company_id', '=', self.company_id.id)]
        if self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        elif self.department_id:
            domain.append(('department_id', '=', self.department_id.id))

        employees = self.env['hr.employee'].search(domain)
        if not employees:
            return False

        service = self.env['attendance.processor.service']
        summaries = service.process_attendance_range(
            self.date_from,
            self.date_to,
            employee_ids=employees.ids,
            company_id=self.company_id.id
        )

        if self.auto_approve:
            summaries.action_approve()
        if self.auto_generate_work_entries:
            for s in summaries:
                s.action_lock_and_generate_work_entries()

        action = self.env["ir.actions.actions"]._for_xml_id("hr_factory_attendance_processing.attendance_daily_summary_action")
        action['domain'] = [('id', 'in', summaries.ids)]
        return action
