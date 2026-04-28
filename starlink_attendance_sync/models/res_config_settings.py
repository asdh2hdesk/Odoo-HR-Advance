from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    starlink_sql_host = fields.Char(
        string='SQL Server Host',
        config_parameter='starlink.sql_host',
        help="e.g. HSML-PC\\SQLEXPRESS",
    )
    starlink_sql_db = fields.Char(
        string='SQL Database',
        config_parameter='starlink.sql_db',
        default='StarSql',
    )
    starlink_sql_user = fields.Char(
        string='SQL User',
        config_parameter='starlink.sql_user',
    )
    starlink_sql_password = fields.Char(
        string='SQL Password',
        config_parameter='starlink.sql_password',
    )
    starlink_sql_driver = fields.Char(
        string='ODBC Driver',
        config_parameter='starlink.sql_driver',
        default='SQL Server Native Client 10.0',
    )
    starlink_tz_source = fields.Char(
        string='Source Timezone',
        config_parameter='starlink.tz_source',
        default='Asia/Kolkata',
        help="Timezone the SQL Server timestamps are recorded in. Used for IST→UTC conversion.",
    )
    starlink_enable_internal_puller = fields.Boolean(
        string='Enable Internal SQL Puller',
        config_parameter='starlink.enable_internal_puller',
        help="When enabled, the live-refresh cron pulls directly from SQL Server via pyodbc.",
    )
    starlink_duration_max_p1 = fields.Float(
        string='Max Duration P1 (h)',
        config_parameter='starlink.duration_max_p1',
        default=12.0,
    )
    starlink_duration_max_p2 = fields.Float(
        string='Max Duration P2 (h)',
        config_parameter='starlink.duration_max_p2',
        default=12.0,
    )
    starlink_duration_max_p3 = fields.Float(
        string='Max Duration P3 (h)',
        config_parameter='starlink.duration_max_p3',
        default=16.0,
    )
    starlink_duration_max_pg = fields.Float(
        string='Max Duration PG (h)',
        config_parameter='starlink.duration_max_pg',
        default=12.0,
    )
    starlink_duration_max_default = fields.Float(
        string='Max Duration Default (h)',
        config_parameter='starlink.duration_max_default',
        default=26.0,
    )
    starlink_duration_min = fields.Float(
        string='Min Duration (h)',
        config_parameter='starlink.duration_min',
        default=0.0,
    )
    starlink_stale_open_hours = fields.Float(
        string='Stale Open Attendance Threshold (h)',
        config_parameter='starlink.stale_open_hours',
        default=18.0,
    )
    starlink_retro_window_days = fields.Integer(
        string='Retro Reconciliation Window (days)',
        config_parameter='starlink.retro_window_days',
        default=7,
    )
