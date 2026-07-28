# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_RULE_SYNC_FIELDS = [
    'sequence',
    'quantity',
    'active',
    'condition_select',
    'condition_range',
    'condition_python',
    'condition_range_min',
    'condition_range_max',
    'amount_select',
    'amount_fix',
    'amount_percentage',
    'amount_python_compute',
    'amount_percentage_base',
    'note',
]

_TRIGGER_FIELDS = {
    'sequence',
    'name',
    'code_id',
    'code',
    'compute_mode',
    'value',
    'python_code',
    'impact',
    'show_in_offer',
}


class SalaryConfigStructureLine(models.Model):
    _inherit = 'salary.config.structure.line'

    hr_salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Payroll Salary Rule',
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_hr_salary_rules()
        return records

    def write(self, vals):
        if self.env.context.get('skip_salary_rule_sync'):
            return super().write(vals)
        res = super().write(vals)
        if _TRIGGER_FIELDS & set(vals.keys()):
            self._sync_hr_salary_rules()
        return res

    def _sync_hr_salary_rules(self):
        HrSalaryRule = self.env['hr.salary.rule']
        for line in self:
            if not line.code_id:
                continue
            sync_vals = line._prepare_hr_salary_rule_sync_vals()
            rule = line.hr_salary_rule_id
            if not rule or not rule.exists():
                rule = HrSalaryRule.search([
                    ('name', '=', line.name or ''),
                    ('category_id', '=', line.code_id.id),
                ], limit=1)
                if not rule and line.code:
                    rule = HrSalaryRule.search([('code', '=', line.code)], limit=1)
            if rule:
                rule.write(sync_vals)
            else:
                create_vals = dict(sync_vals)
                structure = line._get_target_hr_salary_rule_structure()
                if not structure:
                    _logger.warning(
                        "Skipping salary rule sync for line %s: no payroll structure found.",
                        line.display_name,
                    )
                    continue
                create_vals.update({
                    'name': line.name or (line.code_id.name or line.code or 'Line'),
                    'code': line._generate_salary_rule_code(),
                    'category_id': line.code_id.id,
                    'struct_id': structure.id,
                })
                rule = HrSalaryRule.create(create_vals)
            if rule != line.hr_salary_rule_id:
                line.with_context(skip_salary_rule_sync=True).write({'hr_salary_rule_id': rule.id})

    def _prepare_hr_salary_rule_sync_vals(self):
        HrSalaryRule = self.env['hr.salary.rule']
        defaults = HrSalaryRule.default_get(_RULE_SYNC_FIELDS)
        vals = dict(defaults or {})
        vals.update({
            'sequence': self.sequence or 0,
            'quantity': vals.get('quantity') or '1.0',
            'active': bool(self.show_in_offer),
            'condition_select': 'none',
            'condition_range': vals.get('condition_range') or 'contract.wage',
            'condition_range_min': 0.0,
            'condition_range_max': 0.0,
            'note': self._build_salary_rule_note(),
        })
        compute_mode = self.compute_mode or 'formula'
        if compute_mode == 'percent_yearly':
            code = self.code or ''
            pct = (self.value or 0.0) / 100.0
            python_code = f"result = contract.get_salary_breakdown_amount('{code}') or (contract.wage * {pct})" if code else f"result = contract.wage * {pct}"
            vals.update({
                'amount_select': 'code',
                'amount_fix': 0.0,
                'amount_percentage': 0.0,
                'amount_python_compute': python_code,
                'amount_percentage_base': False,
            })
        elif compute_mode == 'fixed_monthly':
            code = self.code or ''
            fix_val = self.value or 0.0
            python_code = f"result = contract.get_salary_breakdown_amount('{code}') or {fix_val}" if code else f"result = {fix_val}"
            vals.update({
                'amount_select': 'code',
                'amount_fix': 0.0,
                'amount_percentage': 0.0,
                'amount_python_compute': python_code,
                'amount_percentage_base': False,
            })
        else:
            code_expr = self._adapt_python_code_for_payroll_rule()
            vals.update({
                'amount_select': 'code',
                'amount_fix': 0.0,
                'amount_percentage': 0.0,
                'amount_python_compute': code_expr,
                'amount_percentage_base': False,
            })
        return vals

    def _build_salary_rule_note(self):
        if self.impact:
            return 'Synced from salary.config.structure.line (%s).' % (self.impact,)
        return 'Synced from salary.config.structure.line.'

    def _generate_salary_rule_code(self):
        base = (self.code or '').strip()
        if not base:
            base = re.sub(r'[^A-Z0-9]+', '_', (self.name or '').upper()).strip('_')
        if not base:
            base = 'LINE'
        HrSalaryRule = self.env['hr.salary.rule']
        code = base.upper()
        candidate = code
        index = 1
        while HrSalaryRule.search_count([('code', '=', candidate)]):
            candidate = '%s_%d' % (code, index)
            index += 1
        return candidate

    def _get_target_hr_salary_rule_structure(self):
        """Return the payroll structure used when creating synced salary rules."""
        structure = self.env.ref('hr_payroll.default_structure', raise_if_not_found=False)
        if not structure:
            structure = self.env['hr.payroll.structure'].search([], limit=1)
        return structure

    def _adapt_python_code_for_payroll_rule(self):
        """Inject helper utilities so salary rule code interoperates with payroll context."""
        code = (self.python_code or '').strip()
        code = (self.python_code or '').strip()
        if not code:
            return 'result = 0.0'

        # Unescape XML entities that may remain from data files
        code = code.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

        def _replace_amount(match):
            return "categories.get('%s', 0.0)" % match.group(2)

        # Replace helper lookups from salary_config context with payroll equivalents
        code = re.sub(r"\b(amount|get)\(\s*['\"]([A-Za-z0-9_]+)['\"]\s*\)", _replace_amount, code)
        code = re.sub(r"\bmonthly_budget\b", '(contract.wage or 0.0)', code)
        code = re.sub(r"\bfinal_yearly_costs\b", '(contract.wage or 0.0) * 12.0', code)

        code = code.strip()
        if not code:
            return 'result = 0.0'
        return code
