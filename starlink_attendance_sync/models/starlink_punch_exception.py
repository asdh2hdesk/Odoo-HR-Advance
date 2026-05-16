from odoo import _, api, fields, models

ISSUE_TYPES = [
    ('orphan_out', 'Orphan Out'),
    ('duplicate_in', 'Duplicate In'),
    ('bad_duration', 'Bad Duration'),
    ('employee_not_mapped', 'Employee Not Mapped'),
    ('missing_checkout', 'Missing Checkout'),
    ('ingestion_error', 'Ingestion Error'),
]

SEVERITY = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
]

DEFAULT_SEVERITY = {
    'orphan_out': 'medium',
    'duplicate_in': 'low',
    'bad_duration': 'medium',
    'employee_not_mapped': 'high',
    'missing_checkout': 'high',
    'ingestion_error': 'high',
}


class StarlinkPunchException(models.Model):
    _name = 'starlink.punch.exception'
    _description = 'StarLink Punch Exception'
    _inherit = ['mail.thread']
    _order = 'punch_time desc, id desc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one('hr.employee', index=True, ondelete='set null')
    badge_code = fields.Char(index=True)
    punch_time = fields.Datetime(index=True)
    issue_type = fields.Selection(ISSUE_TYPES, required=True, tracking=True, index=True)
    severity = fields.Selection(SEVERITY, default='medium', required=True, tracking=True)
    resolved = fields.Boolean(default=False, tracking=True)
    resolved_by = fields.Many2one('res.users', readonly=True)
    resolved_at = fields.Datetime(readonly=True)
    resolution_notes = fields.Text()
    sync_log_ids = fields.One2many('starlink.sync.log', 'exception_id', string='Sync Logs')
    related_attendance_id = fields.Many2one('hr.attendance', ondelete='set null',
                                            help="Attendance record this exception relates to (when applicable).")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    display_name = fields.Char(compute='_compute_display_name_field', store=False)

    @api.depends('issue_type', 'badge_code', 'punch_time')
    def _compute_display_name_field(self):
        labels = dict(ISSUE_TYPES)
        for rec in self:
            rec.display_name = '[%s] %s @ %s' % (
                labels.get(rec.issue_type, rec.issue_type or ''),
                rec.badge_code or _('?'),
                fields.Datetime.to_string(rec.punch_time) if rec.punch_time else '',
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('issue_type') and not vals.get('severity'):
                vals['severity'] = DEFAULT_SEVERITY.get(vals['issue_type'], 'medium')
            vals.setdefault('company_id', self.env.company.id)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_resolve(self):
        for rec in self:
            rec.write({
                'resolved': True,
                'resolved_by': self.env.user.id,
                'resolved_at': fields.Datetime.now(),
            })
        return True

    def action_unresolve(self):
        self.write({
            'resolved': False,
            'resolved_by': False,
            'resolved_at': False,
        })
        return True

    def action_retry(self):
        """Re-feed the linked sync logs through the pairing engine."""
        logs = self.mapped('sync_log_ids')
        if not logs:
            return False
        return logs.action_reprocess()

    @api.model
    def action_retry_selected(self):
        """Bulk action invoked from a list view; uses ``active_ids``."""
        ids = self.env.context.get('active_ids') or []
        if not ids:
            return False
        return self.browse(ids).action_retry()

    # ------------------------------------------------------------------
    # KPI helpers (consumed by the OWL dashboard)
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_kpis(self):
        company_ids = self.env.companies.ids
        domain_company = [('company_id', 'in', company_ids)]

        def _count(extra):
            return self.search_count(domain_company + extra)

        kpis = {
            'orphan_out': _count([('issue_type', '=', 'orphan_out'), ('resolved', '=', False)]),
            'duplicate_in': _count([('issue_type', '=', 'duplicate_in'), ('resolved', '=', False)]),
            'bad_duration': _count([('issue_type', '=', 'bad_duration'), ('resolved', '=', False)]),
            'employee_not_mapped': _count(
                [('issue_type', '=', 'employee_not_mapped'), ('resolved', '=', False)]
            ),
            'missing_checkout': _count(
                [('issue_type', '=', 'missing_checkout'), ('resolved', '=', False)]
            ),
            'resolved': _count([('resolved', '=', True)]),
            'pending': _count([('resolved', '=', False)]),
            'total': _count([]),
        }
        # Sync log counters
        log_model = self.env['starlink.sync.log']
        kpis['logs_paired'] = log_model.search_count(
            domain_company + [('sync_status', '=', 'paired')]
        )
        kpis['logs_pending'] = log_model.search_count(
            domain_company + [('sync_status', '=', 'pending')]
        )
        kpis['logs_total'] = log_model.search_count(domain_company)
        return kpis

    @api.model
    def action_open_filtered(self, issue_type=None, resolved=None):
        domain = []
        if issue_type:
            domain.append(('issue_type', '=', issue_type))
        if resolved is not None:
            domain.append(('resolved', '=', resolved))
        return {
            'type': 'ir.actions.act_window',
            'name': _('StarLink Exceptions'),
            'res_model': 'starlink.punch.exception',
            'view_mode': 'list,form,pivot,graph',
            # The views array is required by Odoo 18's web client; without it
            # _preprocessAction crashes on `views.map()`.
            'views': [
                (False, 'list'),
                (False, 'form'),
                (False, 'pivot'),
                (False, 'graph'),
            ],
            'domain': domain,
            'target': 'current',
        }
