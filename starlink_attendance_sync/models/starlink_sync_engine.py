import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StarlinkSyncEngine(models.AbstractModel):
    """Pairing + reconciliation logic for StarLink punches.

    Lives in an AbstractModel so cron records (`model_id`) can reference it
    and methods can be invoked without any data row.
    """

    _name = 'starlink.sync.engine'
    _description = 'StarLink Sync Engine'

    # ------------------------------------------------------------------
    # Configuration accessors
    # ------------------------------------------------------------------
    def _icp(self):
        return self.env['ir.config_parameter'].sudo()

    def _max_duration_for_shift(self, shift_code):
        icp = self._icp()
        keys = {
            'P1': 'starlink.duration_max_p1',
            'P2': 'starlink.duration_max_p2',
            'P3': 'starlink.duration_max_p3',
            'PG': 'starlink.duration_max_pg',
        }
        default_cap = float(icp.get_param('starlink.duration_max_default', '26') or 26)
        if not shift_code or shift_code not in keys:
            return default_cap
        return float(icp.get_param(keys[shift_code], default_cap) or default_cap)

    def _min_duration_hours(self):
        return float(self._icp().get_param('starlink.duration_min', '0') or 0)

    def _stale_open_hours(self):
        return float(self._icp().get_param('starlink.stale_open_hours', '18') or 18)

    def _retro_window_days(self):
        return int(self._icp().get_param('starlink.retro_window_days', '7') or 7)

    @staticmethod
    def _detect_shift(dt):
        """Bucket an hour to P1/P2/P3/PG based on local hour."""
        if not dt:
            return False
        h = dt.hour
        # P3 is the overnight shift — punches between 22:00 and 06:00.
        if h >= 22 or h < 6:
            return 'P3'
        if 6 <= h < 9:
            return 'P1'
        if 9 <= h < 14:
            return 'PG' if h >= 9 else 'P1'
        if 14 <= h < 22:
            return 'P2'
        return False

    # ------------------------------------------------------------------
    # Pairing
    # ------------------------------------------------------------------
    def _pair_punches(self, sync_logs):
        """Pair IN/OUT logs into hr.attendance, logging exceptions for problems.

        ``sync_logs`` is a recordset of starlink.sync.log; iterate per
        (company, employee) ascending by punch_time so OUT can find the
        latest unpaired IN.
        """
        if not sync_logs:
            return
        # Sudo the whole batch so internal writes are not blocked by ACLs of
        # the calling user — the engine is system-level glue.
        sync_logs = sync_logs.sudo()
        Attendance = self.env['hr.attendance'].sudo()
        Exception_ = self.env['starlink.punch.exception'].sudo()

        # Process per (company, employee) for stable ordering and isolation.
        sync_logs = sync_logs.filtered(lambda l: l.employee_id)
        groups = {}
        for log in sync_logs.sorted(key=lambda l: (l.company_id.id, l.employee_id.id, l.punch_time)):
            groups.setdefault((log.company_id.id, log.employee_id.id), []).append(log)

        for (company_id, employee_id), logs in groups.items():
            company = self.env['res.company'].browse(company_id)
            employee = self.env['hr.employee'].browse(employee_id)

            # Find the latest unpaired IN log for this employee earlier than
            # the oldest in the batch — needed so reconciliation across
            # multiple cron runs still pairs correctly.
            earliest = min(l.punch_time for l in logs)
            pending_in = self.env['starlink.sync.log'].sudo().search([
                ('company_id', '=', company_id),
                ('employee_id', '=', employee_id),
                ('inout', '=', 'I'),
                ('attendance_id', '=', False),
                ('sync_status', 'in', ('pending', 'paired')),
                ('punch_time', '<', earliest),
            ], order='punch_time desc', limit=1)
            pending_in = pending_in or self.env['starlink.sync.log']

            for log in logs:
                if log.sync_status not in ('pending',):
                    # Already processed (e.g., paired previously); skip.
                    continue
                if log.inout == 'I':
                    if pending_in:
                        # Earlier IN was never closed — flag as duplicate_in
                        Exception_.create({
                            'employee_id': employee.id,
                            'badge_code': pending_in.badge_code,
                            'punch_time': pending_in.punch_time,
                            'issue_type': 'duplicate_in',
                            'company_id': company.id,
                            'sync_log_ids': [(6, 0, [pending_in.id])],
                        })
                        pending_in.write({
                            'sync_status': 'skipped',
                            'error_message': _('Duplicate IN — superseded by a later IN.'),
                            'processed_at': fields.Datetime.now(),
                        })
                    pending_in = log
                elif log.inout == 'O':
                    if not pending_in:
                        # Orphan OUT
                        exc = Exception_.create({
                            'employee_id': employee.id,
                            'badge_code': log.badge_code,
                            'punch_time': log.punch_time,
                            'issue_type': 'orphan_out',
                            'company_id': company.id,
                            'sync_log_ids': [(6, 0, [log.id])],
                        })
                        log.write({
                            'sync_status': 'skipped',
                            'exception_id': exc.id,
                            'error_message': _('Orphan OUT — no preceding IN found.'),
                            'processed_at': fields.Datetime.now(),
                        })
                        continue

                    in_log = pending_in
                    duration = (log.punch_time - in_log.punch_time).total_seconds() / 3600.0
                    cap = self._max_duration_for_shift(in_log.shift_code or log.shift_code)
                    minimum = self._min_duration_hours()
                    if duration <= minimum or duration > cap:
                        exc = Exception_.create({
                            'employee_id': employee.id,
                            'badge_code': log.badge_code,
                            'punch_time': log.punch_time,
                            'issue_type': 'bad_duration',
                            'company_id': company.id,
                            'sync_log_ids': [(6, 0, [in_log.id, log.id])],
                            'resolution_notes': _('Computed duration: %.2f hours (cap %.2f).') % (duration, cap),
                        })
                        for l in (in_log, log):
                            l.write({
                                'sync_status': 'skipped',
                                'exception_id': exc.id,
                                'error_message': _('Bad duration: %.2f hours') % duration,
                                'processed_at': fields.Datetime.now(),
                            })
                        pending_in = self.env['starlink.sync.log']
                        continue

                    # Skip if hr.attendance already exists (idempotent reconciliation)
                    existing = Attendance.search([
                        ('employee_id', '=', employee.id),
                        ('check_in', '=', in_log.punch_time),
                    ], limit=1)
                    if existing:
                        for l in (in_log, log):
                            l.write({
                                'sync_status': 'paired',
                                'attendance_id': existing.id,
                                'processed_at': fields.Datetime.now(),
                            })
                        pending_in = self.env['starlink.sync.log']
                        continue

                    # Create the hr.attendance — let Odoo's own constraints
                    # (overlap / single-open) raise; we convert that into a
                    # bad_duration exception so it can be triaged.
                    try:
                        attendance = Attendance.with_company(company).create({
                            'employee_id': employee.id,
                            'check_in': in_log.punch_time,
                            'check_out': log.punch_time,
                            'in_mode': 'technical',
                            'out_mode': 'technical',
                            'starlink_log_in_id': in_log.id,
                            'starlink_log_out_id': log.id,
                        })
                    except ValidationError as err:
                        exc = Exception_.create({
                            'employee_id': employee.id,
                            'badge_code': log.badge_code,
                            'punch_time': log.punch_time,
                            'issue_type': 'bad_duration',
                            'company_id': company.id,
                            'sync_log_ids': [(6, 0, [in_log.id, log.id])],
                            'resolution_notes': str(err),
                        })
                        for l in (in_log, log):
                            l.write({
                                'sync_status': 'error',
                                'exception_id': exc.id,
                                'error_message': str(err)[:240],
                                'processed_at': fields.Datetime.now(),
                            })
                        pending_in = self.env['starlink.sync.log']
                        continue

                    for l in (in_log, log):
                        l.write({
                            'sync_status': 'paired',
                            'attendance_id': attendance.id,
                            'processed_at': fields.Datetime.now(),
                        })
                    pending_in = self.env['starlink.sync.log']

            # End-of-batch: a leftover unclosed IN inside this batch is not yet
            # an exception (the OUT may arrive later) — leave it pending.

        # Update the engine's own checkpoint. Note: ``live_pull`` is owned by
        # the ingest agent (Windows script) and tracks "what was last pushed
        # into Odoo". The engine writes a separate checkpoint so the two
        # never race.
        latest_pt = max(sync_logs.mapped('punch_time') or [False])
        if latest_pt:
            for company in sync_logs.mapped('company_id'):
                self.env['starlink.sync.checkpoint'].sudo().get_or_create(
                    'live_pair', company,
                ).touch(last_sync_at=latest_pt)

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------
    def _reconcile_window(self, date_from, date_to, company=None):
        """Re-run pairing across logs in a window for one (or all) companies."""
        domain = [
            ('punch_time', '>=', date_from),
            ('punch_time', '<=', date_to),
            ('sync_status', 'in', ('pending', 'skipped', 'error')),
        ]
        if company:
            domain.append(('company_id', '=', company.id))

        logs = self.env['starlink.sync.log'].sudo().search(domain)
        if not logs:
            return self.env['starlink.sync.log']

        # Reset transient outcomes; keep `paired` ones untouched (idempotent).
        logs.write({
            'sync_status': 'pending',
            'exception_id': False,
            'error_message': False,
            'processed_at': False,
        })
        self._pair_punches(logs)

        # Refresh the reconciliation checkpoint.
        for c in logs.mapped('company_id'):
            self.env['starlink.sync.checkpoint'].sudo().get_or_create(
                'nightly_reconciliation', c,
            ).touch(last_sync_at=fields.Datetime.now())
        return logs

    def _check_stale_open_attendance(self, company=None):
        """Find hr.attendance with no check_out older than threshold."""
        threshold = fields.Datetime.now() - timedelta(hours=self._stale_open_hours())
        domain = [
            ('check_out', '=', False),
            ('check_in', '<=', threshold),
        ]
        if company:
            domain.append(('employee_id.company_id', '=', company.id))
        attendances = self.env['hr.attendance'].sudo().search(domain)
        Exception_ = self.env['starlink.punch.exception'].sudo()
        for att in attendances:
            already = Exception_.search([
                ('issue_type', '=', 'missing_checkout'),
                ('related_attendance_id', '=', att.id),
                ('resolved', '=', False),
            ], limit=1)
            if already:
                continue
            Exception_.create({
                'employee_id': att.employee_id.id,
                'badge_code': att.employee_id.barcode or False,
                'punch_time': att.check_in,
                'issue_type': 'missing_checkout',
                'severity': 'high',
                'company_id': att.employee_id.company_id.id or self.env.company.id,
                'related_attendance_id': att.id,
            })
        return attendances

    # ------------------------------------------------------------------
    # Cron entrypoints
    # ------------------------------------------------------------------
    @api.model
    def _cron_live_refresh(self):
        """Process pending logs ingested by the Windows agent (or internal puller).

        Runs in three phases per company:
          1. Re-resolve barcode → employee for unmapped logs (admin may have
             added the mapping after ingestion).
          2. Raise ``employee_not_mapped`` exceptions for the still-unmapped.
          3. Pair the mapped pending logs into ``hr.attendance``.
        """
        # Optional internal pyodbc pull
        try:
            self.env['starlink.sql.puller']._pull_from_sql_server()
        except Exception as err:  # noqa: BLE001
            _logger.exception("StarLink SQL puller failed: %s", err)

        Log = self.env['starlink.sync.log'].sudo()
        Employee = self.env['hr.employee'].sudo()

        for company in self.env['res.company'].search([]):
            pending = Log.search([
                ('sync_status', '=', 'pending'),
                ('company_id', '=', company.id),
            ], limit=2000)
            if not pending:
                continue

            # Phase 1 + 2: resolve / flag unmapped
            for log in pending.filtered(lambda l: not l.employee_id):
                emp = Employee.search([
                    ('barcode', '=', (log.badge_code or '').strip()),
                    ('company_id', 'in', [company.id, False]),
                ], limit=1)
                if emp:
                    log.employee_id = emp.id
                else:
                    log._raise_unmapped_exception()

            # Phase 3: pair what's still pending and now has an employee
            mapped = pending.filtered(
                lambda l: l.employee_id and l.sync_status == 'pending'
            )
            if mapped:
                self._pair_punches(mapped)
        return True

    @api.model
    def _cron_nightly_reconcile(self):
        """Re-evaluate the last N days of logs across all companies."""
        days = self._retro_window_days()
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=days)
        for company in self.env['res.company'].search([]):
            self._reconcile_window(date_from, date_to, company=company)
        return True

    @api.model
    def _cron_stale_check(self):
        for company in self.env['res.company'].search([]):
            self._check_stale_open_attendance(company=company)
        return True

    # ------------------------------------------------------------------
    # Public action wrappers (callable from JS / buttons).
    # Methods prefixed with `_` are blocked by Odoo's RPC layer for
    # security; the dashboard calls these public ones instead.
    # ------------------------------------------------------------------
    @api.model
    def action_run_live_refresh(self):
        """Public entry-point for 'Reprocess Exceptions' on the dashboard."""
        self._cron_live_refresh()
        return True

    @api.model
    def action_run_nightly_reconcile(self):
        """Public entry-point to manually trigger the nightly retro pass."""
        self._cron_nightly_reconcile()
        return True

    @api.model
    def action_run_stale_check(self):
        """Public entry-point to manually trigger the stale-open scan."""
        self._cron_stale_check()
        return True
