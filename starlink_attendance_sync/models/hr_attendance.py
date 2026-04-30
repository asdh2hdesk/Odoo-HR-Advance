from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    starlink_log_in_id = fields.Many2one(
        'starlink.sync.log', string='StarLink IN Log', readonly=True, ondelete='set null',
    )
    starlink_log_out_id = fields.Many2one(
        'starlink.sync.log', string='StarLink OUT Log', readonly=True, ondelete='set null',
    )
    starlink_synced = fields.Boolean(
        string='From StarLink',
        compute='_compute_starlink_synced',
        store=True,
    )

    def _compute_starlink_synced(self):
        for rec in self:
            rec.starlink_synced = bool(rec.starlink_log_in_id or rec.starlink_log_out_id)
