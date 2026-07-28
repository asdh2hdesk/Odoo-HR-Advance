# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    factory_ot_start_after_standard = fields.Boolean(
        string='OT Starts After Standard Hours',
        default=True,
        help='If checked, overtime is calculated for hours worked beyond expected calendar daily hours.',
    )
    factory_grace_time_minutes = fields.Integer(
        string='Shortage Grace Time (Minutes)',
        default=15,
        help='Grace time in minutes before shortage hours are flagged.',
    )
    factory_shortage_policy = fields.Selection(
        selection=[
            ('lop', 'Loss of Pay (UNPAID Work Entry)'),
            ('half_day', 'Half Day Deduction'),
            ('ignore', 'Ignore Shortage'),
            ('manual_review', 'Manual HR Review (Default)'),
        ],
        string='Shortage Policy',
        default='manual_review',
        help='Default policy for handling work duration shortages on normal working days.',
    )
    factory_auto_generate_work_entries = fields.Boolean(
        string='Auto-Generate Work Entries on Approval',
        default=False,
        help='Automatically generate hr.work.entry records when daily attendance summary is approved.',
    )
    factory_night_shift_threshold_hours = fields.Float(
        string='Night Shift Window Threshold (Hours)',
        default=12.0,
        help='Maximum gap in hours to associate cross-midnight attendance punches with the previous calendar day.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    factory_ot_start_after_standard = fields.Boolean(
        related='company_id.factory_ot_start_after_standard',
        readonly=False,
    )
    factory_grace_time_minutes = fields.Integer(
        related='company_id.factory_grace_time_minutes',
        readonly=False,
    )
    factory_shortage_policy = fields.Selection(
        related='company_id.factory_shortage_policy',
        readonly=False,
    )
    factory_auto_generate_work_entries = fields.Boolean(
        related='company_id.factory_auto_generate_work_entries',
        readonly=False,
    )
    factory_night_shift_threshold_hours = fields.Float(
        related='company_id.factory_night_shift_threshold_hours',
        readonly=False,
    )
