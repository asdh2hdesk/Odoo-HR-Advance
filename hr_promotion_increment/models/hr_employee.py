# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    promotion_ids = fields.One2many('hr.employee.promotion', 'employee_id', string='Promotions')
    promotion_count = fields.Integer(string='Promotion Count', compute='_compute_promotion_count')

    increment_ids = fields.One2many('hr.salary.increment', 'employee_id', string='Salary Increments')
    increment_count = fields.Integer(string='Increment Count', compute='_compute_increment_count')

    @api.depends('promotion_ids')
    def _compute_promotion_count(self):
        for employee in self:
            employee.promotion_count = len(employee.promotion_ids)

    @api.depends('increment_ids')
    def _compute_increment_count(self):
        for employee in self:
            employee.increment_count = len(employee.increment_ids)

    def action_view_promotions(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_promotion_increment.action_hr_employee_promotion")
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action

    def action_view_increments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_promotion_increment.action_hr_salary_increment")
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action
