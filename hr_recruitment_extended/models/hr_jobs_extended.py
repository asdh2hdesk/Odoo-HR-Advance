from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class Job(models.Model):
    _inherit = 'hr.job'


    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', compute='_compute_state', store=True, tracking=True)
    
    remarks = fields.Text(string='Remarks')
    budgeted = fields.Boolean(string='Budgeted', default=False)
    budget_selection = fields.Selection(
        [('budgeted', 'Budgeted'), ('non_budgeted', 'Non-Budgeted')],
        string='Budgeted/Non-Budgeted',
        compute='_compute_budget_selection',
        store=True,
        default='non_budgeted'
    )
    
    cft_member_ids = fields.Many2many(
        'res.users',
        relation='hr_job_cft_member_rel',
        column1='job_id',
        column2='user_id',
        string='CFT Members',
        store=True
    )
    
    cft_approval_ids = fields.One2many('cft.approval', 'job_id', string='CFT Approvals')
    is_cft_approval_required = fields.Boolean(compute='_compute_is_cft_approval_required', store=True)
    is_cft_approved = fields.Boolean(compute='_compute_is_cft_approved', store=True)
    can_approve_cft = fields.Boolean(
        string="Can Approve CFT",
        compute='_compute_can_approve_cft',
        store=False
    )
    
    user_has_approved = fields.Boolean(
        string='User Has Approved',
        compute='_compute_user_has_approved',
        store=False
    )
    
    can_publish = fields.Boolean(compute='_compute_can_publish', store=False)
    
    qualification = fields.Text(string='Qualification')
    experience = fields.Char(string='Experience (Years)')
    designation = fields.Char(string='Designation')
    ctc_currency_id = fields.Many2one(
        'res.currency',
        string='CTC Currency',
        default=lambda self: self.env.company.currency_id
    )
    ctc = fields.Monetary(
        string='CTC',
        currency_field='ctc_currency_id'
    )
    

    @api.model
    def create(self, vals):
        # Set initial state based on budgeted
        if 'budgeted' in vals:
            vals['state'] = 'approved' if vals['budgeted'] else 'draft'
        else:
            vals['state'] = 'draft'  # Default if not specified
        # Assign CFT members for non-budgeted jobs if not provided
        if not vals.get('budgeted', False) and 'cft_member_ids' not in vals:
            cft_members = self.env['cft.member'].search([
                ('company_id', '=', self.env.company.id),
            ]).mapped('user_id')
            if cft_members:
                vals['cft_member_ids'] = [(6, 0, cft_members.ids)]
        return super(Job, self).create(vals)

    def write(self, vals):
        # Update the record with provided values first
        res = super(Job, self).write(vals)
        # Check if 'budgeted' is being updated
        if 'budgeted' in vals:
            for record in self:
                # If budgeted is False and cft_member_ids is empty, assign default CFT members
                if not record.budgeted and not record.cft_member_ids:
                    cft_members = self.env['cft.member'].search([
                ('company_id', '=', self.env.company.id),
            ]).mapped('user_id')
                    if cft_members:
                        record.write({'cft_member_ids': [(6, 0, cft_members.ids)]})
        return res

    @api.onchange('budgeted')
    def _onchange_budgeted(self):
        """Automatically populate CFT members when budgeted=False"""
        for job in self:
            if not job.budgeted:
                # Fetch users from cft.member model
                cft_members = self.env['cft.member'].search([
                ('company_id', '=', self.env.company.id),
            ]).mapped('user_id')
                job.cft_member_ids = [(6, 0, cft_members.ids)]
                
    @api.depends('cft_approval_ids', 'cft_approval_ids.status')
    def _compute_user_has_approved(self):
        for job in self:
            # Check if the current user has an approved status in the CFT approvals
            job.user_has_approved = any(
                approval.status == 'approved' and 
                approval.cft_member_id.id == self.env.user.id 
                for approval in job.cft_approval_ids
            )
                
    @api.depends('budgeted', 'cft_approval_ids.status')
    def _compute_state(self):
        """Compute state based on budgeted and CFT approvals."""
        for job in self:
            if job.budgeted:
                job.state = 'approved'
            else:
                if not job.cft_approval_ids:
                    job.state = 'draft'
                else:
                    if any(approval.status == 'rejected' for approval in job.cft_approval_ids):
                        job.state = 'rejected'
                    elif all(approval.status == 'approved' for approval in job.cft_approval_ids):
                        job.state = 'approved'
                    else:
                        job.state = 'pending'
                        
    @api.depends('budgeted')
    def _compute_budget_selection(self):
        for job in self:
            job.budget_selection = 'budgeted' if job.budgeted else 'non_budgeted'

    @api.depends('budgeted')
    def _compute_is_cft_approval_required(self):
        for job in self:
            job.is_cft_approval_required = not job.budgeted

    @api.depends('cft_approval_ids.status')
    def _compute_is_cft_approved(self):
        for job in self:
            if job.cft_approval_ids:
                job.is_cft_approved = all(approval.status == 'approved' for approval in job.cft_approval_ids)
            else:
                job.is_cft_approved = False

    @api.depends('is_cft_approval_required', 'cft_approval_ids', 'cft_member_ids', 'active')
    def _compute_can_approve_cft(self):
        for job in self:
            if job.is_cft_approval_required and job.cft_approval_ids and job.active:
                current_user = self.env.user
                is_cft_member = current_user in job.cft_member_ids
                is_recruitment_manager = self.env.user.has_group('hr_recruitment.group_hr_recruitment_manager')
                job.can_approve_cft = is_cft_member or is_recruitment_manager
            else:
                job.can_approve_cft = False

    def create_and_send_for_approval(self):
        """Handle creation and sending for approval, then open the job form view."""
        if not self.budgeted:
            self.action_send_for_cft_approval()
        # Return action to open the view_hr_job_form form view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Position',
            'res_model': 'hr.job',
            'view_mode': 'form',
            'view_id': self.env.ref('hr_recruitment_extended.view_hr_job_form_extended').id,  # Replace 'your_module' with your actual module name
            'res_id': self.id,
            'target': 'current',
        }

    # Existing methods (included for completeness)
    def action_send_for_cft_approval(self):
        """Send job for CFT approval and set state to pending."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Job must be in Draft state to send for approval.')
        if not self.cft_member_ids:
            raise UserError('No CFT Members selected.')
        for member in self.cft_member_ids:
            self.env['cft.approval'].create({
                'job_id': self.id,
                'cft_member_id': member.id,
                'status': 'pending'
            })
        # State will update via _compute_state

    def action_approve_cft(self):
        """Approve the job as a CFT member."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError('Job must be in Pending state to approve.')
        current_user = self.env.user
        approval = self.cft_approval_ids.filtered(lambda a: a.cft_member_id == current_user)
        if approval:
            approval.write({'status': 'approved'})
        else:
            raise UserError('You are not authorized to approve this job.')

    def action_reject_cft(self):
        """Reject the job as a CFT member."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError('Job must be in Pending state to reject.')
        current_user = self.env.user
        approval = self.cft_approval_ids.filtered(lambda a: a.cft_member_id == current_user)
        if approval:
            approval.write({'status': 'rejected'})
        else:
            raise UserError('You are not authorized to reject this job.')

    def action_undo(self):
        """Revert the job position state to 'draft' from 'approved', 'declined', or 'pending'."""
        self.ensure_one()  # Ensures the method runs on a single record
        if self.state in ['approved', 'declined', 'pending']:
            # Clear any related CFT approval records
            if hasattr(self, 'cft_approval_ids'):
                self.cft_approval_ids.unlink()
            # Reset the state to 'draft'
            self.state = 'draft'
        else:
            raise UserError("You can only undo from 'Approved', 'Declined', or 'Pending' states.")

    @api.depends('state')
    def _compute_can_publish(self):
        for record in self:
            record.can_publish = record.state == 'approved'
            
            
    # @api.constrains('website_published', 'state')
    # def _check_publish_state(self):
    #     for record in self:
    #         if record.website_published and record.state != 'approved':
    #             raise ValidationError("You cannot publish a job post that is not approved.")

    @api.constrains('website_published', 'state')
    def _check_publish_state(self):
        # Skip validation during module installation/update
        if self.env.context.get('install_mode') or self.env.context.get('module'):
            return
            
        for record in self:
            if record.website_published and record.state != 'approved':
                raise ValidationError("You cannot publish a job post that is not approved.")