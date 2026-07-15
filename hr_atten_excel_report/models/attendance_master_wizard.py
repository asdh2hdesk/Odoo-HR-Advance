from odoo import models, fields, api
import datetime
from odoo.tools import date_utils
from pytz import timezone, UTC
from collections import defaultdict


class AttendancemasterWizard(models.TransientModel):
    _name = 'attendance.master.wizard'
    _description = 'Attendance Master Report Wizard'

    start_date = fields.Date(string='From Date', required=True)
    end_date = fields.Date(string='To Date', required=True)
    all_employees = fields.Boolean(string='All Employees', default=True)
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model
    def default_get(self, fields_list):
        """Set default values for start_date and end_date to current month."""
        res = super().default_get(fields_list)
        today = fields.Date.today()
        first_day = date_utils.start_of(today, 'month')
        last_day = date_utils.end_of(today, 'month')
        res['start_date'] = first_day
        res['end_date'] = last_day
        return res

    @api.onchange('start_date')
    def _onchange_start_date(self):
        """Update end_date to the last day of the month when start_date changes."""
        if self.start_date:
            self.end_date = date_utils.end_of(self.start_date, 'month')

    @api.onchange('all_employees')
    def _onchange_all_employees(self):
        """Clear employee selection when all employees is checked."""
        if self.all_employees:
            self.employee_ids = [(5, 0, 0)]

    def _get_employees(self):
        """Return employees based on selection."""
        if self.all_employees:
            return self.env['hr.employee'].search([('company_id', '=', self.company_id.id)])
        return self.employee_ids

    def _get_employee_weekoff_day(self, employee):
        """Get the primary week off day for an employee from their work calendar."""
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar:
            return 'N/A'
        
        # Get all working days from calendar
        working_days = set()
        for attendance in calendar.attendance_ids:
            working_days.add(int(attendance.dayofweek))
        
        # All days of week (0=Monday ... 6=Sunday)
        all_days = set(range(7))
        off_days = all_days - working_days
        
        day_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        if off_days:
            # Return the first weekoff day
            first_off = min(off_days)
            return day_names[first_off]
        return 'N/A'

    def _get_leave_type_code(self, leave_type_name):
        """Map leave type name to a short code for the detailed sheet."""
        name_lower = (leave_type_name or '').lower()
        
        # Define mapping for common leave types
        if 'casual' in name_lower or name_lower == 'cl':
            return 'CL'
        elif 'earned' in name_lower or 'annual' in name_lower or name_lower == 'el':
            return 'EL'
        elif 'sick' in name_lower or name_lower == 'sl':
            return 'SL'
        elif 'unpaid' in name_lower or 'lwp' in name_lower or 'loss of pay' in name_lower:
            return 'UL'
        elif 'management' in name_lower or 'mgmt' in name_lower:
            return 'ML'
        elif 'on duty' in name_lower or name_lower == 'od' or 'onduty' in name_lower:
            return 'OD'
        elif 'half' in name_lower:
            return 'HD'
        else:
            # Return first 2-3 letters as code
            return leave_type_name[:3].upper() if leave_type_name else 'L'

    def _get_daily_status(self, employee, start_date, end_date):
        """Calculate daily attendance status for an employee."""
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar:
            return {}, {}

        tz = timezone(calendar.tz) if calendar.tz else UTC
        start = tz.localize(datetime.datetime.combine(start_date, datetime.time.min))
        stop = tz.localize(datetime.datetime.combine(end_date, datetime.time.max))

        # Get attendances
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start.astimezone(UTC).replace(tzinfo=None)),
            ('check_in', '<=', stop.astimezone(UTC).replace(tzinfo=None)),
        ])

        # Build attendance by day with worked hours
        attendances_by_day = defaultdict(list)
        for att in attendances:
            day = att.check_in.astimezone(tz).date() if att.check_in else None
            if day:
                attendances_by_day[day].append(att)

        # Get validated leaves with their types
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('date_from', '<', stop.astimezone(UTC).replace(tzinfo=None)),
            ('date_to', '>', start.astimezone(UTC).replace(tzinfo=None)),
        ])

        # Build leave info by day with leave type details
        leave_info_by_day = {}
        for leave in leaves:
            leave_start = leave.date_from.astimezone(tz).date()
            leave_end = leave.date_to.astimezone(tz).date()
            leave_type_name = leave.holiday_status_id.name if leave.holiday_status_id else 'Leave'
            leave_type_code = self._get_leave_type_code(leave_type_name)
            # Check if it's a half-day leave using request_unit_half field
            is_half_day = leave.request_unit_half if hasattr(leave, 'request_unit_half') else False
            is_unpaid = leave.holiday_status_id.unpaid if leave.holiday_status_id else False
            
            current = leave_start
            while current <= leave_end:
                if start_date <= current <= end_date:
                    leave_info_by_day[current] = {
                        'type_name': leave_type_name,
                        'type_code': leave_type_code,
                        'is_half_day': is_half_day,
                        'is_unpaid': is_unpaid,
                        'number_of_days': leave.number_of_days,
                    }
                current += datetime.timedelta(days=1)

        # Get holidays (global leaves without resource)
        holidays = self.env['resource.calendar.leaves'].search([
            ('resource_id', '=', False),
            ('calendar_id', '=', calendar.id),
            ('date_from', '<', stop.astimezone(UTC).replace(tzinfo=None)),
            ('date_to', '>', start.astimezone(UTC).replace(tzinfo=None)),
        ])

        holiday_days = set()
        for holiday in holidays:
            holiday_start = holiday.date_from.astimezone(tz).date()
            holiday_stop = holiday.date_to.astimezone(tz).date()
            current = max(holiday_start, start_date)
            end_date_eff = min(holiday_stop, end_date)
            while current <= end_date_eff:
                holiday_days.add(current)
                current += datetime.timedelta(days=1)

        # Calculate daily status
        daily_status = {}
        daily_status_detailed = {}  # For detailed sheet with leave types
        date_range = [start_date + datetime.timedelta(days=x) for x in range((end_date - start_date).days + 1)]
        today = fields.Date.today()

        for day in date_range:
            detailed_info = {'status': '', 'leave_type': '', 'is_half_day': False}
            
            if day in holiday_days:
                status = 'H'  # Holiday
                detailed_info['status'] = 'H'
            elif day in leave_info_by_day:
                leave_data = leave_info_by_day[day]
                if leave_data['is_half_day']:
                    # Check if employee also has attendance on this half-day leave
                    if day in attendances_by_day:
                        status = 'P'  # Count as present (half day present + half day leave)
                        detailed_info['status'] = 'HD'  # Half Day
                        detailed_info['is_half_day'] = True
                    else:
                        status = 'L'
                        detailed_info['status'] = 'HD'
                        detailed_info['is_half_day'] = True
                else:
                    status = 'L'
                    detailed_info['status'] = leave_data['type_code']
                detailed_info['leave_type'] = leave_data['type_code']
            else:
                # Check if it's a week off day
                day_start = tz.localize(datetime.datetime.combine(day, datetime.time.min))
                day_end = tz.localize(datetime.datetime.combine(day, datetime.time.max))
                
                try:
                    attendance_intervals = calendar._attendance_intervals_batch(
                        day_start, day_end, resources=employee.resource_id
                    )[employee.resource_id.id]
                except:
                    attendance_intervals = []

                if not attendance_intervals:
                    status = 'W'  # Week off
                    detailed_info['status'] = 'W'
                else:
                    # Check if employee has attendance on this day
                    if day in attendances_by_day:
                        status = 'P'  # Present
                        detailed_info['status'] = 'P'
                    elif day > today:
                        status = ''  # Future date - leave blank
                        detailed_info['status'] = ''
                    else:
                        status = 'A'  # Absent
                        detailed_info['status'] = 'A'

            daily_status[day] = status
            daily_status_detailed[day] = detailed_info

        return daily_status, daily_status_detailed

    def _prepare_report_data(self):
        """Prepare data for the XLSX report."""
        self = self.sudo()
        self.ensure_one()
        employees = self._get_employees()
        
        data = {
            'company_name': self.company_id.name or '',
            'from_date': str(self.start_date),
            'to_date': str(self.end_date),
            'month_name': self.start_date.strftime('%B-%Y').upper(),
            'employees': [],
        }

        # Generate date headers
        date_range = [self.start_date + datetime.timedelta(days=x) 
                      for x in range((self.end_date - self.start_date).days + 1)]
        
        day_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        data['date_headers'] = []
        for d in date_range:
            data['date_headers'].append({
                'date': str(d),
                'day_num': d.day,
                'day_name': day_names[d.weekday()],
            })

        # Process each employee
        for idx, employee in enumerate(employees, start=1):
            daily_status, daily_status_detailed = self._get_daily_status(employee, self.start_date, self.end_date)
            
            # Safely get employee_code (may be from hr_employee_entended module)
            emp_code = ''
            if hasattr(employee, 'employee_code') and employee.employee_code:
                emp_code = employee.employee_code
            elif employee.barcode:
                emp_code = employee.barcode
            
            # Safely get joining_date (may be from hr_employee_entended module)
            doj = ''
            if hasattr(employee, 'joining_date') and employee.joining_date:
                doj = str(employee.joining_date)
            elif hasattr(employee, 'join_date') and employee.join_date:
                doj = str(employee.join_date)
            
            emp_data = {
                'sno': idx,
                'name': employee.name or '',
                'employee_code': emp_code,
                'department': employee.department_id.name if employee.department_id else '',
                'job_position': employee.job_id.name if employee.job_id else '',
                'date_of_joining': doj,
                'weekoff_day': self._get_employee_weekoff_day(employee),
                'daily_status': {str(d): daily_status.get(d, '') for d in date_range},
                'daily_status_detailed': {str(d): daily_status_detailed.get(d, {'status': '', 'leave_type': '', 'is_half_day': False}) for d in date_range},
            }
            data['employees'].append(emp_data)

        return data

    # def action_generate_report(self):
    #     """Generate the attendance master Excel report."""
    #     self.ensure_one()
    #     report_data = self._prepare_report_data()
    #     # Generate filename with month name
    #     month_name = self.start_date.strftime('%B-%Y')
    #     filename = f"Attendance_Master_{month_name}"
    #     return self.env.ref('hr_atten_excel_report.attendance_master_xlsx').report_action(
    #         self, 
    #         data={**report_data, 'report_filename': filename}
    #     )
    def action_generate_report(self):
        """Generate the attendance master Excel report."""
        self.ensure_one()
        report_data = self._prepare_report_data()
        # Remove the report_filename from data - it's not used for XLSX
        return self.env.ref('hr_atten_excel_report.attendance_master_xlsx').report_action(
            self, 
            data=report_data
        )
