# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = 'hr.contract'

    use_factory_attendance = fields.Boolean(
        string='Use Factory Attendance Pipeline',
        default=True,
        help='If enabled, work entries are generated via biometric attendance processing instead of fixed calendar intervals.',
    )

    def _generate_work_entries(self, date_start, date_stop, force=False):
        """
        Override to integrate factory attendance processing pipeline.
        """
        factory_contracts = self.filtered(lambda c: c.use_factory_attendance)
        other_contracts = self - factory_contracts

        res = self.env['hr.work.entry']
        if other_contracts:
            res |= super(HrContract, other_contracts)._generate_work_entries(date_start, date_stop, force=force)

        if factory_contracts:
            service = self.env['attendance.processor.service']
            employees = factory_contracts.mapped('employee_id')
            summaries = service.process_attendance_range(date_start, date_stop, employee_ids=employees.ids)
            for summary in summaries:
                if summary.state in ['calculated', 'approved']:
                    summary.action_lock_and_generate_work_entries()
                    res |= summary.work_entry_ids

        return res


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    daily_summary_id = fields.Many2one(
        'attendance.daily.summary',
        string='Attendance Daily Summary',
        ondelete='set null',
        index=True,
    )
