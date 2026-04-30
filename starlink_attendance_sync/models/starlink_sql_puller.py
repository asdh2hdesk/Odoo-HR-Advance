import json
import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StarlinkSqlPuller(models.AbstractModel):
    """Optional internal cron path that pulls punches from SQL Server.

    Disabled by default. Enable from Settings > HR > StarLink and provide
    the SQL Server connection details. ``pyodbc`` must be installed on
    the Odoo host for this path to do anything.
    """

    _name = 'starlink.sql.puller'
    _description = 'StarLink SQL Puller'

    def _build_connection_string(self):
        icp = self.env['ir.config_parameter'].sudo()
        explicit = icp.get_param('starlink.sql_conn_str')
        if explicit:
            return explicit
        host = icp.get_param('starlink.sql_host')
        db = icp.get_param('starlink.sql_db')
        user = icp.get_param('starlink.sql_user')
        password = icp.get_param('starlink.sql_password')
        driver = icp.get_param('starlink.sql_driver', 'SQL Server Native Client 10.0')
        if not (host and db and user):
            return False
        return (
            "DRIVER={%s};SERVER=%s;DATABASE=%s;UID=%s;PWD=%s;"
            % (driver, host, db, user, password or '')
        )

    @api.model
    def _pull_from_sql_server(self, since=None, until=None):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('starlink.enable_internal_puller', 'False') != 'True':
            return self.env['starlink.sync.log']

        try:
            import pyodbc  # noqa: WPS433 (lazy import on purpose)
        except ImportError:
            _logger.warning(
                "starlink_attendance_sync: pyodbc not installed; internal puller disabled"
            )
            return self.env['starlink.sync.log']

        conn_str = self._build_connection_string()
        if not conn_str:
            _logger.info("starlink_attendance_sync: SQL connection not configured")
            return self.env['starlink.sync.log']

        Log = self.env['starlink.sync.log'].sudo()
        Checkpoint = self.env['starlink.sync.checkpoint'].sudo()

        created = self.env['starlink.sync.log']

        for company in self.env['res.company'].search([]):
            cp = Checkpoint.get_or_create('live_pull', company)
            window_since = since or cp.last_sync_at or (
                fields.Datetime.now() - timedelta(days=1)
            )
            window_until = until or fields.Datetime.now()

            try:
                conn = pyodbc.connect(conn_str, timeout=30)
            except Exception as err:  # noqa: BLE001
                _logger.exception("starlink_attendance_sync: SQL connect failed: %s", err)
                return created

            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT RTRIM(CARDNO), OFFICEPUNCH, INOUT, MACHINENO
                    FROM MachineRawPunch
                    WHERE OFFICEPUNCH > ?
                      AND OFFICEPUNCH <= ?
                    ORDER BY OFFICEPUNCH ASC
                    """,
                    window_since,
                    window_until,
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

            tz_source = icp.get_param('starlink.tz_source', 'Asia/Kolkata')
            for row in rows:
                badge_code = (row[0] or '').strip()
                punch_dt = row[1]
                inout = (row[2] or '').strip().upper()
                machine_id = (row[3] if len(row) > 3 else None) or False
                if not badge_code or inout not in ('I', 'O') or not punch_dt:
                    continue
                # Idempotent: rely on the unique (badge, punch_time, company)
                # constraint; pre-check to keep cron logs clean.
                if Log.search_count([
                    ('badge_code', '=', badge_code),
                    ('punch_time', '=', punch_dt),
                    ('company_id', '=', company.id),
                ]):
                    continue
                rec = Log.with_context(starlink_tz_source=tz_source).create({
                    'badge_code': badge_code,
                    'punch_time': punch_dt,
                    'inout': inout,
                    'machine_id': str(machine_id) if machine_id else False,
                    'company_id': company.id,
                    'raw_payload': json.dumps({
                        'CARDNO': badge_code,
                        'OFFICEPUNCH': str(punch_dt),
                        'INOUT': inout,
                        'MACHINENO': machine_id,
                    }),
                })
                created |= rec

            if rows:
                cp.touch(last_sync_at=window_until)

        return created
