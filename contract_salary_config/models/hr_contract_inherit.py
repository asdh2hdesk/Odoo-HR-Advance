# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup


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

    def _get_breakdown_line(self, code_or_category):
        """Find matching contract salary component line by code, name, category, or alias."""
        self.ensure_one()
        if not code_or_category:
            return False

        target = str(code_or_category).strip().upper()

        # 1. Exact match on line.code (case-insensitive)
        line = self.salary_structure_line_ids.filtered(
            lambda l: l.code and l.code.strip().upper() == target
        )[:1]

        # 2. Match by line.name (case-insensitive & substring match)
        if not line:
            line = self.salary_structure_line_ids.filtered(
                lambda l: l.name and (
                    l.name.strip().upper() == target or
                    target in l.name.strip().upper() or
                    l.name.strip().upper() in target
                )
            )[:1]

        # 3. Match by Salary Rule Category (code_id.code or code_id.name)
        if not line:
            line = self.salary_structure_line_ids.filtered(
                lambda l: l.code_id and (
                    (l.code_id.code and l.code_id.code.strip().upper() == target) or
                    (l.code_id.name and l.code_id.name.strip().upper() == target)
                )
            )[:1]

        # 4. Common Code Aliases
        if not line:
            alias_map = {
                'BASIC_SALARY': ['BASIC', 'BASIC SALARY'],
                'BASIC': ['BASIC_SALARY', 'BASIC SALARY'],
                'HRA': ['HOUSE RENT ALLOWANCE', 'HOUSE_RENT_ALLOWANCE', 'HOUSE RENT'],
                'HOUSE RENT ALLOWANCE': ['HRA', 'HOUSE_RENT'],
                'CONV': ['CONVEYANCE', 'CONVEYANCE ALLOWANCE', 'CONVEYANCE ALLOWNCE', 'TRANSPORT'],
                'CONVEYANCE': ['CONV', 'CONVEYANCE ALLOWANCE', 'CONVEYANCE ALLOWNCE', 'TRANSPORT'],
                'CONVEYANCE ALLOWNCE': ['CONV', 'CONVEYANCE', 'CONVEYANCE ALLOWANCE'],
                'LTA': ['LEAVE TRAVEL ALLOWANCE', 'LTA REIMBURS.', 'LTA_REIMB'],
                'OTHER_ALW': ['OTHER ALLOWANCE', 'OTHER_ALLOWANCE', 'OTHER', 'SUPPLEMENTARY'],
                'OTHER ALLOWANCE': ['OTHER_ALW', 'OTHER_ALLOWANCE', 'OTHER'],
                'BONUS': ['GROSS_BONUS', 'BONUS'],
                'GROSS': ['TOTAL', 'PAYABLE', 'GROSS SALARY', 'TOTAL GROSS EARNING'],
                'TOTAL': ['GROSS', 'PAYABLE', 'GROSS SALARY', 'TOTAL GROSS EARNING'],
                'INHAND': ['NET', 'NET SALARY', 'IN HAND SALARY'],
            }
            aliases = alias_map.get(target, [])
            for alias in aliases:
                line = self.salary_structure_line_ids.filtered(
                    lambda l: (l.code and l.code.strip().upper() == alias) or
                              (l.name and l.name.strip().upper() == alias) or
                              (l.code_id and l.code_id.code and l.code_id.code.strip().upper() == alias) or
                              (l.code_id and l.code_id.name and l.code_id.name.strip().upper() == alias)
                )[:1]
                if line:
                    break

        return line

    def has_salary_breakdown_line(self, code_or_category):
        """Check if contract has a component line matching the given code or category."""
        self.ensure_one()
        return bool(self._get_breakdown_line(code_or_category))

    def get_salary_breakdown_amount(self, code_or_category):
        """Helper for Standard Salary Rules to get breakdown values from custom config."""
        self.ensure_one()
        line = self._get_breakdown_line(code_or_category)
        return float(line.amount_monthly or 0.0) if line else 0.0

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
        help='If enabled, PF will be deducted from salary. PF is calculated as: if (Basic+HRA) >= 15000 then 15000, else round(Basic+HRA).',
        tracking=True,
    )

    # ESIC deduction toggle
    is_esic_deduct = fields.Boolean(
        string='ESIC Deduction',
        default=False,
        help='If enabled, ESIC will be deducted from salary.',
        tracking=True,
    )

    # Computed summary fields (using final_yearly_costs from hr_contract_salary)
    inhand_salary = fields.Monetary(
        string='In Hand Salary',
        currency_field='currency_id',
        compute='_compute_inhand_salary',
        store=True,
        help='Monthly In Hand Salary derived from the INHAND line.',
        tracking=True,
    )
    gross_salary = fields.Monetary(
        string='Gross Salary',
        currency_field='currency_id',
        compute='_compute_gross_salary',
        store=True,
        help='Monthly Gross Salary derived from the GROSS line.',
        tracking=True,
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

    @api.depends('monthly_yearly_costs', 'salary_structure_line_ids.amount_monthly')
    def _compute_gross_salary(self):
        """Gross Salary = Monthly CTC - PF - ESIC"""
        for contract in self:
            monthly_ctc = contract.monthly_yearly_costs or 0.0
            pf_line = contract.salary_structure_line_ids.filtered(
                lambda l: l.code in ('PF', 'PF_EMP')
            )[:1]
            esic_line = contract.salary_structure_line_ids.filtered(
                lambda l: l.code in ('ESIC', 'ESIC_EMP')
            )[:1]
            pf_amount = float(pf_line.amount_monthly or 0.0) if pf_line else 0.0
            esic_amount = float(esic_line.amount_monthly or 0.0) if esic_line else 0.0
            contract.gross_salary = monthly_ctc - pf_amount - esic_amount

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

    @api.onchange('is_esic_deduct')
    def _onchange_is_esic_deduct(self):
        """Recompute salary structure line amounts when ESIC deduct toggle changes."""
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
        """Copy/sync lines from salary structure template to contract respecting employee overrides."""
        self._sync_salary_structure_from_template()

    def _sync_salary_structure_from_template(self):
        """Single central method for syncing contract salary lines with master template."""
        summary_stats = {'updated': 0, 'preserved': 0, 'added': 0, 'removed': 0}
        for contract in self:
            if not contract.salary_structure_id:
                continue

            template_lines = contract.salary_structure_id.line_ids.filtered(lambda l: l.show_in_offer)
            template_line_ids = set(template_lines.ids)

            existing_lines_by_tmpl = {
                line.template_line_id.id: line 
                for line in contract.salary_structure_line_ids 
                if line.template_line_id
            }
            existing_lines_by_code = {
                line.code: line 
                for line in contract.salary_structure_line_ids 
                if line.code and not line.template_line_id
            }

            ctx_sync = dict(self.env.context, from_template_sync=True)

            for t_line in template_lines:
                c_line = existing_lines_by_tmpl.get(t_line.id) or existing_lines_by_code.get(t_line.code)
                if c_line:
                    if not c_line.is_override:
                        # Update template-controlled component
                        c_line.with_context(ctx_sync).write({
                            'name': t_line.name,
                            'code': t_line.code,
                            'code_id': t_line.code_id.id if t_line.code_id else False,
                            'sequence': t_line.sequence,
                            'impact': t_line.impact,
                            'compute_mode': t_line.compute_mode,
                            'value': t_line.value,
                            'python_code': t_line.python_code,
                            'template_line_id': t_line.id,
                        })
                        summary_stats['updated'] += 1
                    else:
                        # Preserve overridden component (do NOT alter compute_mode, value, python_code)
                        if not c_line.template_line_id:
                            c_line.with_context(ctx_sync).write({'template_line_id': t_line.id})
                        summary_stats['preserved'] += 1
                else:
                    # Add new template component
                    contract.env['hr.contract.salary.structure.line'].with_context(ctx_sync).create({
                        'contract_id': contract.id,
                        'name': t_line.name,
                        'code': t_line.code,
                        'code_id': t_line.code_id.id if t_line.code_id else False,
                        'sequence': t_line.sequence,
                        'impact': t_line.impact,
                        'compute_mode': t_line.compute_mode,
                        'value': t_line.value,
                        'python_code': t_line.python_code,
                        'template_line_id': t_line.id,
                        'is_override': False,
                    })
                    summary_stats['added'] += 1

            # Clean up template lines removed from master (if not overridden)
            for c_line in list(contract.salary_structure_line_ids):
                if c_line.template_line_id and c_line.template_line_id.id not in template_line_ids:
                    if not c_line.is_override:
                        c_line.with_context(ctx_sync).unlink()
                        summary_stats['removed'] += 1
                    else:
                        summary_stats['preserved'] += 1

            contract._recompute_structure_line_amounts()
        return summary_stats

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
        # Capture old line values before write
        old_data = {}
        for contract in self:
            old_data[contract.id] = {
                line.id: {
                    'name': line.name or '',
                    'code': line.code or '',
                    'value': line.value or 0.0,
                    'compute_mode': line.compute_mode or '',
                    'amount_monthly': line.amount_monthly or 0.0,
                }
                for line in contract.salary_structure_line_ids
            }

        res = super().write(vals)

        # Recompute line amounts when CTC, bonus, PF deduct, or structure changes
        if 'final_yearly_costs' in vals or 'bonus_amount' in vals or 'is_pf_deduct' in vals or 'salary_structure_line_ids' in vals:
            self._recompute_structure_line_amounts()

        if 'final_yearly_costs' in vals or 'bonus_amount' in vals or 'is_pf_deduct' in vals or 'is_esic_deduct' in vals or 'salary_structure_line_ids' in vals:
            self._recompute_structure_line_amounts()

        # Track line-level changes in chatter
        for contract in self:
            old_lines = old_data.get(contract.id, {})
            new_lines = {
                line.id: {
                    'name': line.name or '',
                    'code': line.code or '',
                    'value': line.value or 0.0,
                    'compute_mode': line.compute_mode or '',
                    'amount_monthly': line.amount_monthly or 0.0,
                }
                for line in contract.salary_structure_line_ids
            }

            changes = []
            symbol = (contract.currency_id.symbol + ' ') if contract.currency_id and contract.currency_id.symbol else ''
            fmt = lambda amt: f"{symbol}{amt:,.2f}"

            # Check modified lines and deleted lines
            for l_id, old_l in old_lines.items():
                if l_id in new_lines:
                    new_l = new_lines[l_id]
                    line_changes = []
                    if abs(old_l['value'] - new_l['value']) > 0.001:
                        line_changes.append(_("Value / %%: %s → %s") % (old_l['value'], new_l['value']))
                    if abs(old_l['amount_monthly'] - new_l['amount_monthly']) > 0.01:
                        line_changes.append(_("Monthly Amount: %s → %s") % (fmt(old_l['amount_monthly']), fmt(new_l['amount_monthly'])))
                    if old_l['compute_mode'] != new_l['compute_mode']:
                        line_changes.append(_("Compute Mode: %s → %s") % (old_l['compute_mode'], new_l['compute_mode']))
                    if old_l['name'] != new_l['name']:
                        line_changes.append(_("Name: %s → %s") % (old_l['name'], new_l['name']))

                    if line_changes:
                        changes.append("<li><b>%s</b>: %s</li>" % (new_l['name'], ", ".join(line_changes)))
                else:
                    changes.append("<li><b>%s</b>: <i>Component Removed</i></li>" % old_l['name'])

            # Check added lines
            for l_id, new_l in new_lines.items():
                if l_id not in old_lines:
                    changes.append("<li><b>%s</b>: <i>Component Added</i> (Value: %s, Monthly: %s)</li>" % (new_l['name'], new_l['value'], fmt(new_l['amount_monthly'])))

            if changes:
                body = "<p><b>Salary Component Changes:</b></p><ul>%s</ul>" % "".join(changes)
                contract.message_post(body=Markup(body))

        return res

    def action_refresh_salary_structure(self):
        """Button action to refresh salary structure from template."""
        stats = self._sync_salary_structure_from_template()
        msg = _(
            "%(contracts)d contract(s) reloaded from template.\n"
            "Summary: %(updated)d updated, %(preserved)d custom override(s) preserved, %(added)d new component(s) added."
        ) % {
            'contracts': len(self),
            'updated': stats['updated'],
            'preserved': stats['preserved'],
            'added': stats['added'],
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reload from Template'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_recompute_salary_amounts(self):
        """Button action to recompute all salary line amounts."""
        self._recompute_structure_line_amounts()
        return True


    def action_set_to_running(self):
        """Action invoked from Contracts list view (Actions menu) to set selected draft contracts to Running ('open') state."""
        draft_contracts = self.filtered(lambda c: c.state == 'draft')
        if not draft_contracts:
            raise UserError(_("No contracts in 'New' (Draft) state were selected."))
        draft_contracts.write({'state': 'open'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contracts Updated'),
                'message': _('%d contract(s) set to Running state!') % len(draft_contracts),
                'type': 'success',
                'sticky': False,
            }
        }


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
    template_line_id = fields.Many2one(
        'salary.config.structure.line',
        string='Template Line',
        ondelete='set null',
        help='Master template line this component was initialized from.',
    )
    is_override = fields.Boolean(
        string='Override Template',
        default=False,
        help='If checked, this component configuration is customized for this employee contract and will be preserved during template reloads.',
    )
    source_display = fields.Selection([
        ('template', 'Template'),
        ('override', 'Custom Override'),
    ], string='Source', compute='_compute_source_display', store=True)

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

    @api.depends('is_override')
    def _compute_source_display(self):
        for line in self:
            line.source_display = 'override' if line.is_override else 'template'

    def action_customize_line(self):
        """Action to mark line as custom override."""
        self.write({'is_override': True})
        return True

    def action_use_template_value(self):
        """Action to reset line to master template value."""
        for line in self:
            if line.template_line_id:
                t_line = line.template_line_id
                ctx_sync = dict(self.env.context, from_template_sync=True)
                line.with_context(ctx_sync).write({
                    'is_override': False,
                    'name': t_line.name,
                    'code': t_line.code,
                    'code_id': t_line.code_id.id if t_line.code_id else False,
                    'sequence': t_line.sequence,
                    'impact': t_line.impact,
                    'compute_mode': t_line.compute_mode,
                    'value': t_line.value,
                    'python_code': t_line.python_code,
                })
                line.amount_monthly = line._compute_amount_from_contract()
            else:
                line.write({'is_override': False})
        if self.mapped('contract_id'):
            self.mapped('contract_id')._recompute_structure_line_amounts()
        return True

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
        is_esic_deduct = bool(contract.is_esic_deduct)

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
                if l.code and l != self
            }

            localdict = {
                # Primary variables (from hr_contract_salary)
                'final_yearly_costs': final_yearly_costs,
                'monthly_yearly_costs': monthly_yearly_costs,
                'bonus': bonus,
                'is_pf_deduct': is_pf_deduct,  # PF deduction toggle
                'is_esic_deduct': is_esic_deduct,
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
                    if l != self and l.impact == 'cost'
                ),
                'sum_benefit': sum(
                    float(l.amount_monthly or 0.0)
                    for l in all_lines
                    if l != self and l.impact == 'benefit'
                ),
                'sum_deduction': sum(
                    float(l.amount_monthly or 0.0)
                    for l in all_lines
                    if l != self and l.impact == 'deduction'
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

        # Auto mark override if calculation parameters are modified by user (not system sync)
        if not self.env.context.get('from_template_sync'):
            if {'compute_mode', 'value', 'python_code'} & set(vals_to_write.keys()):
                if 'is_override' not in vals_to_write:
                    vals_to_write['is_override'] = True

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

