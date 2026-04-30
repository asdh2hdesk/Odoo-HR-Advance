from odoo import api, fields, models


class StarlinkSyncCheckpoint(models.Model):
    _name = 'starlink.sync.checkpoint'
    _description = 'StarLink Sync Checkpoint'
    _order = 'company_id, name'

    name = fields.Char(required=True, help="Checkpoint identifier, e.g. 'live_pull', 'nightly_reconciliation'.")
    last_sync_at = fields.Datetime(help="Latest successfully ingested punch_time.")
    last_run_at = fields.Datetime(help="When this checkpoint was last touched.")
    retro_window_start = fields.Datetime(help="Earliest punch_time to re-evaluate on next reconciliation.")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, ondelete='cascade',
    )

    _sql_constraints = [
        ('uniq_name_company', 'unique(name, company_id)', 'Checkpoint name must be unique per company.'),
    ]

    @api.model
    def get_or_create(self, name, company=None):
        company = company or self.env.company
        cp = self.search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
        if not cp:
            cp = self.create({'name': name, 'company_id': company.id})
        return cp

    def touch(self, last_sync_at=None):
        vals = {'last_run_at': fields.Datetime.now()}
        if last_sync_at:
            vals['last_sync_at'] = last_sync_at
        self.write(vals)
