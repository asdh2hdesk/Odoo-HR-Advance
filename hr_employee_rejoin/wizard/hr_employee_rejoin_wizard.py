from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrEmployeeRejoinWizard(models.TransientModel):
    _name = 'hr.employee.rejoin.wizard'
    _description = 'Rejoin Employee Wizard'

    # Step 1: Search Employee
    search_keyword = fields.Char(string="Search Keyword", help="Search by Name, PAN, Aadhaar or Employee Code")
    previous_employee_id = fields.Many2one(
        'hr.employee', 
        string='Select Archived Employee', 
        domain="[('active', '=', False)]"
    )

    # Step 2: Employee Details (Preview)
    name = fields.Char(string='Name', related='previous_employee_id.name', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', related='previous_employee_id.department_id', readonly=True)
    job_id = fields.Many2one('hr.job', string='Job Position', related='previous_employee_id.job_id', readonly=True)
    old_employee_code = fields.Char(string='Old Employee Code', readonly=True)
    l10n_in_pan = fields.Char(string='PAN', readonly=True)
    identification_id = fields.Char(string='AADHAAR / ID', readonly=True)

    previous_join_date = fields.Date(string='Previous Joining Date')
    previous_exit_date = fields.Date(string='Previous Exit Date')
    
    # Target New details
    rejoin_date = fields.Date(string="Rejoining Date", default=fields.Date.context_today, required=True)

    @api.onchange('search_keyword')
    def _onchange_search_keyword(self):
        if self.search_keyword:
            domain = [
                ('active', '=', False),
                '|', ('name', 'ilike', self.search_keyword),
                '|', ('l10n_in_pan', 'ilike', self.search_keyword),
                '|', ('identification_id', 'ilike', self.search_keyword),
                '|', ('employee_code', 'ilike', self.search_keyword),
                     ('mobile_phone', 'ilike', self.search_keyword)
            ]
            # Try to safely inject other aadhaar variants in domain if we aren't completely sure 
            # Odoo domains ignore non-existing fields if we structure carefully, but here we just try identification_id
            res = self.env['hr.employee'].with_context(active_test=False).search(domain, limit=10)
            return {'domain': {'previous_employee_id': [('id', 'in', res.ids)]}}
        else:
            return {'domain': {'previous_employee_id': [('active', '=', False)]}}

    @api.onchange('previous_employee_id')
    def _onchange_previous_employee_id(self):
        if self.previous_employee_id:
            emp = self.previous_employee_id
            self.old_employee_code = getattr(emp, 'employee_code', False)
            self.l10n_in_pan = getattr(emp, 'l10n_in_pan', False)
            self.identification_id = getattr(emp, 'identification_id', False)
            self.previous_join_date = getattr(emp, 'first_contract_date', False) or getattr(emp, 'create_date', False)
            # Find exit date either from contract or departure_date
            self.previous_exit_date = getattr(emp, 'departure_date', False)

    def action_create_rejoining_employee(self):
        self.ensure_one()
        if not self.previous_employee_id:
            raise UserError(_("Please select an archived employee to proceed."))

        emp = self.previous_employee_id

        # Settings
        IrConfig = self.env['ir.config_parameter'].sudo()
        auto_generate_code = IrConfig.get_param('hr_employee_rejoin.auto_generate_employee_code', 'True') == 'True'
        copy_docs = IrConfig.get_param('hr_employee_rejoin.copy_employee_documents', 'True') == 'True'
        copy_skills = IrConfig.get_param('hr_employee_rejoin.copy_employee_skills', 'True') == 'True'
        copy_education = IrConfig.get_param('hr_employee_rejoin.copy_employee_education', 'True') == 'True'

        # Ensure we don't automatically duplicate unique codes if doing so natively
        copy_dict = {
            'is_rejoining_employee': True,
            'previous_employee_id': emp.id,
            'active': True,
            # Resetting some lifecycle dates if natively exist
            'departure_date': False,
            'departure_reason_id': False,
            'departure_description': False,
            'first_contract_date': self.rejoin_date
        }

        # Clear employee code so create() handles sequence natively if auto_generate_code is True.
        if auto_generate_code:
            copy_dict['employee_code'] = False
            # Check barcode and other things.
            copy_dict['barcode'] = False

        # Actual Copy
        new_emp = emp.copy(default=copy_dict)
        
        # If the environment didn't automatically fill code (because sequence is manual or named differently)
        if auto_generate_code and getattr(new_emp, 'employee_code', None) == False:
            seq = self.env['ir.sequence'].next_by_code('hr.employee') or self.env['ir.sequence'].next_by_code('employee_code')
            if seq:
                new_emp.write({'employee_code': seq})

        # Create History Record
        self.env['hr.employee.rejoin.history'].create({
            'employee_id': new_emp.id,
            'previous_employee_id': emp.id,
            'old_employee_code': self.old_employee_code,
            'new_employee_code': getattr(new_emp, 'employee_code', ''),
            'previous_join_date': self.previous_join_date,
            'previous_exit_date': self.previous_exit_date,
            'rejoin_date': self.rejoin_date
        })

        # The copy method handles one2many if copy=True. 
        # If skills and documents aren't copied due to copy=False natively, we must do it manually:
        if copy_skills and hasattr(emp, 'employee_skill_ids'):
            for skill in getattr(emp, 'employee_skill_ids', []):
                skill.copy({'employee_id': new_emp.id})
        
        if copy_education and hasattr(emp, 'resume_line_ids'):
            for resume in getattr(emp, 'resume_line_ids', []).filtered(lambda r: r.line_type_id.name == 'Education'):
                resume.copy({'employee_id': new_emp.id})

        # Post a message in chatter
        audit_msg = _(
            "Rejoining Employee Created.<br/>"
            "Linked to Former Record: %s<br/>"
            "Old Code: %s<br/>"
            "New Code: %s"
        ) % (
            emp.name,
            self.old_employee_code or 'N/A',
            getattr(new_emp, 'employee_code', 'N/A')
        )
        new_emp.message_post(body=audit_msg)

        # Redirect to the new employee form
        return {
            'name': _('Employee'),
            'view_mode': 'form',
            'res_model': 'hr.employee',
            'res_id': new_emp.id,
            'type': 'ir.actions.act_window',
            'target': 'current'
        }
