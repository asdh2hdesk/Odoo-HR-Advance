from odoo import api, fields, models, tools


class CFTMember(models.Model):
    _name = 'cft.member'
    _description = 'CFT Member'

    user_id = fields.Many2one('res.users', string='User', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('user_company_unique', 'unique(user_id, company_id)',
         'This user is already a CFT member for this company.'),
    ]


class CFTApproval(models.Model):
    _name = 'cft.approval'
    _description = 'CFT Approval'

    job_id = fields.Many2one('hr.job', string='Job', required=True, ondelete='cascade')
    cft_member_id = fields.Many2one('res.users', string='CFT Member', required=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending')
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='job_id.company_id', store=True, index=True,
    )