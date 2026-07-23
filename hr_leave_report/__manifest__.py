{
    'name': 'HR Leave Report',
    'version': '18.0.1.0.0',
    'summary': 'Upload Attendance Report to HR Leave',
    'description': """
        This module adds an option to upload attendance reports in the HR Leave tree view.
    """,
    'category': 'Human Resources/Time Off',
    'author': 'Balaji Bathini',
    'depends': ['hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/upload_attendance_wizard_views.xml',
        'views/hr_leave_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
