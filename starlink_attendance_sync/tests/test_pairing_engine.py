from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('starlink_attendance_sync', 'post_install', '-at_install')
class TestPairingEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Alice Test',
            'barcode': 'TEST001',
            'company_id': cls.company.id,
        })
        cls.SyncLog = cls.env['starlink.sync.log']
        cls.Exception = cls.env['starlink.punch.exception']
        cls.Attendance = cls.env['hr.attendance']

    # ------------------------------------------------------------------
    def _make_log(self, dt, inout, badge='TEST001'):
        return self.SyncLog.create({
            'badge_code': badge,
            'punch_time': dt,
            'inout': inout,
            'company_id': self.company.id,
        })

    # ------------------------------------------------------------------
    def test_paired_in_out_creates_attendance(self):
        t_in = datetime(2026, 4, 1, 8, 0, 0)
        t_out = datetime(2026, 4, 1, 16, 30, 0)
        in_log = self._make_log(t_in, 'I')
        out_log = self._make_log(t_out, 'O')
        self.assertEqual(in_log.sync_status, 'paired')
        self.assertEqual(out_log.sync_status, 'paired')
        self.assertTrue(in_log.attendance_id)
        self.assertEqual(in_log.attendance_id, out_log.attendance_id)
        self.assertAlmostEqual(in_log.attendance_id.worked_hours, 8.5, places=1)

    def test_orphan_out_creates_exception(self):
        out_log = self._make_log(datetime(2026, 4, 1, 17, 0, 0), 'O')
        self.assertEqual(out_log.sync_status, 'skipped')
        self.assertTrue(out_log.exception_id)
        self.assertEqual(out_log.exception_id.issue_type, 'orphan_out')

    def test_duplicate_in_creates_exception(self):
        in1 = self._make_log(datetime(2026, 4, 1, 8, 0, 0), 'I')
        in2 = self._make_log(datetime(2026, 4, 1, 9, 0, 0), 'I')
        self.assertEqual(in1.sync_status, 'skipped',
                         "Earlier IN should be flagged when a later IN arrives unclosed")
        excs = self.Exception.search([('issue_type', '=', 'duplicate_in')])
        self.assertTrue(excs, "duplicate_in exception must exist")
        # The later IN remains pending — eligible to be closed by a future OUT
        self.assertEqual(in2.sync_status, 'pending')

    def test_bad_duration_creates_exception_p1(self):
        # 17h on a P1 shift exceeds the P1 cap (default 12h)
        t_in = datetime(2026, 4, 1, 6, 0, 0)
        t_out = datetime(2026, 4, 1, 23, 0, 0)
        in_log = self._make_log(t_in, 'I')
        out_log = self._make_log(t_out, 'O')
        self.assertEqual(in_log.sync_status, 'skipped')
        self.assertEqual(out_log.sync_status, 'skipped')
        self.assertEqual(out_log.exception_id.issue_type, 'bad_duration')
        # No attendance should have been created
        self.assertFalse(self.Attendance.search([
            ('employee_id', '=', self.employee.id),
            ('check_in', '=', t_in),
        ]))

    def test_overnight_p3_pairs_successfully(self):
        # P3 cap is 16h by default; 8h overnight pair must succeed
        t_in = datetime(2026, 4, 1, 22, 30, 0)
        t_out = datetime(2026, 4, 2, 6, 30, 0)
        in_log = self._make_log(t_in, 'I')
        out_log = self._make_log(t_out, 'O')
        self.assertEqual(in_log.sync_status, 'paired')
        self.assertEqual(out_log.sync_status, 'paired')
        self.assertEqual(in_log.shift_code, 'P3')

    def test_reconcile_skips_existing_attendance(self):
        # Pre-create an hr.attendance directly
        t_in = datetime(2026, 4, 1, 8, 0, 0)
        t_out = datetime(2026, 4, 1, 16, 0, 0)
        existing = self.Attendance.create({
            'employee_id': self.employee.id,
            'check_in': t_in,
            'check_out': t_out,
        })
        # Now ingest matching logs
        in_log = self._make_log(t_in, 'I')
        out_log = self._make_log(t_out, 'O')
        self.assertEqual(in_log.sync_status, 'paired')
        self.assertEqual(in_log.attendance_id, existing,
                         "Engine must reuse existing hr.attendance, not duplicate it")
        # Only the original attendance exists
        self.assertEqual(
            self.Attendance.search_count([
                ('employee_id', '=', self.employee.id),
                ('check_in', '=', t_in),
            ]),
            1,
        )

    def test_employee_not_mapped_creates_exception(self):
        log = self._make_log(datetime(2026, 4, 1, 8, 0, 0), 'I', badge='UNKNOWN999')
        self.assertEqual(log.sync_status, 'error')
        self.assertTrue(log.exception_id)
        self.assertEqual(log.exception_id.issue_type, 'employee_not_mapped')

    def test_stale_open_attendance_creates_exception(self):
        old = datetime.now() - timedelta(hours=24)
        att = self.Attendance.create({
            'employee_id': self.employee.id,
            'check_in': old,
        })
        self.env['starlink.sync.engine']._check_stale_open_attendance(self.company)
        excs = self.Exception.search([
            ('issue_type', '=', 'missing_checkout'),
            ('related_attendance_id', '=', att.id),
        ])
        self.assertTrue(excs)
        # Idempotent: running again does not duplicate
        self.env['starlink.sync.engine']._check_stale_open_attendance(self.company)
        excs2 = self.Exception.search([
            ('issue_type', '=', 'missing_checkout'),
            ('related_attendance_id', '=', att.id),
        ])
        self.assertEqual(len(excs), len(excs2))

    def test_reconcile_window_picks_up_pending(self):
        t_in = datetime(2026, 3, 15, 8, 0, 0)
        t_out = datetime(2026, 3, 15, 16, 0, 0)
        in_log = self._make_log(t_in, 'I')
        out_log = self._make_log(t_out, 'O')
        # Force them back to pending to simulate a prior failed run
        (in_log + out_log).write({'sync_status': 'pending', 'attendance_id': False,
                                   'exception_id': False})
        self.env['starlink.sync.engine']._reconcile_window(
            t_in - timedelta(days=1), t_out + timedelta(days=1), company=self.company,
        )
        in_log.invalidate_recordset()
        out_log.invalidate_recordset()
        self.assertEqual(in_log.sync_status, 'paired')
        self.assertEqual(out_log.sync_status, 'paired')

    def test_kpi_dashboard_counts(self):
        # Mix of resolved and pending
        self._make_log(datetime(2026, 4, 1, 17, 0, 0), 'O')        # orphan
        self._make_log(datetime(2026, 4, 2, 8, 0, 0), 'I')
        self._make_log(datetime(2026, 4, 2, 9, 0, 0), 'I')         # duplicate
        kpis = self.Exception.get_dashboard_kpis()
        self.assertGreaterEqual(kpis['orphan_out'], 1)
        self.assertGreaterEqual(kpis['duplicate_in'], 1)
        self.assertIn('logs_total', kpis)

    def test_deferred_pairing_runs_only_on_cron(self):
        """When ingest agent passes starlink_defer_pairing, create() must NOT pair."""
        SL = self.SyncLog.with_context(starlink_defer_pairing=True)
        in_log = SL.create({
            'badge_code': 'TEST001',
            'punch_time': datetime(2026, 4, 5, 8, 0, 0),
            'inout': 'I',
            'company_id': self.company.id,
        })
        out_log = SL.create({
            'badge_code': 'TEST001',
            'punch_time': datetime(2026, 4, 5, 16, 0, 0),
            'inout': 'O',
            'company_id': self.company.id,
        })
        # Both stay pending; no attendance yet
        self.assertEqual(in_log.sync_status, 'pending')
        self.assertEqual(out_log.sync_status, 'pending')
        self.assertFalse(self.Attendance.search([
            ('employee_id', '=', self.employee.id),
            ('check_in', '=', datetime(2026, 4, 5, 8, 0, 0)),
        ]))

        # Now the live-refresh cron runs and pairs them
        self.env['starlink.sync.engine']._cron_live_refresh()
        in_log.invalidate_recordset()
        out_log.invalidate_recordset()
        self.assertEqual(in_log.sync_status, 'paired')
        self.assertEqual(out_log.sync_status, 'paired')
        self.assertTrue(in_log.attendance_id)

    def test_deferred_unmapped_resolved_by_cron(self):
        """If badge had no mapping at ingest, cron retries the lookup."""
        SL = self.SyncLog.with_context(starlink_defer_pairing=True)
        log = SL.create({
            'badge_code': 'LATE_MAP',
            'punch_time': datetime(2026, 4, 6, 8, 0, 0),
            'inout': 'I',
            'company_id': self.company.id,
        })
        self.assertFalse(log.employee_id)
        self.assertEqual(log.sync_status, 'pending')

        # Admin maps the badge after the fact
        emp = self.env['hr.employee'].create({
            'name': 'Late Map', 'barcode': 'LATE_MAP', 'company_id': self.company.id,
        })

        self.env['starlink.sync.engine']._cron_live_refresh()
        log.invalidate_recordset()
        self.assertEqual(log.employee_id, emp,
                         "Cron should re-resolve barcode → employee post-ingest")
