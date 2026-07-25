# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.exceptions import UserError


class SalaryReportWizard2(models.TransientModel):
    _name = "salary.report.wizard.2"
    _description = "Salary Report 2.0 Launcher Wizard"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date", required=True)

    all_employee = fields.Boolean(string="All Employees", default=True)
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        domain="[('company_id', '=', company_id)]",
        context={'active_test': False},
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.today()
        from odoo.tools import date_utils
        res['date_from'] = date_utils.start_of(today, 'month')
        res['date_to'] = date_utils.end_of(today, 'month')
        return res

    def action_generate_complete_salary_report(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError("From Date cannot be greater than To Date")

        month_str = self.date_from.strftime('%B %Y')
        name = f"Salary Sheet - {month_str}"

        report = self.env['salary.report.2'].create({
            'name': name,
            'company_id': self.company_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'all_employee': self.all_employee,
            'employee_ids': [(6, 0, self.employee_ids.ids)],
        })

        # Fetch and compute line snapshots
        report.action_fetch_and_compute()

        # Return form view of the created persistent report snapshot
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'salary.report.2',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'main',
        }
