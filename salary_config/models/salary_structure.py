# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class SalaryConfigStructure(models.Model):
    _name = 'salary.config.structure'
    _description = 'Salary Structure Template'
    _order = 'name'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('salary.config.structure.line', 'structure_id', string='Lines')
    examples_html = fields.Html(string='Examples Help', sanitize=False, compute='_compute_examples_html', help='Examples of compute modes and formulas.')

    company = fields.Char(related='company_id.name', readonly=True)
    
    @api.depends()
    def _compute_examples_html(self):
        example = _("")
        html = """
        <h3>Salary Component Examples</h3>
        <p>This section illustrates how to configure lines using <b>Compute Mode</b> values: <code>Percent of Employer Budget (yearly)</code>, <code>Fixed Monthly Amount</code>, and <code>Python Formula</code>.</p>
        <ul>
          <li><b>Percent of Employer Budget (yearly)</b>: Set <i>Compute Mode</i> to percentage and enter <i>Value</i>. Example: Basic = 50% of monthly budget (CTC / 12). Set <code>compute_mode = percent_yearly</code> and <code>value = 50</code>.</li>
          <li><b>Fixed Monthly Amount</b>: Set <code>compute_mode = fixed_monthly</code> and provide the monthly amount in <i>Value</i>. Example: Transport Allowance of 1600 monthly.</li>
          <li><b>Python Formula</b>: Set <code>compute_mode = formula</code> and write Python assigning a numeric result to the variable <code>result</code>. Available variables: <code>final_yearly_costs</code> (CTC), <code>monthly_budget</code> (CTC/12), and previously computed line codes accessible via helper dictionary building coming soon; for now reference only budget.</li>
        </ul>
        <p>Demo ideas inspired by the provided demo XML:</p>
        <pre>
        # Basic = 50% of monthly budget (use percent_yearly, value 50)
        # HRA = 50% of BASIC (formula)
        result = monthly_budget * 0.50 * 0.50  # (50% of 50%) example

        # Uniform = 5% of BASIC (formula)
        result = monthly_budget * 0.50 * 0.05

        # KRA = 3% of CTC (percent_yearly, value 3)

        # Adhoc Pay = monthly_budget - (Basic + HRA + Uniform + LTA + PF + KRA)
        # (Would require summing previously computed amounts by code in extended logic.)
        </pre>
        <p><b>In Hand Salary (INHAND)</b> line is auto-created. Adjust its formula as needed.</p>
        """
        for rec in self:
            rec.examples_html = html
            
    german_tmt_html = fields.Html(string='Examples Help', sanitize=False, compute='_compute_german_TMT_html', help='Examples of compute modes and formulas.')

    @api.depends()
    def _compute_german_TMT_html(self):
        example = _("")
        html = """
        <h3>Salary Component Examples</h3>
        <p>This section illustrates how to configure lines using <b>Compute Mode</b> values: <code>Percent of Employer Budget (yearly)</code>, <code>Fixed Monthly Amount</code>, and <code>Python Formula</code>.</p>
        <ul>
          <li><b>Percent of Employer Budget (yearly)</b>: Set <i>Compute Mode</i> to percentage and enter <i>Value</i>. Example: Basic = 60% of monthly budget (CTC / 12). Set <code>compute_mode = percent_yearly</code> and <code>value = 60</code>.</li>
          <li><b>Fixed Monthly Amount</b>: Set <code>compute_mode = fixed_monthly</code> and provide the monthly amount in <i>Value</i>. Example: Transport Allowance of 1600 monthly.</li>
          <li><b>Python Formula</b>: Set <code>compute_mode = formula</code> and write Python assigning a numeric result to the variable <code>result</code>. Available variables: <code>final_yearly_costs</code> (CTC), <code>monthly_budget</code> (CTC/12), and previously computed line codes accessible via helper dictionary building coming soon; for now reference only budget.</li>
        </ul>
        <p>Demo ideas inspired by the provided demo XML:</p>
        <pre>
        # Basic = 60% of monthly budget (use percent_yearly, value 60)
        # HRA = 15% of monthly budget (formula)
        result = monthly_budget * 0.15

        # Conveyance allowances = 4% of monthly budget (formula)
        result = monthly_budget * 0.04

        # Medical allowances = 2.719% of monthly budget (formula)
        result = monthly_budget * 0.02719

        # Other Allowances = monthly_budget - (Basic + HRA + Conveyance + Medical)
        # (Would require summing previously computed amounts by code in extended logic.)
        </pre>
        <p><b>In Hand Salary (INHAND)</b> line is auto-created. Adjust its formula as needed.</p>
        """
        for rec in self:
            rec.german_tmt_html = html 

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Auto create INHAND line if not already present
            if not rec.line_ids.filtered(lambda l: l.code == 'INHAND'):
                rec.write({'line_ids': [(0, 0, {
                    'name': 'In Hand Salary',
                    'code': 'INHAND',
                    'impact': 'benefit',
                    'compute_mode': 'formula',
                    'python_code': 'result = 0.0  # Set formula to compute the structure',
                    'show_in_offer': True,
                    'sequence': 140,
                })]})
        return records

class SalaryConfigStructureLine(models.Model):
    _name = 'salary.config.structure.line'
    _description = 'Salary Structure Template Line'
    _order = 'sequence, id'

    structure_id = fields.Many2one('salary.config.structure', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    code_id = fields.Many2one(
        'hr.salary.rule.category',
        string='Salary Rule Category',
        help='Select the payroll salary rule category used by this line.',
    )
    code = fields.Char(help='Technical code for the component')  # kept for backward compatibility & formula reference
    # computation type: percentage of yearly budget or fixed monthly amount
    compute_mode = fields.Selection([
        ('percent_yearly', 'Percent of Employer Budget (yearly)'),
        ('fixed_monthly', 'Fixed Monthly Amount'),
        ('formula', 'Python Formula')
    ], default='percent_yearly', required=True)
    value = fields.Float(string='Value', help='Percent (e.g., 10 for 10%) or fixed amount depending on mode')
    python_code = fields.Text(help='Python expression evaluated with variables: final_yearly_costs (float), monthly_budget (float). Must return a float monthly amount.',
                              default='result = monthly_budget * 0.0')
    impact = fields.Selection([
        ('cost', 'Employer Cost'),
        ('benefit', 'Benefit'),
        ('deduction', 'Deduction'),
    ], default='cost', required=True)
    show_in_offer = fields.Boolean(default=True)

    @api.onchange('code_id')
    def _onchange_code_id(self):
        for rec in self:
            rec.code = rec.code_id.code if rec.code_id else False

    @api.onchange('code')
    def _onchange_code(self):
        for rec in self:
            if rec.code and not rec.code_id:
                category = self.env['hr.salary.rule.category'].search([('code', '=', rec.code)], limit=1)
                if category:
                    rec.code_id = category

    @api.model_create_multi
    def create(self, vals_list):
        Category = self.env['hr.salary.rule.category']
        prepared_vals = []
        for vals in vals_list:
            vals = dict(vals)
            code = (vals.get('code') or '').strip()
            code_id = vals.get('code_id')
            category = False
            if code_id:
                category = Category.browse(code_id)
            elif code:
                category = Category.search([('code', '=', code)], limit=1)
            if category:
                vals['code_id'] = category.id
                if not code:
                    vals['code'] = category.code
            prepared_vals.append(vals)
        return super().create(prepared_vals)

    def write(self, vals):
        Category = self.env['hr.salary.rule.category']
        vals_to_write = dict(vals)
        if 'code_id' in vals_to_write and 'code' not in vals_to_write:
            code_id = vals_to_write['code_id']
            if code_id:
                category = Category.browse(code_id)
                vals_to_write['code'] = category.code if category else False
            else:
                vals_to_write['code'] = False
        res = super().write(vals_to_write)
        if 'code' in vals_to_write and not vals_to_write.get('code_id'):
            for rec in self:
                if rec.code and not rec.code_id:
                    category = Category.search([('code', '=', rec.code)], limit=1)
                    if category:
                        rec.code_id = category
        return res

    @api.model
    def _compute_monthly_from_yearly(self, yearly):
        # Odoo uses a 12 months monthly equivalent for display
        return yearly / 12.0 if yearly else 0.0

    def compute_monthly_amount(self, final_yearly_costs):
        self.ensure_one()
        monthly_budget = self._compute_monthly_from_yearly(final_yearly_costs)
        if self.compute_mode == 'percent_yearly':
            return monthly_budget * (self.value / 100.0)
        elif self.compute_mode == 'fixed_monthly':
            return self.value
        elif self.compute_mode == 'formula':
            # safe evaluation context
            localdict = {
                'final_yearly_costs': final_yearly_costs or 0.0,
                'monthly_budget': monthly_budget,
                'result': 0.0,
            }
            try:
                exec(self.python_code or '', {}, localdict)
                return float(localdict.get('result') or 0.0)
            except Exception:
                return 0.0
        return 0.0
