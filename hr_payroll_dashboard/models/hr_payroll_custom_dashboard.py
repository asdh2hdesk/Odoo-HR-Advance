# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)


class HrPayrollCustomDashboard(models.Model):
    _name = 'hr.payroll.custom.dashboard'
    _description = 'HR Payroll Custom Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        today = date.today()
        if date_from:
            month_start = date.fromisoformat(date_from)
        else:
            month_start = today.replace(day=1)
        if date_to:
            month_end = date.fromisoformat(date_to)
        else:
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
        today = month_end  # shift "today" context to end of selected range
        current_company = self.env.company
        _logger.warning(">>> Current company: %s (id=%s)", current_company.name, current_company.id)

        # TEMP DEBUG
        _logger.warning("=== get_dashboard_data CALLED ===")
        _logger.warning("month_start=%s month_end=%s", month_start, month_end)

        try:
            payslips = self.env['hr.payslip'].search([
                ('date_from', '>=', month_start),
                ('date_to', '<=', month_end),
                ('state', 'in', ['verify', 'done', 'paid']),
                ('company_id', 'in', self.env.companies.ids),
            ])

            # Fallback: if no payslips this month, use most recent done/paid
            if not payslips:
                payslips = self.env['hr.payslip'].search([
                    ('state', 'in', ['verify', 'done', 'paid']),
                    ('company_id', 'in', self.env.companies.ids),
                ], order='date_from desc', limit=200)
            _logger.warning("ALL payslips this month (any state): %d", len(payslips))
            states = {}
            for p in payslips:
                states[p.state] = states.get(p.state, 0) + 1
            _logger.warning("States: %s", states)

            done = payslips.filtered(lambda p: p.state in ('done', 'paid'))
            _logger.warning("done/paid payslips: %d", len(done))

            if done:
                sample = done[0]
                _logger.warning("Sample slip: emp=%s struct=%s",
                                sample.employee_id.name,
                                sample.struct_id.name if sample.struct_id else 'NO STRUCT')
                for line in sample.line_ids:
                    _logger.warning("  LINE code=%-20s cat=%-10s name=%-35s total=%.2f",
                                    line.code or '-',
                                    line.category_id.code if line.category_id else '-',
                                    (line.name or '-')[:35],
                                    line.total)
            else:
                # No done/paid — check broader date range
                broader = self.env['hr.payslip'].search([
                    ('state', 'in', ['verify', 'done', 'paid']),
                    ('company_id', 'in', self.env.companies.ids),
                ], limit=3)
                _logger.warning("No done/paid this month. Recent done/paid slips (any date):")
                for p in broader:
                    _logger.warning("  emp=%s date_from=%s date_to=%s state=%s",
                                    p.employee_id.name, p.date_from, p.date_to, p.state)

        except Exception as e:
            _logger.error("DEBUG block failed: %s", e)

        _logger.warning("=== END DEBUG ===")

        def safe(fn, *args):
            try:
                return fn(*args)
            except Exception as e:
                _logger.warning("Dashboard section failed [%s]: %s", fn.__name__, e)
                return {}

        return {
            'attendance_salary': safe(self._get_attendance_salary, month_start, month_end),
            'actual_payout': safe(self._get_actual_payout, month_start, month_end),
            'daily_attendance': safe(self._get_daily_attendance, today),
            'leaves_for_approval': safe(self._get_leaves_for_approval),
            'loan_summary': safe(self._get_loan_summary),
            'payslip_summary': safe(self._get_payslip_summary, month_start, month_end),
            'new_joinees': safe(self._get_new_joinees, month_start, month_end),
            'monthly_attendance_trend': safe(self._get_monthly_attendance_trend, today),
            'extra': safe(self._get_extra_data, today, month_start, month_end),
            'monthly_leave_analysis': self._get_monthly_leave_analysis(),
            'join_resign': self._get_join_resign(),
            'attrition': self._get_attrition(),
            'salary_report': safe(self._get_salary_report_kpis, month_start, month_end),
            'german_salary_report': safe(self._get_german_salary_report_kpis, month_start, month_end),
        }

    @api.model
    def _get_extra_data(self, today, month_start, month_end):
        # Use sudo() with explicit company filter to respect active company selection
        company_ids = self.env.companies.ids
        Employee = self.env['hr.employee'].sudo()
        Leave = self.env['hr.leave'].sudo()
        Contract = self.env['hr.contract'].sudo()

        # ── Department distribution ──────────────────────────────────────
        dept_data = {}
        for emp in Employee.search([('active', '=', True), ('company_id', 'in', company_ids)]):
            dept = emp.department_id.name or 'Unassigned'
            dept_data[dept] = dept_data.get(dept, 0) + 1
        dept_distribution = [{'name': k, 'count': v} for k, v in dept_data.items()]

        # ── Monthly leave analysis (last 6 months) ───────────────────────
        monthly_leave = []
        for i in range(5, -1, -1):
            m_start = month_start - relativedelta(months=i)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            count = Leave.search_count([
                ('state', 'not in', ['refuse', 'cancel']),
                ('date_from', '>=', m_start),
                ('date_from', '<=', m_end),
                ('employee_id.company_id', 'in', company_ids),
            ])
            monthly_leave.append({'month': m_start.strftime('%b'), 'total': count})

        # ── Join / Resign (last 12 months) ───────────────────────────────
        join_resign = []
        for i in range(11, -1, -1):
            m_start = month_start - relativedelta(months=i)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            joined = Contract.search_count([
                ('date_start', '>=', m_start),
                ('date_start', '<=', m_end),
                ('company_id', 'in', company_ids),
            ])
            resigned = Employee.search_count([
                ('active', '=', False),
                ('departure_date', '>=', m_start),
                ('departure_date', '<=', m_end),
                ('company_id', 'in', company_ids),
            ])
            join_resign.append({'month': m_start.strftime('%b'), 'joined': joined, 'resigned': resigned})

        # ── Attrition (last 12 months) ───────────────────────────────────
        attrition = []
        for i in range(11, -1, -1):
            m_start = month_start - relativedelta(months=i)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            resigned = Employee.search_count([
                ('active', '=', False),
                ('departure_date', '>=', m_start),
                ('departure_date', '<=', m_end),
                ('company_id', 'in', company_ids),
            ])
            attrition.append({'month': m_start.strftime('%b'), 'rate': resigned})

        # ── Leave counts ─────────────────────────────────────────────────
        leave_today = Leave.search_count([
            ('date_from', '<=', datetime.combine(today, datetime.max.time())),
            ('date_to', '>=', datetime.combine(today, datetime.min.time())),
            ('state', 'not in', ['refuse', 'cancel']),
            ('employee_id.company_id', 'in', company_ids),
        ])
        leave_month = Leave.search_count([
            ('date_from', '>=', month_start),
            ('state', 'not in', ['refuse', 'cancel']),
            ('employee_id.company_id', 'in', company_ids),
        ])

        return {
            'timesheets': 0,
            'contracts': Contract.search_count([('state', '=', 'open'), ('company_id', 'in', company_ids)]),
            'broad_factor': 0,
            'leave_today': leave_today,
            'leave_month': leave_month,
            'leave_allocations': self.env['hr.leave.allocation'].sudo().search_count([
                ('state', '=', 'validate'),
                ('employee_id.company_id', 'in', company_ids),
            ]),
            'job_applications': self.env['hr.applicant'].sudo().search_count([
                ('company_id', 'in', company_ids),
            ]) if 'hr.applicant' in self.env else 0,
            'dept_total': Employee.search_count([('active', '=', True), ('company_id', 'in', company_ids)]),
            'dept_count': len(set(
                emp.department_id.id
                for emp in Employee.search([('active', '=', True), ('company_id', 'in', company_ids)])
                if emp.department_id
            )),
            'dept_distribution': dept_distribution,
            'monthly_leave_analysis': monthly_leave,
            'my_leave_analysis': [],
            'join_resign': join_resign,
            'attrition': attrition,
            'birthdays': [],
            'events': [],
            'announcements': [],
        }

    def _get_monthly_leave_analysis(self):
        company_ids = tuple(self.env.companies.ids)
        self.env.cr.execute("""
            SELECT TO_CHAR(date_from, 'Mon') AS month,
                   COUNT(*) AS total
            FROM hr_leave
            WHERE state NOT IN ('refuse', 'cancel')
              AND date_from >= NOW() - INTERVAL '6 months'
              AND company_id IN %s
            GROUP BY TO_CHAR(date_from, 'Mon'), DATE_TRUNC('month', date_from)
            ORDER BY DATE_TRUNC('month', date_from)
        """, (company_ids,))
        return [{'month': r[0], 'total': r[1]} for r in self.env.cr.fetchall()]

    @api.model
    def _get_join_resign(self):
        company_ids = tuple(self.env.companies.ids)
        self.env.cr.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', d), 'Mon') AS month,
                   SUM(CASE WHEN type = 'join' THEN 1 ELSE 0 END) AS joined,
                   SUM(CASE WHEN type = 'resign' THEN 1 ELSE 0 END) AS resigned
            FROM (
                SELECT c.date_start AS d, 'join' AS type
                FROM hr_contract c
                WHERE c.date_start IS NOT NULL
                  AND c.company_id IN %s
                UNION ALL
                SELECT e.departure_date AS d, 'resign' AS type
                FROM hr_employee e
                WHERE e.departure_date IS NOT NULL
                  AND e.company_id IN %s
            ) sub
            WHERE d >= NOW() - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', d)
            ORDER BY DATE_TRUNC('month', d)
        """, (company_ids, company_ids))
        return [{'month': r[0], 'joined': r[1], 'resigned': r[2]} for r in self.env.cr.fetchall()]

    def _get_attrition(self):
        company_ids = tuple(self.env.companies.ids)
        self.env.cr.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', departure_date), 'Mon') AS month,
                   COUNT(*) AS rate
            FROM hr_employee
            WHERE departure_date IS NOT NULL
              AND departure_date >= NOW() - INTERVAL '12 months'
              AND company_id IN %s
            GROUP BY DATE_TRUNC('month', departure_date)
            ORDER BY DATE_TRUNC('month', departure_date)
        """, (company_ids,))
        return [{'month': r[0], 'rate': r[1]} for r in self.env.cr.fetchall()]

    @api.model
    def debug_salary_kpis(self):
        """Call this from Odoo shell to diagnose zero values."""
        from datetime import date
        from dateutil.relativedelta import relativedelta
        from datetime import timedelta

        today = date.today()
        month_start = today.replace(day=1)
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

        _logger.warning("=== SALARY KPI DEBUG ===")
        _logger.warning("Date range: %s to %s", month_start, month_end)

        # 1. How many payslips exist this month?
        all_payslips = self.env['hr.payslip'].search([
            ('date_from', '>=', month_start),
            ('date_to', '<=', month_end),
        ])
        _logger.warning("Total payslips (all states): %d", len(all_payslips))

        done_payslips = all_payslips.filtered(lambda p: p.state in ('done', 'paid'))
        _logger.warning("Payslips in done/paid state: %d", len(done_payslips))

        # 2. Show states of all payslips
        states = {}
        for p in all_payslips:
            states[p.state] = states.get(p.state, 0) + 1
        _logger.warning("Payslip states breakdown: %s", states)

        # 3. Show all unique line codes in these payslips
        all_codes = set()
        all_cat_codes = set()
        for slip in done_payslips[:20]:  # check first 20
            for line in slip.line_ids:
                if line.code:
                    all_codes.add(line.code.upper())
                if line.category_id and line.category_id.code:
                    all_cat_codes.add(line.category_id.code.upper())
        _logger.warning("Unique line CODES found: %s", sorted(all_codes))
        _logger.warning("Unique category CODES found: %s", sorted(all_cat_codes))

        # 4. Show salary structures used
        struct_names = set()
        for slip in done_payslips:
            if slip.struct_id:
                struct_names.add(slip.struct_id.name)
        _logger.warning("Salary structures used: %s", struct_names)

        # 5. Check final_yearly_costs on contracts
        contracts_with_ctc = 0
        contracts_without_ctc = 0
        for slip in done_payslips[:50]:
            if slip.contract_id:
                if slip.contract_id.final_yearly_costs:
                    contracts_with_ctc += 1
                else:
                    contracts_without_ctc += 1
        _logger.warning("Contracts WITH final_yearly_costs: %d", contracts_with_ctc)
        _logger.warning("Contracts WITHOUT final_yearly_costs: %d", contracts_without_ctc)

        # 6. Show sample lines from first payslip
        if done_payslips:
            sample = done_payslips[0]
            _logger.warning("--- Sample payslip: %s | struct: %s ---",
                            sample.employee_id.name,
                            sample.struct_id.name if sample.struct_id else 'None')
            for line in sample.line_ids:
                _logger.warning("  Line: code=%-25s cat=%-10s name=%-40s total=%s",
                                line.code or '-',
                                line.category_id.code if line.category_id else '-',
                                line.name or '-',
                                line.total)

        _logger.warning("=== END DEBUG ===")

    # -------------------------------------------------------------------------
    # Salary Report KPIs (CTC + Gross)
    # -------------------------------------------------------------------------
    @api.model
    def _get_salary_report_kpis(self, month_start, month_end):
        _logger.warning(">>> [SALARY_KPI] START month_start=%s month_end=%s", month_start, month_end)
        _logger.warning(">>> [SALARY_KPI] companies=%s", self.env.companies.ids)

        payslips = self.env['hr.payslip'].sudo().search([
            ('date_from', '>=', month_start),
            ('date_to', '<=', month_end),
            ('state', 'in', ['verify', 'done', 'paid']),
            ('company_id', 'in', self.env.companies.ids),
        ])
        _logger.warning(">>> [SALARY_KPI] payslips found: %d", len(payslips))

        # Log company IDs on each payslip vs env companies
        if payslips:
            slip_companies = set(payslips.mapped('company_id.id'))
            _logger.warning(">>> [SALARY_KPI] payslip company_ids: %s | env.companies.ids: %s",
                            slip_companies, self.env.companies.ids)

        GROSS_CODES = {
            'GROSS', 'GROSS_EARN', 'TOTAL_GROSS', 'GROSS_SALARY',
            'TOTAL_GROSS_EARN', 'TOTAL_GROSS_EARNING', 'TOTAL_EARN',
            'GROSS_BONUS', 'EARN',
        }
        GROSS_KEYWORDS = ('total gross earning', 'gross earning', 'gross salary', 'total gross')

        def get_gross_from_lines(lines):
            # Try code match first
            v = sum(l.total for l in lines if l.code and l.code.upper() in GROSS_CODES)
            if v:
                return v
            # Try name keyword match
            v = sum(
                l.total for l in lines
                if l.name and any(kw in l.name.lower() for kw in GROSS_KEYWORDS)
            )
            if v:
                return v
            # Fallback: sum BASIC+ALW category lines
            return sum(
                l.total for l in lines
                if l.category_id and l.category_id.code
                and l.category_id.code.upper() in ('ALW', 'BASIC', 'ALLOWANCE')
            )

        # ── DEBUG: sample first payslip lines ────────────────────────────
        if payslips:
            sample = payslips[0]
            _logger.warning(">>> [SALARY_KPI] sample slip: emp=%s struct=%s date_from=%s state=%s",
                            sample.employee_id.name,
                            sample.struct_id.name if sample.struct_id else 'NO_STRUCT',
                            sample.date_from, sample.state)
            _logger.warning(">>> [SALARY_KPI] line_ids count on sample: %d", len(sample.line_ids))
            for line in sample.line_ids:
                matched_code = line.code and line.code.upper() in GROSS_CODES
                matched_kw   = line.name and any(kw in line.name.lower() for kw in GROSS_KEYWORDS)
                _logger.warning(">>> [SALARY_KPI]   line code=%-20s cat=%-8s total=%-10.2f "
                                "GROSS_CODE_MATCH=%s KEYWORD_MATCH=%s name=%s",
                                line.code or '-',
                                line.category_id.code if line.category_id else '-',
                                line.total,
                                matched_code,
                                matched_kw,
                                line.name or '-')
            gross_sample = get_gross_from_lines(sample.line_ids)
            _logger.warning(">>> [SALARY_KPI] gross from sample slip = %.2f", gross_sample)

            # CTC debug
            c = sample.contract_id
            if c:
                _logger.warning(">>> [SALARY_KPI] contract: wage=%s final_yearly_costs=%s",
                                c.wage,
                                getattr(c, 'final_yearly_costs', 'FIELD_MISSING'))
            else:
                _logger.warning(">>> [SALARY_KPI] NO CONTRACT on sample slip")
        # ─────────────────────────────────────────────────────────────────

        total_gross = 0.0
        total_ctc = 0.0
        total_inhand = 0.0
        total_net = 0.0
        total_pf = 0.0

        for slip in payslips:
            for line in slip.line_ids:
                code = (line.code or '').upper()
                if code in GROSS_CODES:
                    total_gross += line.total
                if slip.contract_id:
                    total_ctc = total_ctc  # handled below
                if code == 'INHAND':
                    total_inhand += line.total
                elif code == 'NET':
                    total_net += line.total
                elif code == 'PF':
                    total_pf += abs(line.total)

        total_ctc = sum(
            (slip.contract_id.wage or 0)
            for slip in payslips
            if slip.contract_id
        )

        _logger.warning(">>> [SALARY_KPI] RESULT total_gross=%.2f total_ctc=%.2f", total_gross, total_ctc)
        return {
            'total_ctc': round(total_ctc, 2),
            'total_gross': round(total_gross, 2),
            'total_inhand': round(total_inhand, 2),
            'total_net': round(total_net, 2),
            'total_pf': round(total_pf, 2),
            'currency': self.env.company.currency_id.symbol or '₹',
        }

    @api.model
    def _get_german_salary_report_kpis(self, month_start, month_end):
        _logger.warning(">>> [GERMAN_KPI] START month_start=%s month_end=%s", month_start, month_end)

        payslips = self.env['hr.payslip'].sudo().search([
            ('date_from', '>=', month_start),
            ('date_to', '<=', month_end),
            ('state', 'in', ['verify', 'done', 'paid']),
            ('company_id', 'in', self.env.companies.ids),
        ])
        _logger.warning(">>> [GERMAN_KPI] total payslips (all structs): %d", len(payslips))

        all_struct_names = set(s.struct_id.name for s in payslips if s.struct_id)
        _logger.warning(">>> [GERMAN_KPI] ALL struct names in payslips: %s", all_struct_names)

        # Filter by salary structure name containing 'german'
        german_payslips = payslips.filtered(
            lambda s: s.struct_id and 'german' in (s.struct_id.name or '').lower()
        )
        _logger.warning(">>> [GERMAN_KPI] german_payslips (filtered by 'german'): %d", len(german_payslips))

        if not german_payslips:
            _logger.warning(">>> [GERMAN_KPI] WARNING: No payslips matched 'german' in struct name!")
            _logger.warning(">>> [GERMAN_KPI] WARNING: Struct names found: %s", all_struct_names)

        GROSS_CODES = {
            'GROSS', 'GROSS_EARN', 'TOTAL_GROSS', 'GROSS_SALARY',
            'TOTAL_GROSS_EARN', 'TOTAL_GROSS_EARNING', 'TOTAL_EARN',
            'GROSS_BONUS', 'EARN',
        }
        GROSS_KEYWORDS = ('total gross earning', 'gross earning', 'gross salary', 'total gross')

        def get_gross_from_lines(lines):
            v = sum(l.total for l in lines if l.code and l.code.upper() in GROSS_CODES)
            if v:
                return v
            v = sum(
                l.total for l in lines
                if l.name and any(kw in l.name.lower() for kw in GROSS_KEYWORDS)
            )
            return v

        if german_payslips:
            sample = german_payslips[0]
            _logger.warning(">>> [GERMAN_KPI] sample slip: emp=%s struct=%s",
                            sample.employee_id.name,
                            sample.struct_id.name if sample.struct_id else 'NO_STRUCT')
            for line in sample.line_ids:
                matched_code = bool(line.code and line.code.upper() in GROSS_CODES)
                matched_kw = bool(line.name and any(kw in line.name.lower() for kw in GROSS_KEYWORDS))
                _logger.warning(">>> [GERMAN_KPI]   code=%-20s cat=%-8s total=%-10.2f CODE_MATCH=%s KW_MATCH=%s name=%s",
                                line.code or '-',
                                line.category_id.code if line.category_id else '-',
                                line.total, matched_code, matched_kw, line.name or '-')
            gross_sample = get_gross_from_lines(sample.line_ids)
            _logger.warning(">>> [GERMAN_KPI] gross from sample slip = %.2f", gross_sample)
            c = sample.contract_id
            if c:
                _logger.warning(">>> [GERMAN_KPI] contract wage=%s final_yearly_costs=%s",
                                c.wage, getattr(c, 'final_yearly_costs', 'FIELD_MISSING'))
            else:
                _logger.warning(">>> [GERMAN_KPI] NO CONTRACT on sample slip")

        german_gross = sum(
            get_gross_from_lines(slip.line_ids) for slip in german_payslips
        )
        german_ctc = sum(
            (slip.contract_id.wage or 0)
            for slip in german_payslips
            if slip.contract_id
        )
        _logger.warning(">>> [GERMAN_KPI] RESULT german_gross=%.2f german_ctc=%.2f", german_gross, german_ctc)
        return {
            'total_ctc': round(german_ctc, 2),
            'total_gross': round(german_gross, 2),
            'currency': self.env.company.currency_id.symbol or '₹',
        }
    # -------------------------------------------------------------------------
    # 1. Attendance-wise salary
    # -------------------------------------------------------------------------
    @api.model
    def _get_attendance_salary(self, month_start, month_end):
        """
        Returns per-employee attendance hours vs contracted hours and
        the prorated salary for the current month.
        """
        employees = self.env['hr.employee'].sudo().search([
            ('company_id', 'in', self.env.companies.ids),
            ('active', '=', True),
        ])

        records = []
        total_attendance_salary = 0.0
        total_gross_salary = 0.0

        for emp in employees:
            # Contracted wage
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'open'),
            ], limit=1)
            if not contract:
                continue

            # Total working days in month (simplified: Mon-Fri)
            total_days = sum(
                1 for d in range((month_end - month_start).days + 1)
                if (month_start + timedelta(days=d)).weekday() < 5
            )

            # Attendance hours this month
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', emp.id),
                ('check_in', '>=', datetime.combine(month_start, datetime.min.time())),
                ('check_in', '<=', datetime.combine(month_end, datetime.max.time())),
            ])
            attended_hours = sum(a.worked_hours for a in attendances)
            attended_days  = round(attended_hours / 8, 1) if attended_hours else 0

            daily_rate = contract.wage / total_days if total_days else 0
            att_salary = round(min(attended_days, total_days) * daily_rate, 2)

            total_attendance_salary += att_salary
            total_gross_salary      += contract.wage

            records.append({
                'employee': emp.name,
                'department': emp.department_id.name or '-',
                'attended_days': attended_days,
                'total_days': total_days,
                'gross_salary': contract.wage,
                'attendance_salary': att_salary,
                'currency': contract.currency_id.symbol or '₹',
            })

        return {
            'records': records[:20],          # cap at 20 rows for display
            'total_attendance_salary': round(total_attendance_salary, 2),
            'total_gross_salary': round(total_gross_salary, 2),
            'currency': self.env.company.currency_id.symbol or '₹',
        }

    # -------------------------------------------------------------------------
    # 2. Actual payout salary
    # -------------------------------------------------------------------------
    @api.model
    def _get_actual_payout(self, month_start, month_end):
        """
        Reads confirmed / paid payslips for the current month and sums
        net salaries.
        """
        payslips = self.env['hr.payslip'].search([
            ('date_from', '>=', month_start),
            ('date_to', '<=', month_end),
            ('state', 'in', ['verify', 'done', 'paid']),
            ('company_id', 'in', self.env.companies.ids),
        ])
        if not payslips:
            payslips = self.env['hr.payslip'].search([
                ('state', 'in', ['verify', 'done', 'paid']),
                ('company_id', 'in', self.env.companies.ids),
            ], order='date_from desc', limit=500)

        net_total  = 0.0
        gross_total = 0.0
        deductions_total = 0.0

        for slip in payslips:
            for line in slip.line_ids:
                if line.category_id.code == 'NET':
                    net_total += line.total
                elif line.category_id.code == 'GROSS':
                    gross_total += line.total
                elif line.category_id.code == 'DED':
                    deductions_total += abs(line.total)

        currency = self.env.company.currency_id.symbol or '₹'
        return {
            'total_payslips': len(payslips),
            'gross_total': round(gross_total, 2),
            'deductions_total': round(deductions_total, 2),
            'net_total': round(net_total, 2),
            'currency': currency,
            'paid_count': len(payslips.filtered(lambda p: p.state == 'paid')),
            'pending_count': len(payslips.filtered(lambda p: p.state == 'done')),
        }

    # -------------------------------------------------------------------------
    # 3. Daily attendance
    # -------------------------------------------------------------------------
    @api.model
    def _get_daily_attendance(self, today):
        """
        Returns today's check-in / check-out summary.
        """
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day   = datetime.combine(today, datetime.max.time())

        total_employees = self.env['hr.employee'].search_count([
            ('company_id', 'in', self.env.companies.ids),
            ('active', '=', True),
        ])

        # Checked-in today — filter by employees of the active companies
        company_ids = self.env.companies.ids
        company_employee_ids = self.env['hr.employee'].sudo().search([
            ('company_id', 'in', company_ids),
            ('active', '=', True),
        ]).ids
        checked_in_today = self.env['hr.attendance'].search([
            ('check_in', '>=', start_of_day),
            ('check_in', '<=', end_of_day),
            ('employee_id', 'in', company_employee_ids),
        ])
        present  = len(checked_in_today.mapped('employee_id'))
        # Still checked in (no checkout yet)
        still_in = len(checked_in_today.filtered(lambda a: not a.check_out)
                       .mapped('employee_id'))

        # On approved leave today — filter by employee company (hr.leave has company_id)
        on_leave = 0  # unused
        leaves_today = self.env['hr.leave'].search_count([
            ('date_from', '<=', end_of_day),
            ('date_to', '>=', start_of_day),
            ('state', '=', 'validate'),
            ('employee_id', 'in', company_employee_ids),
        ])

        absent = max(total_employees - present - leaves_today, 0)

        # Build list of currently checked-in employees
        live_records = []
        for att in checked_in_today.filtered(lambda a: not a.check_out)[:15]:
            live_records.append({
                'employee': att.employee_id.name,
                'department': att.employee_id.department_id.name or '-',
                'check_in': att.check_in.strftime('%H:%M') if att.check_in else '-',
                'worked_hours': round(att.worked_hours, 2),
            })
        checked_out = len(checked_in_today.filtered(lambda a: a.check_out).mapped('employee_id'))
        missed_out = still_in  # present but never checked out = missed checkout
        return {
            'date': today.strftime('%d %B %Y'),
            'total': total_employees,
            'present': present,
            'absent': absent,
            'on_leave': leaves_today,
            'still_checked_in': still_in,
            'checked_out': checked_out,
            'missed_out': missed_out,
            'live_records': live_records,
        }

    # -------------------------------------------------------------------------
    # 4. Leaves for approval
    # -------------------------------------------------------------------------
    @api.model
    def _get_leaves_for_approval(self):
        """
        Pending leave requests that need manager / HR approval.
        """
        pending_leaves = self.env['hr.leave'].sudo().search([
            ('state', 'in', ['confirm', 'validate1']),
            ('company_id', 'in', self.env.companies.ids),
        ], order='date_from asc')

        records = []
        by_type = {}

        for leave in pending_leaves[:25]:
            leave_type = leave.holiday_status_id.name or 'Unknown'
            by_type[leave_type] = by_type.get(leave_type, 0) + 1
            records.append({
                'id': leave.id,
                'employee': leave.employee_id.name,
                'department': leave.employee_id.department_id.name or '-',
                'leave_type': leave_type,
                'date_from': leave.date_from.strftime('%d %b %Y') if leave.date_from else '-',
                'date_to': leave.date_to.strftime('%d %b %Y') if leave.date_to else '-',
                'days': leave.number_of_days,
                'state': dict(leave._fields['state'].selection).get(leave.state, leave.state),
            })

        return {
            'total_pending': len(pending_leaves),
            'records': records,
            'by_type': [{'type': k, 'count': v} for k, v in by_type.items()],
        }

    @api.model
    def _get_loan_summary(self):
        if not self.env['ir.model'].sudo().search([('model', '=', 'hr.salary.attachment')], limit=1):
            return {
                'available': False,
                'total_to_recover': 0,
                'total_recovered': 0,
                'total_given': 0,
                'active_loans': 0,
                'records': [],
                'currency': self.env.company.currency_id.symbol or '₹',
            }

        company_ids = self.env.companies.ids
        # hr.salary.attachment uses employee_ids (many2many), filter post-fetch
        all_attachments = self.env['hr.salary.attachment'].sudo().search([
            ('state', 'in', ['open', 'running']),
        ])
        # Keep only attachments whose employees belong to active companies
        attachments = all_attachments.filtered(
            lambda a: any(emp.company_id.id in company_ids for emp in a.employee_ids)
        ) if all_attachments else all_attachments
        _logger.warning(">>> [LOAN] attachments found: %d", len(attachments))
        if attachments:
            sample = attachments[0]
            _logger.warning(">>> [LOAN] fields: %s", [f for f in sample._fields.keys()])

        total_to_recover = 0.0
        total_recovered = 0.0
        total_given = 0.0
        records = []

        for att in attachments[:20]:
            total_amt = att.total_amount or 0
            paid_amt = att.paid_amount or 0
            remaining = att.remaining_amount or 0
            total_given += total_amt
            total_to_recover += remaining
            total_recovered += paid_amt

            emp_names = ', '.join(att.employee_ids.mapped('name')) if att.employee_ids else '-'
            records.append({
                'description': att.description or '-',
                'employees': emp_names,
                'monthly_amount': att.monthly_amount or 0,
                'total_amount': total_amt,
                'remaining_amount': round(remaining, 2),
                'recovered': round(paid_amt, 2),
            })

        currency = self.env.company.currency_id.symbol or '₹'
        return {
            'available': True,
            'total_to_recover': round(total_to_recover, 2),
            'total_recovered': round(total_recovered, 2),
            'total_given': round(total_given, 2),
            'active_loans': len(attachments),
            'records': records,
            'currency': currency,
        }

    @api.model
    def _get_payslip_summary(self, month_start, month_end):
        """
        Payslip counts by state for the current month.
        """
        all_slips = self.env['hr.payslip'].search([
            ('date_from', '>=', month_start),
            ('date_to', '<=', month_end),
            ('company_id', 'in', self.env.companies.ids),
        ])
        if not all_slips:
            all_slips = self.env['hr.payslip'].search([
                ('company_id', 'in', self.env.companies.ids),
            ], order='date_from desc', limit=500)

        state_labels = {
            'draft': 'Draft',
            'verify': 'Waiting',
            'done': 'Done',
            'paid': 'Paid',
            'cancel': 'Cancelled',
        }

        by_state = {}
        for slip in all_slips:
            label = state_labels.get(slip.state, slip.state)
            by_state[label] = by_state.get(label, 0) + 1

        recent = []
        for slip in all_slips.sorted('date_to', reverse=True)[:10]:
            net = sum(
                line.total for line in slip.line_ids
                if line.category_id.code == 'NET'
            )
            recent.append({
                'name': slip.name,
                'employee': slip.employee_id.name,
                'department': slip.department_id.name or '-',
                'date_from': slip.date_from.strftime('%d %b') if slip.date_from else '-',
                'date_to': slip.date_to.strftime('%d %b %Y') if slip.date_to else '-',
                'net': round(net, 2),
                'state': state_labels.get(slip.state, slip.state),
            })

        return {
            'total': len(all_slips),
            'by_state': [{'state': k, 'count': v} for k, v in by_state.items()],
            'recent': recent,
            'currency': self.env.company.currency_id.symbol or '₹',
            'month': month_start.strftime('%B %Y'),
        }

    # -------------------------------------------------------------------------
    # 7. New joinees
    # -------------------------------------------------------------------------
    @api.model
    def _get_new_joinees(self, month_start, month_end):
        """
        Employees whose contract start date / joining date falls in the
        current month.
        """
        # Try contract date first
        new_contracts = self.env['hr.contract'].search([
            ('date_start', '>=', month_start),
            ('date_start', '<=', month_end),
            ('company_id', 'in', self.env.companies.ids),
        ])

        # Also check employee create date for companies not using contracts
        new_employees = self.env['hr.employee'].search([
            ('create_date', '>=', datetime.combine(month_start, datetime.min.time())),
            ('create_date', '<=', datetime.combine(month_end, datetime.max.time())),
            ('company_id', 'in', self.env.companies.ids),
        ])

        seen_ids = set()
        records = []

        for contract in new_contracts:
            emp = contract.employee_id
            if emp.id in seen_ids:
                continue
            seen_ids.add(emp.id)
            records.append({
                'employee': emp.name,
                'department': emp.department_id.name or '-',
                'job': emp.job_id.name or '-',
                'joining_date': contract.date_start.strftime('%d %b %Y') if contract.date_start else '-',
                'wage': contract.wage,
                'currency': contract.currency_id.symbol or '₹',
            })

        for emp in new_employees:
            if emp.id in seen_ids:
                continue
            seen_ids.add(emp.id)
            records.append({
                'employee': emp.name,
                'department': emp.department_id.name or '-',
                'job': emp.job_id.name or '-',
                'joining_date': emp.create_date.strftime('%d %b %Y') if emp.create_date else '-',
                'wage': 0,
                'currency': self.env.company.currency_id.symbol or '₹',
            })

        return {
            'count': len(records),
            'records': records,
            'month': month_start.strftime('%B %Y'),
        }

    # -------------------------------------------------------------------------
    # 8. Monthly attendance trend (last 7 days)
    # -------------------------------------------------------------------------
    @api.model
    def _get_monthly_attendance_trend(self, today):
        """
        Returns daily present/absent counts for the last 7 working days.
        """
        company_ids = self.env.companies.ids
        company_employee_ids = self.env['hr.employee'].sudo().search([
            ('company_id', 'in', company_ids),
            ('active', '=', True),
        ]).ids
        total_employees = len(company_employee_ids)
        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            if day.weekday() >= 5:  # skip weekends
                continue
            start = datetime.combine(day, datetime.min.time())
            end   = datetime.combine(day, datetime.max.time())
            present = len(
                self.env['hr.attendance'].search([
                    ('check_in', '>=', start),
                    ('check_in', '<=', end),
                    ('employee_id', 'in', company_employee_ids),
                ]).mapped('employee_id')
            )
            trend.append({
                'day': day.strftime('%a %d'),
                'present': present,
                'absent': max(total_employees - present, 0),
            })
        return trend