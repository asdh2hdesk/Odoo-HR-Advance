# -*- coding: utf-8 -*-
{
    'name': "Employee Promotion & Salary Increment History",
    'summary': """Track employee promotion history, salary revisions, increment workflows, and historical records.""",
    'description': """
Employee Promotion & Salary Increment History
=============================================
This module allows HR to manage and track employee promotions and salary increases:
- **Promotion History**: Log changes in job position, department, and grade with effective dates and approval workflow.
- **Salary Increment History**: Record wage and CTC adjustments (percentage or fixed amount) with effective dates and approval workflow.
- **Employee Integration**: View historical promotions and salary revisions directly from the Employee profile with smart buttons and history tab.
    """,
    'author': "Balaji Bathini",
    'category': 'Human Resources/Employees',
    'version': '18.0.1.0.0',
    'depends': ['hr', 'hr_contract'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/hr_employee_promotion_views.xml',
        'views/hr_salary_increment_views.xml',
        'views/hr_employee_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
