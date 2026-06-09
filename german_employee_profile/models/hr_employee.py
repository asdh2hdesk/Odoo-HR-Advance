# -*- coding: utf-8 -*-
from odoo import models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def action_download_profile_docx(self):
        self.ensure_one()
        wizard = self.env["employee.profile.wizard"].create({
            "employee_id": self.id,
        })
        return wizard.action_generate_docx()
