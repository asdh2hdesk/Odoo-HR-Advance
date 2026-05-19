# -*- coding: utf-8 -*-
{
    
    "name": "Human Resources/Recruitment Modification",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    'sequence': 1,
    "author": "Akshat Gupta",
    'license': 'LGPL-3',    
    'website': 'https://github.com/Akshat-10',
    "installable": True,
    "application": True,
    "summary": "Custom modification in recruitment module",
    "depends": ["hr", "hr_recruitment", "mail", 'website', 'website_hr_recruitment', 'hr_recruitment_survey', 'hr_recruitment_skills', 'hr_skills', 'hr_contract_salary'],
    "data": [
        'data/mail_template.xml',
        "data/hr_recruitment_data.xml",
        "security/ir.model.access.csv",
        "security/recruitment_security.xml",
        "views/cft_approval_views.xml",
        "views/cft_members_views.xml",
        "views/hr_job_views_extended.xml",
        "views/hr_recruitment_extended_view.xml",
        "views/website_hr_recruitment_modify.xml",
        'views/hr_candidate_extended_view.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
                    'hr_recruitment_extended/static/src/scss/website_hr_recruitment.scss',
                    'hr_recruitment_extended/static/src/css/custom.css',
                    'hr_recruitment_extended/static/src/css/web_form.css',
                ],
        'web.assets_frontend': [
                '/hr_recruitment_extended/static/src/js/application_form.js',
                # '/hr_recruitment_extended/static/src/js/js_skills.js',
                # '/hr_recruitment_extended/static/src/js/recruitment_form.js',
            ],
    },
    
}
