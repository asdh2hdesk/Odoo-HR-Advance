from odoo import models
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import base64

class HrCustomFormLeaveApplication(models.Model):
    _inherit = "hr.custom.form.leave_application"
    
    def action_generate_excel_report(self):
        self.ensure_one()

        doc = Document()

        # ===== Common Font =====
        style = doc.styles['Normal']
        style.font.name = 'Calibri'
        style.font.size = Pt(11)

        # Helper Function for SAME spacing
        def add_p(text, bold=False, center=False):
            p = doc.add_paragraph(text)
            p.paragraph_format.space_after = Pt(20)
            p.paragraph_format.space_before = Pt(0)
            if bold:
                for r in p.runs:
                    r.bold = True
            if center:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            return p


        # ===== Company Name =====    
        add_p("GERMAN TMT PVT LTD", bold=True, center=True)
        add_p("Leave Application Form\n", bold=True, center=True)


        # ===== Basic Details =====
        add_p(f"Department: {self.department_id.name or '___________________'}")
        add_p(f"Name: {self.employee_id.name or '______________________________'}")
        add_p(f"Designation: {self.employee_id.job_id.name or '_________________'}")


        # ===== Leave Details =====
        add_p(f"Reason of Leave: {self.leave_reason or '____________________________________________'}")

        add_p(
            f"Days: {self.leave_days or '_____'}        "
            f"From Date: {self.leave_from.strftime('%d-%m-%Y') if self.leave_from else '___________'}        "
            f"To Date: {self.leave_to.strftime('%d-%m-%Y') if self.leave_to else '___________'}"
        )
        add_p("Applicant's Signature: ____________________")
        add_p(f"Manager Remarks: {self.manager_remarks or '____________________________'}")
        add_p(f"Approved / Not Approved: {self.approval_status or '____________________________'}")


        # ===== Signature =====
        add_p("G.M. Signature: _____________        Checked By: ______________")
        add_p("H.R. Signature: _____________        Security Supervisor: ______________")


        # ===== Contact Details =====
        add_p(f"Permanent Address: {self.permanent_address or '____________________________'}")
        add_p(f"Mobile No.: {self.contact_number or '____________________'}")


        # ===== Save to Memory =====
        buffer = io.BytesIO()
        doc.save(buffer)

        filename = (
            f"Leave Application - {self.employee_id.name or ''}({self.employee_id.employee_code or ''}).docx"
            if self.employee_id.employee_code
            else f"Leave Application - {self.employee_id.name or ''}.docx"
        )
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(buffer.getvalue()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'res_model': self._name,
            'res_id': self.id,
        })

        # ===== Download =====
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
