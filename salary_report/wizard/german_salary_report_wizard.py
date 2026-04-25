from odoo import api, models, fields
from odoo.exceptions import UserError
from io import BytesIO
import base64
from collections import defaultdict
import calendar


class GermanSalaryReportWizard(models.TransientModel):
    _name = "german.salary.report.wizard"
    _description = "German Salary Report"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date", required=True)

    all_employee = fields.Boolean(string="All Employees")
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        domain="[('active', '=', True), ('company_id', '=', company_id)]",
    )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        allowed_employees = self._get_employees_for_company()
        self.employee_ids = self.employee_ids.filtered(lambda emp: emp in allowed_employees)

    def _get_company_scoped_self(self):
        self.ensure_one()
        return self.with_company(self.company_id).with_context(
            allowed_company_ids=[self.company_id.id]
        )

    def _get_employees_for_company(self):
        scoped_self = self._get_company_scoped_self()
        return scoped_self.env["hr.employee"].search([
            ("active", "=", True),
            ("company_id", "=", scoped_self.company_id.id),
        ])

    def _get_selected_employees(self):
        self.ensure_one()
        employees = self._get_employees_for_company()
        if self.all_employee:
            return employees
        if not self.employee_ids:
            raise UserError("Please select employees or tick All Employees.")
        return employees.filtered(lambda emp: emp.id in self.employee_ids.ids)

    def _get_report_employee(self, employee):
        self.ensure_one()
        return employee.sudo().with_company(self.company_id).with_context(
            allowed_company_ids=[self.company_id.id]
        )

    def action_bulk_enable_pf(self):
        scoped_self = self._get_company_scoped_self()
        contracts = scoped_self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('l10n_in_provident_fund', '=', False),
            ('company_id', '=', scoped_self.company_id.id),
        ])

        if not contracts:
            raise UserError(
                "No contracts found to update. All contracts already have PF enabled or no active contracts exist."
            )

        contracts.write({'l10n_in_provident_fund': True})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'PF Enabled Successfully',
                'message': f'Provident Fund enabled for {len(contracts)} active contract(s)',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_generate_excel(self):
        self = self._get_company_scoped_self()
        if self.date_from > self.date_to:
            raise UserError("From Date cannot be greater than To Date")

        employees = self._get_selected_employees()

        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Salary report"

        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

        blue_fill = PatternFill("solid", fgColor="5B9BD5")
        light_blue_fill = PatternFill("solid", fgColor="87CEFA")
        grey_fill = PatternFill("solid", fgColor="D9D9D9")

        header_font = Font(bold=True)
        title_font = Font(size=20, bold=True)

        ws.row_dimensions[1].height = 101
        ws.row_dimensions[2].height = 20
        ws.row_dimensions[3].height = 41

        headers = [
            "Emp Code", "Other Bank Ac No", "ICICI Ac No",
            "PF?", "ESIC?", "UAN", "ESIC NO", "Employee Name",
            "New Gross", "Department Name", "Designation Name",
            "CTC salary", "GROSS SALARY", "Basic", "HRA",
            "Conveyance", "LTA", "Other Allowance", "TOTAL",
            "Bonus", "Payable", "PF SALARY",
            "Paid Days", "Basic", "HRA", "Conveyance", "LTA",
            "Other Allowance", "Bonus", "AREARS", "Earning Sal",
            "PF SALARY", "PF", "ESIC", "PT", "L.W.F",
            "Advance Bank", "Advance cash", "TDS",
            "Total Deduction", "Net Salary", "Remark", "Status"
        ]

        total_cols = len(headers)


        # Get the year and month from date_from
        year = self.date_from.year
        month = self.date_from.month
        # Calculate the number of days in the selected month
        days_in_month = calendar.monthrange(year, month)[1]



        # 🔴 FIX: FETCH COMPANY NAME & ADDRESS FROM COMPANY ID
        company = self.company_id
        partner = company.partner_id

        address_parts = [
            partner.street or "",
            partner.street2 or "",
            partner.city or "",
            partner.state_id.name if partner.state_id else "",
            partner.zip or "",
        ]

        address = ", ".join([p for p in address_parts if p])

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
        ws["A1"] = f"{company.name}\n{address}"
        ws["A1"].font = Font(size=20, bold=True)  # single font (Excel limitation)
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws["A1"].fill = light_blue_fill
        ws.row_dimensions[1].height = 80

        ws.merge_cells("A2:B2")
        ws["A2"] = "Month:"
        ws["A2"].fill = grey_fill
        ws["C2"] = self.date_from.strftime("%B %Y")

        ws.merge_cells("E2:F2")
        ws["E2"] = "Days:"
        ws["E2"].fill = grey_fill
        ws["G2"] = (self.date_to - self.date_from).days + 1

        column_widths = {
            "A": 12, "B": 20, "C": 20, "D": 17, "E": 17,
            "F": 17, "G": 17, "H": 26, "I": 11, "J": 13,
            "K": 13, "L": 11, "M": 12, "N": 10, "O": 10,
            "P": 12, "Q": 10, "R": 11, "S": 11, "T": 10,
            "U": 10, "V": 10, "W": 10, "X": 10, "Y": 10,
            "Z": 10, "AA": 10, "AB": 10, "AC": 10, "AD": 10,
            "AE": 10, "AF": 10, "AG": 10, "AH": 10, "AI": 10,
            "AJ": 10, "AK": 10, "AL": 10, "AM": 10,
            "AN": 10, "AO": 10, "AP": 14, "AQ": 12,
        }

        header_row = 3
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(header_row, col, header)
            cell.font = header_font
            cell.alignment = align_center
            cell.fill = blue_fill
            cell.border = border
            col_letter = get_column_letter(col)
            ws.column_dimensions[col_letter].width = column_widths.get(col_letter, 18)

        payslips = self.env["hr.payslip"].search([
            ("employee_id", "in", employees.ids),
            ("date_from", "<=", self.date_to),
            ("date_to", ">=", self.date_from),
            ("state", "in", ["done", "paid"]),
        ])

        slip_map = defaultdict(list)
        for slip in payslips:
            slip_map[slip.employee_id.id].append(slip)

        row = header_row + 1

        for emp in employees:
            emp_report = self._get_report_employee(emp)
            emp_slips = slip_map.get(emp.id, [])

            paid_days = 0.0
            for slip in emp_slips:
                for wd in slip.worked_days_line_ids:
                    if wd.is_paid:
                        paid_days += wd.number_of_days

            structure_lines = emp_report.contract_id.salary_structure_line_ids if emp_report.contract_id else self.env[
                'hr.contract.salary.structure.line']

            def get_amt(code):
                lines = structure_lines.filtered(lambda l: l.code == code)
                return sum(lines.mapped('amount_monthly')) if lines else 0.0

            basic = get_amt('BASIC')
            hra = get_amt('HRA')
            conveyance = get_amt('CONV')
            lta = get_amt('LTA')
            other_allowance = get_amt('OTHER_ALW')

            gross = get_amt('TOTAL')
            bonus = get_amt('BONUS')
            payable = get_amt('PAYABLE')
            pf_salary = get_amt('PF_SALARY')
            net = get_amt('INHAND')

            pf = round(pf_salary * 0.12, 0) if pf_salary else 0.0
            pf_flag = "Yes" if emp_report.contract_id and emp_report.contract_id.is_pf_deduct else "No"

            esic = 0.0  # ESIC not defined in structure yet



            other_bank_ac = ""
            icici_ac = ""
            if emp_report.bank_account_id and emp_report.bank_account_id.bank_id:
                bank_name = (emp_report.bank_account_id.bank_id.name or "").upper()
                acc_no = emp_report.bank_account_id.acc_number or ""
                if "ICICI" in bank_name:
                    icici_ac = acc_no
                else:
                    other_bank_ac = acc_no

            data = [
                emp_report.employee_code or "",
                other_bank_ac,
                icici_ac,
                pf_flag,
                "Yes" if esic else "No",
                emp_report.l10n_in_uan or "Not Available",
                emp_report.l10n_in_esic_number or "Not Available",
                emp_report.name,
                gross,
                emp_report.department_id.name if emp_report.department_id else "",
                emp_report.job_id.name if emp_report.job_id else "",
                emp_report.contract_id.final_yearly_costs if emp_report.contract_id else 0,
                gross,
                basic,
                hra,
                conveyance,
                lta,
                other_allowance,
                basic + hra + conveyance + lta + other_allowance,
                bonus,
                net,
                pf_salary,
            ]

            final_row_data = data + [""] * (total_cols - len(data))

            for col, value in enumerate(final_row_data, start=1):
                ws.cell(row, col, value).border = border

            #  USE DYNAMIC DAYS IN MONTH
            ws[f"W{row}"] = paid_days
            ws[f"X{row}"] = f"=ROUND(N{row}*W{row}/{days_in_month},0)"
            ws[f"Y{row}"] = f"=ROUND(O{row}*W{row}/{days_in_month},0)"
            ws[f"Z{row}"] = f"=ROUND(P{row}*W{row}/{days_in_month},0)"
            ws[f"AA{row}"] = f"=ROUND(Q{row}*W{row}/{days_in_month},0)"
            ws[f"AB{row}"] = f"=ROUND(R{row}*W{row}/{days_in_month},0)"
            ws[f"AC{row}"] = f"=ROUND(T{row}*W{row}/{days_in_month},0)"


            ws[f"AD{row}"] = ""
            ws[f"AE{row}"] = f"=SUM(X{row}:AD{row})"
            ws[f"AF{row}"] = (
                f'=IF(D{row}="No",0,IF(D{row}="Yes",'
                f'IF((X{row}+Z{row}+AA{row}+AB{row})>=15000,15000,'
                f'ROUND((X{row}+Z{row}+AA{row}+AB{row}),0)),0))'
            )

            ws[f"AG{row}"] = f"=ROUND(AF{row}*12%,0)"
            ws[f"AH{row}"] = f"=IF((S{row})>21001,0,ROUNDUP((AE{row})*0.75/100,0))"
            ws[f"AI{row}"] = f"=IF((AE{row})>12001,200,0)"
            ws[f"AL{row}"] = f"=IFERROR(VLOOKUP(A{row},ADVANCE!$A$4:$E$309,5,0),0)"
            ws[f"AN{row}"] = f"=AG{row}+AH{row}+AI{row}+AL{row}+AK{row}+AJ{row}+AM{row}"
            ws[f"AO{row}"] = f"=AE{row}-AN{row}"
            ws[f"AP{row}"] = ""
            ws[f"AQ{row}"] = ""

            row += 1

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        attachment = self.env["ir.attachment"].create({
            "name": f"German_Salary_Report_{self.date_from.strftime('%B %Y')}.xlsx",
            "type": "binary",
            "datas": base64.b64encode(output.read()),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "company_id": self.company_id.id,
            "res_model": self._name,
            "res_id": self.id,
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }
