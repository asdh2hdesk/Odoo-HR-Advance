from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    biometric_id = fields.Char(
        string="Biometric ID",
        copy=False,
        index=True
    )