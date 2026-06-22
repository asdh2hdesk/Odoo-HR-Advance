from odoo import models, fields

class HrEmployeeRejoinHistory(models.Model):
    _name = 'hr.employee.rejoin.history'
    _description = 'Employee Rejoining History'
    _order = 'rejoin_date desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade', index=True)
    previous_employee_id = fields.Many2one('hr.employee', string='Previous Employee', ondelete='set null', index=True)
    old_employee_code = fields.Char(string='Old Employee Code', help="Code of the archived employee record")
    new_employee_code = fields.Char(string='New Employee Code', help="Code generated for the new rejoining employee")
    previous_join_date = fields.Date(string='Previous Joining Date')
    previous_exit_date = fields.Date(string='Previous Exit Date')
    rejoin_date = fields.Date(string='Rejoining Date', required=True, default=fields.Date.context_today)
    
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id', store=True)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id', store=True)

    # Standard audit fields: create_uid and create_date are already handled by Odoo automatically. 
    # To display them we can use them directly or rename them explicitly if needed.
