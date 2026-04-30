from datetime import timedelta

from odoo import _, api, fields, models


class StarlinkReconcileWizard(models.TransientModel):
    _name = 'starlink.reconcile.wizard'
    _description = 'StarLink Reconciliation Wizard'

    date_from = fields.Datetime(
        required=True,
        default=lambda self: fields.Datetime.now() - timedelta(days=30),
    )
    date_to = fields.Datetime(
        required=True,
        default=lambda self: fields.Datetime.now(),
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        help="Leave empty to reconcile all accessible companies.",
    )
    log_count = fields.Integer(string='Logs Re-evaluated', readonly=True)
    paired_count = fields.Integer(string='Newly Paired', readonly=True)
    exception_count = fields.Integer(string='New Exceptions', readonly=True)

    def action_run(self):
        self.ensure_one()
        engine = self.env['starlink.sync.engine']
        before_paired = self.env['starlink.sync.log'].search_count([
            ('sync_status', '=', 'paired'),
        ])
        before_exc = self.env['starlink.punch.exception'].search_count([])

        logs = engine._reconcile_window(
            self.date_from, self.date_to, company=self.company_id or None,
        )

        after_paired = self.env['starlink.sync.log'].search_count([
            ('sync_status', '=', 'paired'),
        ])
        after_exc = self.env['starlink.punch.exception'].search_count([])

        self.write({
            'log_count': len(logs),
            'paired_count': max(0, after_paired - before_paired),
            'exception_count': max(0, after_exc - before_exc),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'starlink.reconcile.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_reconcile_30_days(self):
        """Convenience entry-point used by the dashboard 'Reconcile Last 30 Days' button."""
        wizard = self.create({
            'date_from': fields.Datetime.now() - timedelta(days=30),
            'date_to': fields.Datetime.now(),
            'company_id': self.env.company.id,
        })
        return wizard.action_run()
