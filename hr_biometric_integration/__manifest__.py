{
    'name': 'HR Biometric Integration',
    'version': '18.0.0.0',
    'summary': 'Biometric Device Integration with HR Attendance',
    'author': 'RAKESH ASD',
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_view.xml',
        'views/biometric_device_views.xml',
        'views/biometric_log_views.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
}