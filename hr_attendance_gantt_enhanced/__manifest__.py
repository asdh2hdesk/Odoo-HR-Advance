{
    'name': 'Enhanced Attendance Gantt',
    'summary': """Enhanced Gantt view for Attendance""",
    'description': """
    Enhanced Gantt view for Attendance
    """,
    'version': '1.0',
    'author': 'Akshat Gupta',
    'license': 'LGPL-3',
    'website': 'https://github.com/Akshat-10',
    'category': 'Human Resources',
    'depends': ['hr_attendance_gantt', 'hr_holidays', 'report_xlsx', 'hr_induction',
                'hr_expense',
                'hr_employee_entended',
                ],
    'data': [
        'security/ir.model.access.csv',
        'views/attendance_report_wizard_views.xml',
        'reports/attendance_report.xml',
    ],
    'installable': True,
    'application': True,
    
}