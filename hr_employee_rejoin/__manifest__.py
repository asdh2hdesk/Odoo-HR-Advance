# -*- coding: utf-8 -*-
{
    'name': "Employee Rejoining Management",
    'summary': """Handle employee rejoining process, copy previous data, and generate new records.""",
    'description': """
Employee Rejoining Management
=============================
This module allows HR to manage employees who have resigned and rejoined the company.
It features:
- Tracking of employee rejoining history.
- Auto-fetching of previous employee data (Personal, Identity, Employment).
- Validating PAN against archived employees only.
- Auto-generation of new Employee Code.
- A smart button on Employee profile to show rejoining history.
    """,
    'author': "Balaji Bathini",
    'category': 'Human Resources/Employees',
    'version': '18.0.1.0.0',
    'depends': ['hr', 'l10n_in_hr_payroll'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/hr_employee_rejoin_history_views.xml',
        'wizard/hr_employee_rejoin_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
