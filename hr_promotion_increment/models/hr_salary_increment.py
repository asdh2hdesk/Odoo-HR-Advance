# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrSalaryIncrement(models.Model):
    _name = 'hr.salary.increment'
    _description = 'Salary Increment History'
    _order = 'effective_date desc, id desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', domain="[('employee_id', '=', employee_id)]")
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', store=True)

    increment_date = fields.Date(string='Proposal Date', default=fields.Date.context_today, required=True)
    effective_date = fields.Date(string='Effective Date', default=fields.Date.context_today, required=True)

    increment_type = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Monthly Amount'),
    ], string='Increment Mode', default='percentage', required=True)

    previous_wage = fields.Monetary(string='Previous Monthly Wage', currency_field='currency_id')
    previous_ctc = fields.Monetary(string='Previous Annual CTC', currency_field='currency_id')

    increment_value = fields.Float(string='Increment Value', default=0.0, required=True, help="Percentage (%) or Monthly Fixed Amount to add.")
    increment_amount_monthly = fields.Monetary(string='Monthly Salary Hike', currency_field='currency_id', compute='_compute_new_salary', store=True)

    new_wage = fields.Monetary(string='New Monthly Wage', currency_field='currency_id', compute='_compute_new_salary', store=True)
    new_ctc = fields.Monetary(string='New Annual CTC', currency_field='currency_id', compute='_compute_new_salary', store=True)

    reason = fields.Text(string='Increment Reason / Appraisal Note')
    notes = fields.Text(string='Internal Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Applied'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True, copy=False)

    display_name = fields.Char(string='Display Name', compute='_compute_display_name_field', store=True)

    @api.depends('employee_id.company_id', 'contract_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            if rec.contract_id and rec.contract_id.currency_id:
                rec.currency_id = rec.contract_id.currency_id
            elif rec.company_id and rec.company_id.currency_id:
                rec.currency_id = rec.company_id.currency_id
            else:
                rec.currency_id = self.env.company.currency_id

    @api.depends('employee_id', 'new_wage', 'effective_date')
    def _compute_display_name_field(self):
        for rec in self:
            if rec.employee_id:
                rec.display_name = f"Increment: {rec.employee_id.name} ({rec.effective_date or ''})"
            else:
                rec.display_name = _("New Salary Increment")

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            # Find active contract or latest contract
            open_contract = self.env['hr.contract'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', 'in', ['open', 'draft'])
            ], limit=1, order='state asc, id desc')
            if open_contract:
                self.contract_id = open_contract
                self.previous_wage = open_contract.wage
                if hasattr(open_contract, 'final_yearly_costs'):
                    self.previous_ctc = open_contract.final_yearly_costs
                else:
                    self.previous_ctc = open_contract.wage * 12.0

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.previous_wage = self.contract_id.wage
            if hasattr(self.contract_id, 'final_yearly_costs'):
                self.previous_ctc = self.contract_id.final_yearly_costs
            else:
                self.previous_ctc = self.contract_id.wage * 12.0

    @api.depends('previous_wage', 'previous_ctc', 'increment_type', 'increment_value')
    def _compute_new_salary(self):
        for rec in self:
            prev_wage = rec.previous_wage or 0.0
            prev_ctc = rec.previous_ctc or (prev_wage * 12.0)
            val = rec.increment_value or 0.0

            if rec.increment_type == 'percentage':
                monthly_hike = prev_wage * (val / 100.0)
            else:
                monthly_hike = val

            rec.increment_amount_monthly = monthly_hike
            rec.new_wage = prev_wage + monthly_hike
            rec.new_ctc = prev_ctc + (monthly_hike * 12.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.salary.increment') or _('New')
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft records can be approved."))
            rec.state = 'approved'

    def action_apply(self):
        """Apply the salary increment to the active contract."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_("Only approved salary increment records can be applied."))

            if rec.contract_id:
                contract_vals = {'wage': rec.new_wage}
                if hasattr(rec.contract_id, 'final_yearly_costs'):
                    contract_vals['final_yearly_costs'] = rec.new_ctc
                rec.contract_id.sudo().write(contract_vals)
                # Trigger structure recalculation if method exists
                if hasattr(rec.contract_id, '_recompute_structure_line_amounts'):
                    rec.contract_id._recompute_structure_line_amounts()

            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'
