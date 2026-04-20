# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    employee_code = fields.Char(
        string='Employee Code',
        related='employee_id.employee_code',
        store=True,
        readonly=True,
    )

    def _get_localdict(self):
        """Magic Fix: Inject custom variables into the calculation context."""
        localdict = super()._get_localdict()
        contract = localdict.get('contract')
        
        # Pull values from the custom breakdown and context
        if contract:
            # Add variables expected by the user's custom formulas
            localdict.update({
                'final_yearly_costs': float(contract.final_yearly_costs or 0.0),
                'monthly_yearly_costs': float(contract.monthly_yearly_costs or 0.0),
                'annual_ctc': float(contract.final_yearly_costs or 0.0),
                'monthly_ctc': float(contract.monthly_yearly_costs or 0.0),
                'amount': lambda code: contract.get_salary_breakdown_amount(code),
                'get': lambda code: contract.get_salary_breakdown_amount(code),
            })
        return localdict
