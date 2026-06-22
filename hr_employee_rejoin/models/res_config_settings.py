from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_rejoining_employee_tracking = fields.Boolean(
        string="Rejoining Employee Tracking",
        config_parameter='hr_employee_rejoin.enable_rejoining_employee_tracking',
        default=True
    )
    copy_employee_documents = fields.Boolean(
        string="Auto Copy Documents",
        config_parameter='hr_employee_rejoin.copy_employee_documents',
        default=True
    )
    copy_employee_skills = fields.Boolean(
        string="Auto Copy Skills",
        config_parameter='hr_employee_rejoin.copy_employee_skills',
        default=True
    )
    copy_employee_education = fields.Boolean(
        string="Auto Copy Education",
        config_parameter='hr_employee_rejoin.copy_employee_education',
        default=True
    )
    auto_generate_employee_code = fields.Boolean(
        string="Auto Generate Employee Code",
        config_parameter='hr_employee_rejoin.auto_generate_employee_code',
        default=True
    )
