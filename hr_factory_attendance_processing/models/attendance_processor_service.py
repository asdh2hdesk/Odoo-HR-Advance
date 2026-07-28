# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AttendanceProcessorService(models.AbstractModel):
    _name = 'attendance.processor.service'
    _description = 'Attendance Processor Engine Service'

    def process_attendance_range(self, date_from, date_to, employee_ids=None, company_id=None):
        """
        Main entry point for processing attendance range into attendance.daily.summary records.
        """
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        if not employee_ids:
            domain = [('active', '=', True)]
            if company_id:
                domain.append(('company_id', '=', company_id if isinstance(company_id, int) else company_id.id))
            elif self.env.companies:
                domain.append(('company_id', 'in', self.env.companies.ids))
            employees = self.env['hr.employee'].search(domain)
        else:
            employees = self.env['hr.employee'].browse(employee_ids)

        summaries = self.env['attendance.daily.summary']
        current_date = date_from
        while current_date <= date_to:
            for employee in employees:
                summary = self._process_single_employee_date(employee, current_date)
                if summary:
                    summaries |= summary
            current_date += timedelta(days=1)
        return summaries

    def _process_single_employee_date(self, employee, date_val):
        """
        Processes a single employee for a specific calendar date.
        """
        if not employee or not date_val:
            return False

        # Find contract
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['open', 'close']),
            ('date_start', '<=', date_val),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', date_val),
        ], limit=1, order='date_start desc')

        calendar = contract.resource_calendar_id or employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar:
            return False

        tz_name = calendar.tz or employee.tz or 'UTC'
        tz = pytz.timezone(tz_name)

        # Expected daily hours
        expected_hours = calendar.hours_per_day or 8.0

        # Construct date bounds in UTC
        start_local = tz.localize(datetime.combine(date_val, time.min))
        stop_local = tz.localize(datetime.combine(date_val, time.max))
        start_utc = start_local.astimezone(pytz.UTC)
        stop_utc = stop_local.astimezone(pytz.UTC)

        # Fetch attendances for employee on date_val
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', stop_utc),
            ('check_out', '!=', False),
        ], order='check_in asc')

        # SUM(intervals)
        worked_hours = 0.0
        first_in = False
        last_out = False

        if attendances:
            first_in = min(attendances.mapped('check_in'))
            last_out = max(attendances.mapped('check_out'))
            for att in attendances:
                worked_hours += att.worked_hours

        # Determine Day Type
        day_type = self._determine_day_type(employee, calendar, date_val, start_utc, stop_utc)

        # Hour Splitting Rules
        regular_hours = 0.0
        ot_hours = 0.0
        shortage_hours = 0.0

        if day_type in ['weekoff', 'public_holiday']:
            # 100% OT for worked weekly off / public holiday
            regular_hours = 0.0
            ot_hours = worked_hours
            shortage_hours = 0.0
        elif day_type == 'leave':
            regular_hours = 0.0
            ot_hours = 0.0
            shortage_hours = 0.0
        elif day_type == 'half_day':
            expected_hours = expected_hours / 2.0
            if worked_hours > 0:
                regular_hours = min(worked_hours, expected_hours)
                ot_hours = max(0.0, worked_hours - expected_hours)
                shortage_hours = max(0.0, expected_hours - worked_hours)
            else:
                shortage_hours = expected_hours
        else: # working_day / absent
            if worked_hours == 0.0:
                day_type = 'absent'
                regular_hours = 0.0
                ot_hours = 0.0
                shortage_hours = expected_hours
            else:
                day_type = 'working_day'
                regular_hours = min(worked_hours, expected_hours)
                ot_hours = max(0.0, worked_hours - expected_hours)
                shortage_hours = max(0.0, expected_hours - worked_hours)

        # Apply grace time threshold if shortage is minor
        grace_minutes = employee.company_id.factory_grace_time_minutes or 15
        if shortage_hours > 0 and (shortage_hours * 60.0) <= grace_minutes:
            shortage_hours = 0.0

        # Search existing summary
        summary = self.env['attendance.daily.summary'].search([
            ('employee_id', '=', employee.id),
            ('date', '=', date_val),
        ], limit=1)

        vals = {
            'employee_id': employee.id,
            'contract_id': contract.id if contract else False,
            'date': date_val,
            'first_in': first_in,
            'last_out': last_out,
            'worked_hours': round(worked_hours, 2),
            'expected_hours': round(expected_hours, 2),
            'regular_hours': round(regular_hours, 2),
            'ot_hours': round(ot_hours, 2),
            'shortage_hours': round(shortage_hours, 2),
            'day_type': day_type,
            'state': summary.state if (summary and summary.state == 'locked') else 'calculated',
            'attendance_ids': [(6, 0, attendances.ids)],
        }

        if summary:
            if summary.state != 'locked':
                summary.write(vals)
        else:
            summary = self.env['attendance.daily.summary'].create(vals)

        return summary

    def _determine_day_type(self, employee, calendar, date_val, start_utc, stop_utc):
        """
        Determines whether date is a Public Holiday, Approved Leave, Weekly Off, or Normal Working Day.
        """
        # 1. Public Holiday (calendar global leaves)
        holiday_leaves = calendar.global_leave_ids.filtered(
            lambda l: l.date_from.date() <= date_val <= l.date_to.date()
        )
        if holiday_leaves:
            return 'public_holiday'

        # 2. Approved Leave (hr.leave)
        approved_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', stop_utc),
            ('date_to', '>=', start_utc),
        ])
        if approved_leaves:
            if any(l.number_of_days < 1.0 for l in approved_leaves):
                return 'half_day'
            return 'leave'

        # 3. Weekly Off (check calendar attendance lines weekday)
        # Weekday: 0 = Monday, ..., 6 = Sunday
        weekday_str = str(date_val.weekday())
        calendar_weekdays = calendar.attendance_ids.mapped('dayofweek')
        if weekday_str not in calendar_weekdays:
            return 'weekoff'

        return 'working_day'

    def _generate_work_entries_for_summary(self, summary):
        """
        Generates hr.work.entry records for a locked/approved summary record.
        """
        if not summary or not summary.employee_id:
            return False

        contract = summary.contract_id or self.env['hr.contract'].search([
            ('employee_id', '=', summary.employee_id.id),
            ('state', 'in', ['open', 'close']),
        ], limit=1)

        if not contract:
            return False

        # Work Entry Types
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
        if not attendance_type:
            attendance_type = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)

        overtime_type = self.env.ref('hr_payroll_workdays_extended.hr_work_entry_type_weekoff', raise_if_not_found=False)
        if not overtime_type:
            overtime_type = self.env['hr.work.entry.type'].search([('code', 'in', ['OVERTIME', 'OT'])], limit=1)
        if not overtime_type:
            overtime_type = attendance_type

        unpaid_type = self.env.ref('hr_work_entry_contract.work_entry_type_unpaid', raise_if_not_found=False)
        if not unpaid_type:
            unpaid_type = self.env['hr.work.entry.type'].search([('code', '=', 'UNPAID')], limit=1)

        holiday_type = self.env.ref('hr_work_entry_contract.work_entry_type_legal_leave', raise_if_not_found=False)
        if not holiday_type:
            holiday_type = self.env['hr.work.entry.type'].search([('code', '=', 'LEAVE114')], limit=1)

        # Unlink previous work entries linked to this summary
        if summary.work_entry_ids:
            summary.work_entry_ids.unlink()

        tz_name = summary.employee_id.tz or contract.resource_calendar_id.tz or 'UTC'
        tz = pytz.timezone(tz_name)

        # Base datetime reference
        if summary.first_in:
            base_start = summary.first_in
        else:
            local_start = tz.localize(datetime.combine(summary.date, time(hour=8, minute=0)))
            base_start = local_start.astimezone(pytz.UTC)

        created_entries = self.env['hr.work.entry']
        current_cursor = base_start

        # 1. Regular Hours Work Entry
        if summary.regular_hours > 0 and attendance_type:
            stop_time = current_cursor + timedelta(hours=summary.regular_hours)
            entry = self.env['hr.work.entry'].create({
                'name': f"Regular Attendance ({summary.employee_id.name})",
                'employee_id': summary.employee_id.id,
                'contract_id': contract.id,
                'work_entry_type_id': attendance_type.id,
                'date_start': current_cursor,
                'date_stop': stop_time,
                'daily_summary_id': summary.id,
            })
            created_entries |= entry
            current_cursor = stop_time

        # 2. Overtime Hours Work Entry
        if summary.ot_hours > 0 and overtime_type:
            stop_time = current_cursor + timedelta(hours=summary.ot_hours)
            entry = self.env['hr.work.entry'].create({
                'name': f"Overtime ({summary.employee_id.name})",
                'employee_id': summary.employee_id.id,
                'contract_id': contract.id,
                'work_entry_type_id': overtime_type.id,
                'date_start': current_cursor,
                'date_stop': stop_time,
                'daily_summary_id': summary.id,
            })
            created_entries |= entry
            current_cursor = stop_time

        # 3. Shortage / LOP Work Entry (if company policy == 'lop' or 'half_day')
        shortage_policy = summary.company_id.factory_shortage_policy
        if summary.shortage_hours > 0 and unpaid_type and shortage_policy in ['lop', 'half_day']:
            stop_time = current_cursor + timedelta(hours=summary.shortage_hours)
            entry = self.env['hr.work.entry'].create({
                'name': f"Unpaid Shortage ({summary.employee_id.name})",
                'employee_id': summary.employee_id.id,
                'contract_id': contract.id,
                'work_entry_type_id': unpaid_type.id,
                'date_start': current_cursor,
                'date_stop': stop_time,
                'daily_summary_id': summary.id,
            })
            created_entries |= entry

        # 4. Public Holiday Unworked Work Entry
        if summary.day_type == 'public_holiday' and summary.worked_hours == 0 and holiday_type:
            stop_time = current_cursor + timedelta(hours=summary.expected_hours)
            entry = self.env['hr.work.entry'].create({
                'name': f"Public Holiday ({summary.employee_id.name})",
                'employee_id': summary.employee_id.id,
                'contract_id': contract.id,
                'work_entry_type_id': holiday_type.id,
                'date_start': current_cursor,
                'date_stop': stop_time,
                'daily_summary_id': summary.id,
            })
            created_entries |= entry

        return created_entries
