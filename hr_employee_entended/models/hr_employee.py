from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from random import choice
from string import digits


class HrCaste(models.Model):
    _name = "hr.caste"
    _description = "Caste Master"
    _order = "sequence, name"

    name = fields.Char(string="Caste", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)


class Employee(models.Model):
    _inherit = 'hr.employee'
    _order = "employee_code, id"

    joining_date = fields.Date(
        compute='_compute_joining_date',
        string='Joining Date',
        store=True,
        help="Employee joining date"
    )
    
    join_date = fields.Date(string='Join Date', store=True)
    father_name = fields.Char(string='Father Name')
    caste_id = fields.Many2one("hr.caste", string="Caste")
    age = fields.Integer(
        string='Age',
        compute='_compute_age',
        store=True,
        help="Employee age computed from date of birth"
    )

    @api.depends('birthday')
    def _compute_age(self):
        """Compute employee age from birthday."""
        today = date.today()
        for employee in self:
            if employee.birthday:
                delta = relativedelta(today, employee.birthday)
                employee.age = delta.years
            else:
                employee.age = 0

    @api.depends('join_date', 'create_date')
    def _compute_joining_date(self):
        """Compute the joining date based on when the employee record was created."""
        for employee in self:
            if employee.join_date:
                employee.joining_date = employee.join_date
            elif employee.create_date:
                employee.joining_date = employee.create_date.date()
            else:
                employee.joining_date = False

    def action_generate_barcodes_bulk(self):
        """Generate random barcodes for selected employees who don't have one.
        
        This method is designed to be called from a server action in the list view.
        It only generates barcodes for employees that don't already have one,
        preventing overwriting of existing barcodes.
        """
        employees_without_barcode = self.filtered(lambda e: not e.barcode)
        generated_count = 0
        skipped_count = len(self) - len(employees_without_barcode)
        
        for employee in employees_without_barcode:
            employee.barcode = '041' + "".join(choice(digits) for i in range(9))
            generated_count += 1
        
        # Return a notification message
        message = f"Barcodes generated for {generated_count} employee(s)."
        if skipped_count > 0:
            message += f" {skipped_count} employee(s) already had barcodes and were skipped."
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Barcode Generation Complete',
                'message': message,
                'type': 'success' if generated_count > 0 else 'warning',
                'sticky': False,
            }
        }

    def write(self, vals):
        """Override write to synchronize resource_calendar_id with open contracts."""
        # Skip synchronization if already in a contract-employee update loop
        if self.env.context.get('skip_contract_calendar_sync'):
            return super(Employee, self).write(vals)

        # Store old contract_id for leave transfer processing
        old_contract_ids = {employee.id: employee.contract_id for employee in self}

        # Apply the changes to the employee
        res = super(Employee, self).write(vals)

        # Synchronize resource_calendar_id to open contracts
        if 'resource_calendar_id' in vals and not self.env.context.get('calendar_sync_from_contract'):
            new_calendar = vals['resource_calendar_id']
            for employee in self:
                # Check if the new calendar matches the current contract's calendar
                # If so, skip updating contracts to prevent loops from contract updates
                if employee.contract_id and employee.contract_id.resource_calendar_id.id == new_calendar:
                    continue

                # Find all open contracts for the employee
                open_contracts = employee.contract_ids.filtered(lambda c: c.state == 'open')
                if open_contracts:
                    # Update resource_calendar_id for all open contracts
                    open_contracts.with_context(calendar_sync_from_employee=True).sudo().write({
                        'resource_calendar_id': new_calendar
                    })
                    # Ensure contract_id is set to an open contract if not already
                    if employee.contract_id not in open_contracts:
                        employee.with_context(skip_contract_calendar_sync=True).contract_id = open_contracts[0]
                # Update contract_id's calendar if no open contracts exist but contract_id is set
                elif employee.contract_id:
                    employee.contract_id.with_context(calendar_sync_from_employee=True).sudo().write({
                        'resource_calendar_id': new_calendar
                    })

        # Handle contract_id changes for leave transfers
        if vals.get('contract_id') and not self.env.context.get('skip_contract_calendar_sync'):
            for employee in self:
                old_contract = old_contract_ids.get(employee.id)
                if old_contract and old_contract.id != employee.contract_id.id:
                    old_calendar = old_contract.resource_calendar_id
                    new_calendar = employee.contract_id.resource_calendar_id
                    old_calendar.transfer_leaves_to(new_calendar, employee.resource_id)

                # Sync employee's calendar with the new contract
                if employee.resource_calendar_id.id != employee.contract_id.resource_calendar_id.id:
                    employee.with_context(
                        calendar_sync_from_contract=True,
                        skip_contract_calendar_sync=True
                    ).resource_calendar_id = employee.contract_id.resource_calendar_id

        return res

class Contract(models.Model):
    _inherit = 'hr.contract'

    father_name = fields.Char(string='Father Name', related='employee_id.father_name', store=True)
    employee_code = fields.Char(string='Employee Code', related='employee_id.employee_code', store=True)

    @api.depends('employee_id')
    def _compute_employee_contract(self):
        """Override to ensure job_id and department_id are properly computed from employee."""
        super(Contract, self)._compute_employee_contract()
        for contract in self.filtered('employee_id'):
            if contract.employee_id:
                # Ensure job_id is set if not already
                if not contract.job_id and contract.employee_id.job_id:
                    contract.job_id = contract.employee_id.job_id
                # Ensure department_id is set if not already
                if not contract.department_id and contract.employee_id.department_id:
                    contract.department_id = contract.employee_id.department_id
                # Ensure resource_calendar_id is set if not already
                if not contract.resource_calendar_id and contract.employee_id.resource_calendar_id:
                    contract.resource_calendar_id = contract.employee_id.resource_calendar_id
                # Ensure company_id is set if not already
                if not contract.company_id and contract.employee_id.company_id:
                    contract.company_id = contract.employee_id.company_id

    def write(self, vals):
        """Override write to handle contract updates, relying on base behavior for employee sync."""
        # Apply changes via the parent method (includes base hr.contract logic)
        res = super(Contract, self).write(vals)

        # The base hr.contract write method already updates employee.resource_calendar_id
        # for open contracts or specific draft states. Additional sync logic can be minimal.
        # If custom employee sync beyond base behavior is needed, add it here with checks.
        if 'resource_calendar_id' in vals and not self.env.context.get('calendar_sync_from_employee'):
            open_contracts = self.filtered(lambda c: c.state == 'open')
            for contract in open_contracts:
                # Only update employee if this is the current contract and values differ
                if (contract == contract.employee_id.contract_id and
                    contract.employee_id.resource_calendar_id.id != vals['resource_calendar_id']):
                    contract.employee_id.with_context(calendar_sync_from_contract=True).sudo().write({
                        'resource_calendar_id': vals['resource_calendar_id']
                    })

        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure employee fields are properly populated."""
        contracts = super(Contract, self).create(vals_list)
        
        # Populate missing fields from employee after creation
        for contract in contracts:
            if contract.employee_id:
                update_vals = {}
                if not contract.job_id and contract.employee_id.job_id:
                    update_vals['job_id'] = contract.employee_id.job_id.id
                if not contract.department_id and contract.employee_id.department_id:
                    update_vals['department_id'] = contract.employee_id.department_id.id
                if not contract.resource_calendar_id and contract.employee_id.resource_calendar_id:
                    update_vals['resource_calendar_id'] = contract.employee_id.resource_calendar_id.id
                if not contract.company_id and contract.employee_id.company_id:
                    update_vals['company_id'] = contract.employee_id.company_id.id
                
                if update_vals:
                    # Use super().write to avoid triggering custom logic
                    super(Contract, contract).write(update_vals)
        
        return contracts