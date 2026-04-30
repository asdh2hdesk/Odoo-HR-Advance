# -*- coding: utf-8 -*-
{
    'name': 'HR Payroll Custom Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Comprehensive HR Payroll Dashboard — attendance, salary, loans, leaves & payslips',
    'description': """
        Custom HR Payroll Dashboard featuring:
        - Attendance-wise salary breakdown
        - Actual payout salary summary
        - Daily attendance tracking
        - Leaves pending approval
        - Loan amounts (to be recovered & recovered)
        - Payslip overview
        - New joinees summary
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',

    # ── Only hard-require modules that are always present ──────────────────
    # hr_payroll, hr_attendance, hr_holidays are optional; the Python model
    # already handles missing models gracefully (see _get_loan_summary etc.)
    'depends': [
        'hr',
        'hr_payroll',
        'hr_attendance',
        'hr_holidays',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/hr_payroll_custom_dashboard_views.xml',
        'views/hr_payroll_menu.xml',           # standalone menu — no external parent
    ],

    'assets': {
        'web.assets_backend': [
            'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap',
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
            'https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
            'hr_payroll_dashboard/static/src/js/hr_payroll_custom_dashboard.js',
            'hr_payroll_dashboard/static/src/xml/dashboard.xml',
            'hr_payroll_dashboard/static/src/css/dashboard.css',
        ],
    },

    'installable': True,
    'application': True,          # makes it appear as an App with its own icon
    'auto_install': False,
    'license': 'LGPL-3',
}