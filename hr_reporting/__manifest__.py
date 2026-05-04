# -*- coding: utf-8 -*-
{

    "name": "Human Resources Forms Reporting",
    "version": "18.0.0.0",
    "category": "Human Resources",
    'sequence': -5,
    "author": "Akshat Gupta",
    'license': 'LGPL-3',
    'website': 'https://github.com/Akshat-10',
    "installable": True,
    "application": True,
    "summary": "Human Resources Forms Reporting",
    "depends": ["hr_custom_forms", "inventory_extended", "hr_recruitment_extended", "hr_payroll", 'l10n_in_hr_payroll', 'hr_employee_entended',
    'hr_employee_activity_calendar',
    "report_xlsx",
    'payroll_salary_link',
    'contract_salary_config',
    ],

    "data": [
        'security/ir.model.access.csv',
        'data/appointment_letter_sequence.xml',
        'views/appointment_letter_views.xml',
        'views/resignation_letter_views.xml',
        'report/resignation_action.xml',
        'report/resignation_report.xml',
        'views/leave_application_views.xml',
        'views/form15G_views.xml',
        'views/form_11_newsept_17_views.xml',
        'views/recruitment_views.xml',
        'views/ESIC_form_views.xml',
        'views/pf_form_views.xml',

        "views/covering_letter_views.xml",
        'report/covering_letter_action.xml',
        'report/covering_letter_report.xml',

        "views/mw_notice_views.xml",
        "views/formd_excel_views.xml",
        "views/form2_word_views.xml",
        "views/er1_word_views.xml",
        "views/hr_salary_attachment_excel.xml",
        'views/hr_custom_form_staff_loan_views.xml',
        "views/nomination_form_views.xml",
        'views/labour_colony_agreement_views.xml',



        ],
}