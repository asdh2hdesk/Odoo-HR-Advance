{
    "name": "Salary Report 2.0",
    "version": "18.0.2.0.0",
    "category": "Human Resources",
    "summary": "Persistent Monthly Salary Sheet Snapshot, In-UI XML Editor & XLSX Export",
    "license": "LGPL-3",
    "author": "Balaji Bathini",
    "depends": [
        "hr", 
        "hr_payroll", 
        "l10n_in_hr_payroll", 
        "hr_employee_entended", 
        "payroll_salary_link", 
        "hr_custom_forms", 
        "hr_attendance"
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/salary_report_wizard_2_views.xml",
        "views/salary_report_2_views.xml",
    ],
    "application": True,
    "installable": True,
}
