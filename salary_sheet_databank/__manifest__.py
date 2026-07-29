{
    'name': 'Salary Sheet Databank',
    'version': '18.0.1.0.0',
    'summary': 'Databank to manage monthly salary sheets and attachments in Kanban view',
    'description': """
        Salary Sheet Databank Application
        =================================
        This module allows HR and Finance teams to manage and store monthly salary sheets.
        
        Key Features:
        - Kanban view storing month salary sheet names
        - Many2many attachments displayed directly below sheet name/details
        - Company-specific records with multi-company security rules
        - Status tracking (Draft, Confirmed, Archived)
        - Search, filter, and group capabilities by month and year
    """,
    'category': 'Human Resources/Payroll',
    'author': 'Balaji Bathini',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
    ],
    'data': [
        'security/salary_sheet_security.xml',
        'security/ir.model.access.csv',
        'views/salary_sheet_databank_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
