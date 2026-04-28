import json
import logging
import pytz

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

SYNC_STATUS = [
    ('pending', 'Pending'),
    ('paired', 'Paired'),
    ('skipped', 'Skipped'),
    ('error', 'Error'),
]

INOUT = [
    ('I', 'In'),
    ('O', 'Out'),
]

SHIFT_CODES = [
    ('P1', 'P1 (06-14)'),
    ('P2', 'P2 (14-22)'),
    ('P3', 'P3 (22-06 overnight)'),
    ('PG', 'PG (09-18)'),
]


class StarlinkSyncLog(models.Model):
    _name = 'starlink.sync.log'
    _description = 'StarLink Sync Log'
    _inherit = ['mail.thread']
    _order = 'punch_time desc, id desc'
    _rec_name = 'badge_code'

    employee_id = fields.Many2one('hr.employee', string='Employee', index=True, ondelete='set null')
    badge_code = fields.Char(required=True, index=True)
    punch_time = fields.Datetime(required=True, index=True, help="Stored in UTC.")
    inout = fields.Selection(INOUT, required=True, string='I/O')
    machine_id = fields.Char(string='Machine')
    shift_code = fields.Selection(SHIFT_CODES, string='Shift')
    sync_status = fields.Selection(SYNC_STATUS, default='pending', required=True, tracking=True)
    attendance_id = fields.Many2one('hr.attendance', ondelete='set null', readonly=True)
    exception_id = fields.Many2one('starlink.punch.exception', ondelete='set null', readonly=True)
    raw_payload = fields.Text(help="Original payload (JSON) from StarLink for forensics.")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    processed_at = fields.Datetime(readonly=True)
    error_message = fields.Char(readonly=True)

    _sql_constraints = [
        (
            'uniq_punch',
            'unique(badge_code, punch_time, company_id)',
            'A punch with the same badge, time and company already exists.',
        ),
    ]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('company_id', self.env.company.id)
            company_id = vals['company_id']
            # Normalize incoming timezone if caller signals IST source via context
            if vals.get('punch_time') and self.env.context.get('starlink_tz_source'):
                vals['punch_time'] = self._convert_to_utc(
                    vals['punch_time'], self.env.context['starlink_tz_source'],
                )
            # Resolve employee from barcode if not provided
            if not vals.get('employee_id') and vals.get('badge_code'):
                emp = self.env['hr.employee'].sudo().search([
                    ('barcode', '=', vals['badge_code'].strip()),
                    ('company_id', 'in', [company_id, False]),
                ], limit=1)
                if emp:
                    vals['employee_id'] = emp.id
            # Auto-detect shift
            if vals.get('punch_time') and not vals.get('shift_code'):
                vals['shift_code'] = self.env['starlink.sync.engine']._detect_shift(
                    fields.Datetime.to_datetime(vals['punch_time'])
                )
            # Serialize raw_payload if dict provided
            payload = vals.get('raw_payload')
            if isinstance(payload, dict):
                vals['raw_payload'] = json.dumps(payload, default=str)

        records = super().create(vals_list)

        # Caller can pass {'starlink_defer_pairing': True} so a high-volume
        # ingest agent (Windows scheduler script) dumps rows fast and lets
        # the live-refresh cron pair them. Default keeps the synchronous
        # path so tests and manual creates still work as before.
        if self.env.context.get('starlink_defer_pairing'):
            return records

        for rec in records:
            if not rec.employee_id:
                rec._raise_unmapped_exception()
        records.filtered(lambda r: r.sync_status == 'pending' and r.employee_id) \
            ._trigger_pairing()
        return records

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _convert_to_utc(dt_value, tz_name):
        """Treat ``dt_value`` as a naive datetime in ``tz_name`` and return UTC."""
        dt = fields.Datetime.to_datetime(dt_value)
        if dt.tzinfo is not None:
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return dt
        return tz.localize(dt).astimezone(pytz.UTC).replace(tzinfo=None)

    def _raise_unmapped_exception(self):
        self.ensure_one()
        exc = self.env['starlink.punch.exception'].sudo().create({
            'employee_id': False,
            'badge_code': self.badge_code,
            'punch_time': self.punch_time,
            'issue_type': 'employee_not_mapped',
            'severity': 'high',
            'company_id': self.company_id.id,
            'sync_log_ids': [(6, 0, [self.id])],
        })
        self.write({
            'sync_status': 'error',
            'exception_id': exc.id,
            'error_message': _('Badge %s is not mapped to any employee.') % self.badge_code,
            'processed_at': fields.Datetime.now(),
        })

    def _trigger_pairing(self):
        if not self:
            return
        self.env['starlink.sync.engine']._pair_punches(self)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_reprocess(self):
        """Re-run pairing on selected logs (clears prior outcome first)."""
        for rec in self:
            rec.write({
                'sync_status': 'pending',
                'attendance_id': False,
                'error_message': False,
                'processed_at': False,
            })
        self.env['starlink.sync.engine']._pair_punches(self)
        return True

    def action_open_attendance(self):
        self.ensure_one()
        if not self.attendance_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'res_id': self.attendance_id.id,
            'view_mode': 'form',
        }
