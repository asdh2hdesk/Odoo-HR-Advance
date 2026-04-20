# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrContract(models.Model):
    _inherit = 'hr.contract'

    # ----- Salary Structure Fields -----
    salary_structure_id = fields.Many2one(
        'salary.config.structure',
        string='Salary Structure Template',
        help='Select a salary structure template to auto-populate salary lines.',
        tracking=True,
    )
    salary_structure_line_ids = fields.One2many(
        'hr.contract.salary.structure.line',
        'contract_id',
        string='Salary Structure Lines',
        copy=True,
    )

    def get_salary_breakdown_amount(self, code):
        """Helper for Standard Salary Rules to get breakdown values from custom config."""
        self.ensure_one()
        line = self.salary_structure_line_ids.filtered(lambda l: l.code == code)[:1]
        return line.amount_monthly if line else 0.0

    # Bonus field - additional allowance
    bonus_amount = fields.Monetary(
        string='Bonus',
        currency_field='currency_id',
        default=1200.0,
        help='Monthly bonus amount. Default is 1200.',
        tracking=True,
    )

    # PF deduction toggle
    is_pf_deduct = fields.Boolean(
        string='PF Deduction',
        default=False,
        help='If enabled, PF will be deducted from salary. PF is calculated as: if (Basic+HRA+Conveyance+LTA) >= 15000 then 15000, else round(Basic+HRA+Conveyance+LTA).',
        tracking=True,
    )

    # Computed summary fields (using final_yearly_costs from hr_contract_salary)
    inhand_salary = fields.Monetary(
        string='In Hand Salary',
        currency_field='currency_id',
        compute='_compute_inhand_salary',
        store=True,
        help='Monthly In Hand Salary derived from the INHAND line.',
    )
    gross_salary = fields.Monetary(
        string='Gross Salary',
        currency_field='currency_id',
        compute='_compute_gross_salary',
        store=True,
        help='Monthly Gross Salary derived from the GROSS line.',
    )
    current_company_name = fields.Char(
        string="Current Company",
        default=lambda self: self.env.company.name
    )
    
    # Note: final_yearly_costs and monthly_yearly_costs are inherited from hr_contract_salary
    @api.depends('salary_structure_line_ids.amount_monthly')
    def _compute_inhand_salary(self):
        for contract in self:
            inhand_line = contract.salary_structure_line_ids.filtered(
                lambda l: l.code == 'INHAND'
            )[:1]
            contract.inhand_salary = float(inhand_line.amount_monthly) if inhand_line else 0.0

    @api.depends('monthly_yearly_costs', 'bonus_amount')
    def _compute_gross_salary(self):
        """Gross Salary = Monthly CTC - Bonus Amount"""
        for contract in self:
            monthly_ctc = contract.monthly_yearly_costs or 0.0
            bonus = contract.bonus_amount or 0.0
            contract.gross_salary = monthly_ctc - bonus

    # ----- Onchange & Recomputation -----
    @api.onchange('final_yearly_costs')
    def _onchange_final_yearly_costs_salary_lines(self):
        """Recompute salary structure line amounts when CTC changes."""
        self._recompute_structure_line_amounts()

    @api.onchange('bonus_amount')
    def _onchange_bonus_amount(self):
        """Recompute salary structure line amounts when bonus changes."""
        self._recompute_structure_line_amounts()

    @api.onchange('is_pf_deduct')
    def _onchange_is_pf_deduct(self):
        """Recompute salary structure line amounts when PF deduct toggle changes."""
        self._recompute_structure_line_amounts()

    @api.onchange('salary_structure_id')
    def _onchange_salary_structure_id(self):
        """Populate salary structure lines from selected template."""
        if self.salary_structure_id:
            self._apply_salary_structure_template()

    @api.onchange('salary_structure_line_ids')
    def _onchange_salary_structure_line_ids(self):
        """Recompute amounts when lines are edited."""
        self._recompute_structure_line_amounts()

    @api.onchange('structure_type_id')
    def _onchange_structure_type_id_salary(self):
        """Auto-select salary structure from structure type if available.
        
        When user changes the Salary Structure Type (structure_type_id), 
        automatically set the salary_structure_id from the structure type's 
        salary_config_structure_id field and populate the salary lines.
        """
        if self.structure_type_id and self.structure_type_id.salary_config_structure_id:
            # Always update salary_structure_id to match structure type's default
            self.salary_structure_id = self.structure_type_id.salary_config_structure_id
            # Only apply template if no lines exist or if structure changed
            self._apply_salary_structure_template()
        elif self.structure_type_id and not self.structure_type_id.salary_config_structure_id:
            # Clear salary structure if structure type has no default
            self.salary_structure_id = False

    # ----- Business Logic -----
    def _apply_salary_structure_template(self):
        """Copy lines from salary structure template to contract."""
        self.ensure_one()
        if not self.salary_structure_id:
            return

        lines_vals = []
        for line in self.salary_structure_id.line_ids.filtered(lambda l: l.show_in_offer):
            lines_vals.append((0, 0, {
                'name': line.name,
                'code': line.code,
                'code_id': line.code_id.id if line.code_id else False,
                'sequence': line.sequence,
                'impact': line.impact,
                'compute_mode': line.compute_mode,
                'value': line.value,
                'python_code': line.python_code,
            }))

        if lines_vals:
            # Clear existing lines and add new ones
            self.salary_structure_line_ids = [(5, 0, 0)] + lines_vals
            self._recompute_structure_line_amounts()

    def _recompute_structure_line_amounts(self):
        """Recompute all structure line amounts with formula dependencies."""
        for contract in self:
            sorted_lines = contract.salary_structure_line_ids.sorted(
                key=lambda x: (x.sequence or 0, (x.code or '').lower(), (x.name or '').lower())
            )
            # Multi-pass to resolve formula dependencies (max 4 passes)
            for _ in range(4):
                changed = False
                for line in sorted_lines:
                    old_amount = float(line.amount_monthly or 0.0)
                    new_amount = float(line._compute_amount_from_contract() or 0.0)
                    if abs(new_amount - old_amount) > 0.005:
                        line.amount_monthly = new_amount
                        changed = True
                if not changed:
                    break

    # ----- CRUD Overrides -----
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for contract in records:
            # Auto-apply salary structure from structure type if set
            if contract.structure_type_id and contract.structure_type_id.salary_config_structure_id:
                if not contract.salary_structure_line_ids:
                    contract.salary_structure_id = contract.structure_type_id.salary_config_structure_id
                    contract._apply_salary_structure_template()
            elif contract.salary_structure_id and not contract.salary_structure_line_ids:
                contract._apply_salary_structure_template()
            else:
                contract._recompute_structure_line_amounts()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Recompute line amounts when CTC, bonus, PF deduct, or structure changes
        if 'final_yearly_costs' in vals or 'bonus_amount' in vals or 'is_pf_deduct' in vals or 'salary_structure_line_ids' in vals:
            self._recompute_structure_line_amounts()
        return res

    def action_refresh_salary_structure(self):
        """Button action to refresh salary structure from template."""
        for contract in self:
            if contract.salary_structure_id:
                contract._apply_salary_structure_template()
        return True

    def action_recompute_salary_amounts(self):
        """Button action to recompute all salary line amounts."""
        self._recompute_structure_line_amounts()
        return True


class HrContractSalaryStructureLine(models.Model):
    _name = 'hr.contract.salary.structure.line'
    _description = 'Contract Salary Structure Line'
    _order = 'sequence, id'

    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Component Name', required=True)
    code_id = fields.Many2one(
        'hr.salary.rule.category',
        string='Salary Rule Category',
        help='Payroll salary rule category used for formulas and reporting.',
    )
    code = fields.Char(
        string='Code',
        help='Technical code for referencing in formulas (e.g., BASIC, HRA, PF).',
    )
    impact = fields.Selection([
        ('cost', 'Employer Cost'),
        ('benefit', 'Benefit'),
        ('deduction', 'Deduction'),
    ], default='cost', required=True, string='Type')
    compute_mode = fields.Selection([
        ('percent_yearly', 'Percent of Annual CTC'),
        ('fixed_monthly', 'Fixed Monthly Amount'),
        ('formula', 'Python Formula'),
    ], default='percent_yearly', required=True, string='Compute Mode')
    value = fields.Float(
        string='Value',
        help='Percentage (e.g., 50 for 50%) or fixed monthly amount depending on mode.',
    )
    python_code = fields.Text(
        string='Python Formula',
        help='Python expression. Variables: final_yearly_costs, monthly_yearly_costs, bonus, amount(code). Assign result.',
        default='result = monthly_yearly_costs * 0.0',
    )
    amount_monthly = fields.Monetary(
        string='Monthly Amount',
        currency_field='currency_id',
        store=True,
    )
    amount_annual = fields.Monetary(
        string='Annual Amount',
        currency_field='currency_id',
        compute='_compute_amount_annual',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='contract_id.currency_id',
        readonly=True,
    )

    @api.depends('amount_monthly')
    def _compute_amount_annual(self):
        for line in self:
            line.amount_annual = (line.amount_monthly or 0.0) * 12.0

    def _compute_amount_from_contract(self):
        """Compute the monthly amount based on compute_mode and contract CTC."""
        self.ensure_one()
        contract = self.contract_id
        # Use final_yearly_costs and monthly_yearly_costs from hr_contract_salary
        final_yearly_costs = float(contract.final_yearly_costs or 0.0)
        monthly_yearly_costs = float(contract.monthly_yearly_costs or 0.0)
        bonus = float(contract.bonus_amount or 0.0)
        is_pf_deduct = bool(contract.is_pf_deduct)

        if self.compute_mode == 'percent_yearly':
            # Percentage of monthly CTC (final_yearly_costs / 12)
            return monthly_yearly_costs * (float(self.value or 0.0) / 100.0)

        elif self.compute_mode == 'fixed_monthly':
            return float(self.value or 0.0)

        elif self.compute_mode == 'formula':
            # Build amounts dict from other lines
            all_lines = contract.salary_structure_line_ids
            amounts_by_code = {
                l.code: float(l.amount_monthly or 0.0)
                for l in all_lines
                if l.code and l.id != self.id
            }

            localdict = {
                # Primary variables (from hr_contract_salary)
                'final_yearly_costs': final_yearly_costs,
                'monthly_yearly_costs': monthly_yearly_costs,
                'bonus': bonus,
                'is_pf_deduct': is_pf_deduct,  # PF deduction toggle
                # Aliases for backward compatibility
                'annual_ctc': final_yearly_costs,
                'monthly_ctc': monthly_yearly_costs,
                'monthly_budget': monthly_yearly_costs,
                # Helper functions to get amounts by code
                'get': lambda code: float(amounts_by_code.get(code, 0.0)),
                'amount': lambda code: float(amounts_by_code.get(code, 0.0)),
                # Built-in functions for formulas
                'round': round,
                'min': min,
                'max': max,
                'abs': abs,
                # Aggregate helpers
                'sum_cost': sum(
                    float(l.amount_monthly or 0.0)
                    for l in all_lines
                    if l.id != self.id and l.impact == 'cost'
                ),
                'sum_benefit': sum(
                    float(l.amount_monthly or 0.0)
                    for l in all_lines
                    if l.id != self.id and l.impact == 'benefit'
                ),
                'sum_deduction': sum(
                    float(l.amount_monthly or 0.0)
                    for l in all_lines
                    if l.id != self.id and l.impact == 'deduction'
                ),
                'result': 0.0,
            }

            try:
                exec((self.python_code or ''), {}, localdict)
                return float(localdict.get('result') or 0.0)
            except Exception:
                return 0.0

        return 0.0

    # ----- Onchange Methods -----
    @api.onchange('code_id')
    def _onchange_code_id(self):
        for rec in self:
            if rec.code_id:
                rec.code = rec.code_id.code

    @api.onchange('code')
    def _onchange_code(self):
        for rec in self:
            if rec.code and not rec.code_id:
                category = self.env['hr.salary.rule.category'].search(
                    [('code', '=', rec.code)], limit=1
                )
                if category:
                    rec.code_id = category

    @api.onchange('compute_mode', 'value', 'python_code')
    def _onchange_recompute_amount(self):
        for rec in self:
            rec.amount_monthly = rec._compute_amount_from_contract()

    # ----- CRUD Overrides -----
    @api.model_create_multi
    def create(self, vals_list):
        Category = self.env['hr.salary.rule.category']
        prepared_vals = []
        for vals in vals_list:
            vals = dict(vals)
            code = (vals.get('code') or '').strip()
            code_id = vals.get('code_id')

            # Auto-link code_id and code
            if code_id and not code:
                category = Category.browse(code_id)
                if category:
                    vals['code'] = category.code
            elif code and not code_id:
                category = Category.search([('code', '=', code)], limit=1)
                if category:
                    vals['code_id'] = category.id

            prepared_vals.append(vals)

        records = super().create(prepared_vals)
        for rec in records:
            rec.amount_monthly = rec._compute_amount_from_contract()
        return records

    def write(self, vals):
        Category = self.env['hr.salary.rule.category']
        vals_to_write = dict(vals)

        # Sync code and code_id
        if 'code_id' in vals_to_write and 'code' not in vals_to_write:
            code_id = vals_to_write['code_id']
            if code_id:
                category = Category.browse(code_id)
                vals_to_write['code'] = category.code if category else False
            else:
                vals_to_write['code'] = False

        res = super().write(vals_to_write)

        # Recompute amount if relevant fields changed
        if {'compute_mode', 'value', 'python_code', 'code', 'contract_id'} & set(vals_to_write.keys()):
            for rec in self:
                rec.amount_monthly = rec._compute_amount_from_contract()

        # Auto-link code to category
        if 'code' in vals_to_write and not vals_to_write.get('code_id'):
            for rec in self:
                if rec.code and not rec.code_id:
                    category = Category.search([('code', '=', rec.code)], limit=1)
                    if category:
                        rec.code_id = category

        return res
