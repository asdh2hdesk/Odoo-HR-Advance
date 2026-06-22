from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_rejoining_employee = fields.Boolean(
        string='Is Rejoining Employee', 
        default=False,
        tracking=True,
        help="Check this to indicate this is a returning employee."
    )
    previous_employee_id = fields.Many2one(
        'hr.employee', 
        string='Previous Employee', 
        domain=[('active', '=', False)],
        help="Linked archived employee record for the rejoining employee."
    )
    rejoin_history_count = fields.Integer(
        string='Rejoin History Count', 
        compute='_compute_rejoin_history_count'
    )

    # Disable the SQL constraint uniquely defining PAN if natively added (or harmless dummy if not)
    # So we can enforce it gracefully using an api.constrains instead
    _sql_constraints = [
        ('unique_l10n_in_pan', 'CHECK(1=1)', 'Overridden locally.')
    ]

    def _compute_rejoin_history_count(self):
        for rec in self:
            count = self.env['hr.employee.rejoin.history'].search_count([
                '|', ('employee_id', '=', rec.id), ('previous_employee_id', '=', rec.id)
            ])
            rec.rejoin_history_count = count

    def action_view_rejoining_history(self):
        self.ensure_one()
        return {
            'name': _('Rejoining History'),
            'view_mode': 'list,form',
            'res_model': 'hr.employee.rejoin.history',
            'domain': ['|', ('employee_id', '=', self.id), ('previous_employee_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_employee_id': self.id}
        }

    @api.constrains('l10n_in_pan', 'is_rejoining_employee', 'previous_employee_id')
    def _check_unique_pan_rejoin(self):
        """ Allow PAN duplication ONLY if the new employee is marked as rejoining and linked to the retired employee. """
        for employee in self:
            # We assume l10n_in_pan exists, gracefully getting it
            if not getattr(employee, 'l10n_in_pan', False):
                continue
            
            # Find any other employee with the same PAN
            domain = [('l10n_in_pan', '=', employee.l10n_in_pan), ('id', '!=', employee.id)]
            duplicates = self.env['hr.employee'].with_context(active_test=False).search(domain)
            
            if not duplicates:
                continue
                
            if not employee.is_rejoining_employee:
                raise ValidationError(_("A related PAN already exists. If this is a rejoining employee, please enable 'Is Rejoining Employee' and select the previous record."))
            
            if employee.is_rejoining_employee and employee.previous_employee_id:
                # Need to be sure the duplicate is ONLY the previous employee
                invalid_duplicates = duplicates.filtered(lambda d: d.id != employee.previous_employee_id.id)
                if invalid_duplicates:
                    raise ValidationError(_("Another employee apart from the selected previous employee utilizes this PAN!"))
            else:
                # If marked as rejoining but hasn't linked yet, we still fail
                raise ValidationError(_("Please link the Previous Employee record to correctly utilize this PAN."))

