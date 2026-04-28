{
    'name': 'StarLink Attendance Sync',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Sync StarLink biometric punches into HR Attendance with exception tracking',
    'description': """
StarLink Attendance Sync
========================
Receives biometric punches from external StarLink (SQL Server) systems,
pairs them into hr.attendance records, logs every decision, and tracks
problem rows (orphan OUT, duplicate IN, bad duration, employee not mapped,
missing checkout) in a dedicated exception model with a KPI dashboard
and reconciliation tooling.

Supports two ingestion paths:
  * External script writes ``starlink.sync.log`` rows over XML-RPC.
  * Optional internal cron pulls directly from SQL Server via pyodbc
    (configured under Settings).

Multi-company aware. Shift-aware duration validation (P1/P2/P3/PG).
""",
    'author': 'BALAJI BATHINI',
    'website': '',
    'depends': ['hr_attendance', 'mail'],
    'external_dependencies': {'python': ['pyodbc']},
    'data': [
        'security/starlink_security.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/ir_cron_data.xml',
        'views/starlink_sync_log_views.xml',
        'views/starlink_punch_exception_views.xml',
        'views/starlink_sync_checkpoint_views.xml',
        'wizard/starlink_reconcile_wizard_views.xml',
        'views/starlink_dashboard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'starlink_attendance_sync/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
