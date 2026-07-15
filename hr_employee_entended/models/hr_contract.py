from odoo import fields, models, api

class HrContract(models.Model):
    _inherit = 'hr.contract'

    wage_on_signature = fields.Monetary(string="Offer Accepted Wage")

    default_structure_id = fields.Many2one(
        'hr.payroll.structure',
        compute='_compute_default_structure_id',
        string='Default Salary Structure',
        store=True,
        depends=['structure_type_id']
    )
    
    salary_rule_ids = fields.Many2many(
        'hr.salary.rule',
        compute='_compute_salary_rule_ids',
        string='Salary Rules',
        depends=['structure_type_id']
    )

    def _compute_default_structure_id(self):
        """Compute the default_structure_id based on structure_type_id."""
        for contract in self:
            contract.default_structure_id = contract.structure_type_id.default_struct_id

    def _compute_salary_rule_ids(self):
        """Compute salary_rule_ids by fetching all rule_ids from all struct_ids of structure_type_id."""
        for contract in self:
            if contract.structure_type_id and contract.structure_type_id.struct_ids:
                # Collect all rule_ids from all structures linked to structure_type_id
                all_rule_ids = contract.structure_type_id.struct_ids.mapped('rule_ids')
                contract.salary_rule_ids = [(6, 0, all_rule_ids.ids)] if all_rule_ids else False
            else:
                contract.salary_rule_ids = False

    def action_open_structure(self):
        """Open the form view of the default_structure_id."""
        self.ensure_one()
        if self.default_structure_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'hr.payroll.structure',
                'view_mode': 'form',
                'res_id': self.default_structure_id.id,
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}