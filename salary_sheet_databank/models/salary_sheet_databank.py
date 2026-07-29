from odoo import models, fields, api, _

class SalarySheetDatabank(models.Model):
    _name = 'salary.sheet.databank'
    _description = 'Salary Sheet Databank'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, month desc, id desc'

    name = fields.Char(
        string='Salary Sheet Name',
        required=True,
        tracking=True,
        help="Name of the monthly salary sheet (e.g. January 2026 Salary Sheet)"
    )
    month = fields.Selection(
        selection=[
            ('01', 'January'),
            ('02', 'February'),
            ('03', 'March'),
            ('04', 'April'),
            ('05', 'May'),
            ('06', 'June'),
            ('07', 'July'),
            ('08', 'August'),
            ('09', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
        string='Month',
        required=True,
        default=lambda self: fields.Date.today().strftime('%m'),
        tracking=True
    )
    year = fields.Char(
        string='Year',
        required=True,
        default=lambda self: str(fields.Date.today().year),
        tracking=True,
        help="Year of the salary sheet stored as text"
    )
    date = fields.Date(
        string='Sheet Date',
        default=fields.Date.context_today,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
        help="Company to which this salary sheet belongs"
    )
    total_employees = fields.Integer(
        string='Total Employees',
        help="Number of employees included in this salary sheet"
    )
    total_amount = fields.Monetary(
        string='Total Salary Amount',
        currency_field='currency_id',
        help="Total payroll amount for this sheet"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )
    notes = fields.Html(
        string='Notes / Summary',
        help="Additional remarks or notes regarding this salary sheet"
    )
    color = fields.Integer(
        string='Color Index',
        default=0
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True
    )
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='salary_sheet_ir_attachment_rel',
        column1='salary_sheet_id',
        column2='attachment_id',
        string='Attachments',
        help="Attached salary sheet files (Excel, PDF, CSV, etc.)"
    )
    attachment_count = fields.Integer(
        string='Attachments Count',
        compute='_compute_attachment_count'
    )

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    def action_archive(self):
        for record in self:
            record.state = 'archived'
