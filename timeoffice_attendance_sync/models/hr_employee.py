# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    """Extend hr.employee with the identifier used by the Time Office
    system to report punches (``employee_code`` in the payload)."""

    _inherit = "hr.employee"

    biometric_code = fields.Char(
        string="Biometric Code",
        copy=False,
        index=True,
        help="Employee code as reported by the Time Office system "
        "(payload field 'employee_code'). Used to map incoming "
        "attendance punches to the correct Odoo employee.",
    )

    _sql_constraints = [
        (
            "biometric_code_uniq",
            "unique(biometric_code, company_id)",
            "The Biometric Code must be unique per company.",
        ),
    ]
