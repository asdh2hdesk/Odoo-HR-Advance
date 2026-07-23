{
    'name': 'HR Attendance Excel Report',
    'summary': """Monthly Attendance master Excel Report with P/W/A status and formulas""",
    'description': """
        Generate Monthly Attendance master Report in Excel format.
        Features:
        - Date range selection (From Date - To Date)
        - All employees or selected employees option
        - Company name heading centered
        - Date range and Month display
        - Employee details: S.No, Name, Code, Department, Job Position, Joining Date, Week Off Day
        - Daily attendance with weekday headers (SAT, SUN, MON, TUE, WED, THU, FRI)
        - Status codes: P (Present), W (Weekoff), A (Absent), H (Holiday)
        - Color coding for P, W, A, H statuses
        - Summary columns with Excel formulas for auto-calculation
        - Present Days, Weekoff Days, Absent Days, Holidays, Total with formulas
    """,
    'version': '1.0',
    'author': 'Akshat Gupta',
    'license': 'LGPL-3',
    'website': 'https://github.com/Akshat-10',
    'sequence': -8,
    'category': 'Human Resources',
    'depends': ['hr_attendance', 'hr_holidays', 'hr', 'report_xlsx', 'resource', 'hr_employee_entended'],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_leave_type_data.xml',
        'views/attendance_master_wizard_views.xml',
        'reports/attendance_master_report.xml',
    ],
    'installable': True,
    'application': True,
}
