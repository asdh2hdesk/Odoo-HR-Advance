# -*- coding: utf-8 -*-
{
    'name': 'Factory Biometric Attendance Processing & Work Entries',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Biometric-driven attendance processing pipeline for factory shift operations and payroll work entry generation',
    'description': """
Factory Biometric Attendance Processing
======================================
This module decouples operational shifts from standard resource calendars:
- Biometric attendance punches (hr.attendance) serve as the primary source of truth.
- Computes daily attendance summaries by summing actual attendance intervals.
- Uses contract resource.calendar as reference for standard daily hours and weekly off days.
- Supports 100% OT on worked weekly off / public holidays.
- Calculates regular, overtime, and shortage hours.
- Intermediate HR review model (attendance.daily.summary) with approval workflow.
- Generates standard hr.work.entry records for Payroll compatibility.
- Includes interactive OWL JS Workflow Guide & Live Hours Calculator.
""",
    'author': 'Balaji Bathini',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'hr_attendance',
        'hr_payroll',
        'hr_work_entry',
        'hr_contract',
        'hr_holidays',
        'hr_payroll_workdays_extended',
        'hr_attendance_extended',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_factory_attendance_processing_security.xml',
        'data/cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/attendance_daily_summary_views.xml',
        'views/attendance_processor_wizard_views.xml',
        'views/attendance_flow_guide_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_factory_attendance_processing/static/src/css/attendance_flow_dashboard.css',
            'hr_factory_attendance_processing/static/src/js/attendance_flow_dashboard.js',
            'hr_factory_attendance_processing/static/src/xml/attendance_flow_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
