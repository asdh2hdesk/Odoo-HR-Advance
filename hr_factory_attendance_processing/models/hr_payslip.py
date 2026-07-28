# -*- coding: utf-8 -*-
from odoo import api, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        """
        Override to trigger biometric attendance processing before generating payslip worked day lines.
        """
        for payslip in self:
            if payslip.contract_id and payslip.contract_id.use_factory_attendance and payslip.date_from and payslip.date_to:
                service = self.env['attendance.processor.service']
                summaries = service.process_attendance_range(
                    payslip.date_from,
                    payslip.date_to,
                    employee_ids=[payslip.employee_id.id]
                )
                for summary in summaries:
                    if summary.state in ['calculated', 'approved']:
                        summary.action_lock_and_generate_work_entries()

        return super()._get_worked_day_lines(domain=domain, check_out_of_contract=check_out_of_contract)
