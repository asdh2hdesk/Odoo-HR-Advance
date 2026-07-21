# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployeePromotion(models.Model):
    _name = 'hr.employee.promotion'
    _description = 'Employee Promotion History'
    _order = 'effective_date desc, id desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id', store=True, readonly=True)
    
    promotion_date = fields.Date(string='Promotion Proposal Date', default=fields.Date.context_today, required=True)
    effective_date = fields.Date(string='Effective Date', default=fields.Date.context_today, required=True)

    # Job Position Changes
    current_job_id = fields.Many2one('hr.job', string='Current Job Position', readonly=True)
    new_job_id = fields.Many2one('hr.job', string='New Job Position', required=True)

    # Department Changes
    current_department_id = fields.Many2one('hr.department', string='Current Department', readonly=True)
    new_department_id = fields.Many2one('hr.department', string='New Department')

    # Grade / Designation Changes
    current_grade = fields.Char(string='Current Grade / Designation')
    new_grade = fields.Char(string='New Grade / Designation')

    reason = fields.Text(string='Reason for Promotion')
    notes = fields.Text(string='Internal Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Applied'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True, copy=False)

    display_name = fields.Char(string='Display Name', compute='_compute_display_name_field', store=True)

    @api.depends('employee_id', 'new_job_id', 'effective_date')
    def _compute_display_name_field(self):
        for rec in self:
            if rec.employee_id and rec.new_job_id:
                rec.display_name = f"{rec.employee_id.name} -> {rec.new_job_id.name}"
            elif rec.employee_id:
                rec.display_name = f"Promotion: {rec.employee_id.name}"
            else:
                rec.display_name = _("New Promotion")

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.current_job_id = self.employee_id.job_id
            self.current_department_id = self.employee_id.department_id
            if not self.new_department_id:
                self.new_department_id = self.employee_id.department_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.promotion') or _('New')
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft records can be approved."))
            rec.state = 'approved'

    def action_apply(self):
        """Apply the promotion changes to the employee record."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_("Only approved promotion records can be applied."))
            
            update_vals = {}
            if rec.new_job_id:
                update_vals['job_id'] = rec.new_job_id.id
            if rec.new_department_id:
                update_vals['department_id'] = rec.new_department_id.id

            if update_vals:
                rec.employee_id.sudo().write(update_vals)
            
            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'
