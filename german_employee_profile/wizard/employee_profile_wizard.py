# -*- coding: utf-8 -*-
import base64
from urllib.parse import quote

from odoo import models, fields, tools, _
from odoo.exceptions import UserError
from .docx_generator import build_employee_profile_docx


class EmployeeProfileWizard(models.TransientModel):
    _name = 'employee.profile.wizard'
    _description = 'Generate Employee Profile DOCX'

    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
        required=True,
        default=lambda self: self._default_employee()
    )
    docx_file = fields.Binary(string='DOCX File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    def _default_employee(self):
        if self.env.context.get('active_model') == 'hr.employee':
            return self.env.context.get('active_id')
        return False

    def action_generate_docx(self):
        """Generate the Employee Profile DOCX file."""
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            raise UserError(_('Please select an employee.'))

        # Collect all employee data
        data = self._collect_employee_data(emp)

        # Generate DOCX from the collected employee data
        docx_bytes = self._generate_docx(data)

        # Store on wizard
        self.write({
            'docx_file': base64.b64encode(docx_bytes),
            'file_name': f'Employee_Profile_{emp.name.replace(" ", "_")}.docx',
        })

        url = (
            "/web/content"
            "?model=employee.profile.wizard"
            "&id=%s"
            "&field=docx_file"
            "&filename_field=file_name"
            "&download=true"
            "&filename=%s"
        ) % (self.id, quote(self.file_name or "employee_profile.docx"))

        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    def _get_selection_label(self, record, field_name, value):
        """Return the translated label for a selection field safely."""
        if not value or field_name not in record._fields:
            return ''

        field = record._fields[field_name]
        try:
            selection = field._description_selection(record.env)
        except Exception:
            raw_selection = field.selection(record) if callable(field.selection) else field.selection
            selection = [
                item for item in (raw_selection or [])
                if isinstance(item, (list, tuple)) and len(item) >= 2
            ]
        return dict(selection).get(value, '')

    def _format_date(self, value):
        """Format dates as DD-MM-YYYY."""
        if not value:
            return ''
        if isinstance(value, str):
            value = fields.Date.to_date(value)
        return value.strftime('%d-%m-%Y') if value else ''

    def _format_datetime_as_date(self, value):
        """Format datetime/date values as DD-MM-YYYY in user timezone."""
        if not value:
            return ''
        if isinstance(value, str):
            value = fields.Datetime.to_datetime(value)
        if hasattr(value, 'hour'):
            value = fields.Datetime.context_timestamp(self, value)
        return value.strftime('%d-%m-%Y') if value else ''

    def _get_first_field_value(self, record, field_names):
        """Return the first available non-empty field value from the record."""
        for field_name in field_names:
            if field_name in record._fields:
                value = record[field_name]
                if value:
                    return value
        return False

    def _collect_employee_data(self, emp):
        """Collect all relevant employee data into a dict."""

        def val(v):
            return v if v else '#N/A'

        # Qualification lines from hr.employee main fields
        qualifications = []
        exam_str = ''
        if emp.certificate:
            exam_str += dict(emp._fields['certificate'].selection).get(emp.certificate, emp.certificate)
        if emp.study_field:
            if exam_str:
                exam_str += f" - {emp.study_field}"
            else:
                exam_str = emp.study_field

        if exam_str or getattr(emp, 'year_of_passing', False) or emp.study_school:
            qualifications.append({
                'exam': val(exam_str),
                'year': val(getattr(emp, 'year_of_passing', '')),
                'board': val(emp.study_school),
                'percentage': '#N/A',
            })

        # Append from hr.resume.line as well
        resume_lines = emp.resume_line_ids.filtered(
            lambda r: r.line_type_id.name in ('Education', 'education', 'Qualification')
        )
        for line in resume_lines:
            qualifications.append({
                'exam': val(line.name),
                'year': val(str(line.date_end.year) if line.date_end else ''),
                'board': val(line.description),
                'percentage': '#N/A',
            })
        if not qualifications:
            qualifications = [{'exam': '#N/A', 'year': '#N/A', 'board': '#N/A', 'percentage': '#N/A'}]

        # Experience lines
        experiences = []
        exp_lines = emp.resume_line_ids.filtered(
            lambda r: r.line_type_id.name in ('Experience', 'experience', 'Work Experience')
        )
        for line in exp_lines:
            period = ''
            if line.date_start:
                period = str(line.date_start.year)
            if line.date_end:
                period += f' - {line.date_end.year}'
            experiences.append({
                'company': val(line.name),
                'designation': val(tools.html2plaintext(line.description) if line.description else ''),
                'period': val(period),
                'reason': '-',
            })
        while len(experiences) < 2:
            experiences.append({'company': '#N/A', 'designation': '#N/A', 'period': '#N/A', 'reason': '-'})

        # Family contacts – use hr.employee.relative if available, else empty
        family_contacts = [
            {'name': '#N/A', 'contact': '#N/A', 'relation': '#N/A', 'address': '#N/A'},
            {'name': '#N/A', 'contact': '#N/A', 'relation': '#N/A', 'address': '#N/A'},
        ]

        # Emergency contact
        emergency = [
            {
                'name': val(emp.emergency_contact),
                'contact': val(emp.emergency_phone),
                'relation': val(emp.sudo().l10n_in_relationship if hasattr(emp.sudo(), 'l10n_in_relationship') and emp.sudo().l10n_in_relationship else '#N/A'),
                'address': val(emp.sudo().emergency_address if hasattr(emp.sudo(), 'emergency_address') and emp.sudo().emergency_address else '#N/A'),
            },
            {
                'name': val(emp.sudo().emergency_contact2 if hasattr(emp.sudo(), 'emergency_contact2') and emp.sudo().emergency_contact2 else '#N/A'),
                'contact': val(emp.sudo().emergency_phone2 if hasattr(emp.sudo(), 'emergency_phone2') and emp.sudo().emergency_phone2 else '#N/A'),
                'relation': val(emp.sudo().emergency_relation2 if hasattr(emp.sudo(), 'emergency_relation2') and emp.sudo().emergency_relation2 else '#N/A'),
                'address': val(emp.sudo().emergency_address2 if hasattr(emp.sudo(), 'emergency_address2') and emp.sudo().emergency_address2 else '#N/A'),
            }
        ]
        emp_sudo = emp.sudo()
        joining_date = self._get_first_field_value(
            emp_sudo,
            ['date_start', 'joining_date', 'join_date', 'first_contract_date', 'date_of_joining'],
        )
        message_model = self.env['mail.message'].sudo()
        tracked_messages = message_model.search([
            ('model', '=', 'hr.employee'),
            ('res_id', '=', emp.id),
            ('tracking_value_ids', '!=', False),
        ], order='date desc, id desc')
        thread_messages = tracked_messages or message_model.search([
            ('model', '=', 'hr.employee'),
            ('res_id', '=', emp.id),
        ], order='date desc, id desc')
        latest_thread_message = thread_messages[:1]
        revision_no = max(len(thread_messages) - 1, 0)
        revision_date = (
            latest_thread_message.date
            or emp.write_date
            or emp.create_date
        )

        data = {
            'employee_code': val(emp_sudo.employee_code if hasattr(emp_sudo, 'employee_code') else emp.barcode or emp.employee_id),
            'date': val(self._format_date(joining_date)),
            'department': val(emp.department_id.name if emp.department_id else ''),
            'post': val(emp.job_id.name if emp.job_id else ''),
            'blood_group': val(emp_sudo.blood_group if hasattr(emp_sudo, 'blood_group') and emp_sudo.blood_group else (emp_sudo.blood_type if hasattr(emp_sudo, 'blood_type') else '')),
            'employee_photo': (
                getattr(emp_sudo, 'image_1920', False)
                or getattr(emp_sudo, 'avatar_1920', False)
                or False
            ),
            'company_name': val((emp.company_id or self.env.company).name if (emp.company_id or self.env.company) else ''),
            'company_logo': (
                getattr(emp.company_id or self.env.company, 'logo', False)
                or getattr(emp.company_id or self.env.company, 'image_1920', False)
                or getattr(emp.company_id or self.env.company, 'logo_web', False)
                or False
            ),
            'revision_label': 'REV/%02d/%s' % (
                revision_no,
                self._format_datetime_as_date(revision_date),
            ),
            # Personal details
            'name': val(emp.name),
            'father_name': val(emp_sudo.father_name if hasattr(emp_sudo, 'father_name') else '#N/A'),
            'mother_name': val(emp_sudo.mother_name if hasattr(emp_sudo, 'mother_name') else '#N/A'),
            'address': val(emp_sudo.private_street or ''),
            'contact': val(emp_sudo.private_phone or emp.mobile_phone or ''),
            'email': val(emp_sudo.private_email or emp.work_email or ''),
            'language': val(emp_sudo.language if hasattr(emp_sudo, 'language') else '#N/A'),
            'birth_date': val(self._format_date(emp_sudo.birthday)),
            'gender': val(self._get_selection_label(emp, 'gender', emp.gender)),
            'marital': val(self._get_selection_label(emp_sudo, 'marital', emp_sudo.marital)),
            'height': val(str(emp_sudo.height) if hasattr(emp_sudo, 'height') and emp_sudo.height else '#N/A'),
            'bank_account': val(emp_sudo.employee_bank_account if hasattr(emp_sudo, 'employee_bank_account') and emp_sudo.employee_bank_account else (emp_sudo.bank_account_id.acc_number if emp_sudo.bank_account_id else '')),
            'food_preference': val(emp_sudo.food_preference if hasattr(emp_sudo, 'food_preference') else '#N/A'),
            'aadhaar': val(emp_sudo.identification_id if hasattr(emp_sudo, 'identification_id') and emp_sudo.identification_id else '#N/A'),
            'pan': val(emp_sudo.pan_no if hasattr(emp_sudo, 'pan_no') else emp_sudo.pan if hasattr(emp_sudo, 'pan') else '#N/A'),
            'nationality': val(emp_sudo.country_id.name if emp_sudo.country_id else ''),
            'weight': val(str(emp_sudo.weight) if hasattr(emp_sudo, 'weight') and emp_sudo.weight else '#N/A'),
            'uan': val(emp_sudo.uan if hasattr(emp_sudo, 'uan') else '#N/A'),
            # Sections
            'qualifications': qualifications,
            'experiences': experiences,
            'family_contacts': family_contacts,
            'emergency': emergency,
            'last_salary': '#N/A',
            'expected_salary': '#N/A',
            'job_skill': val(', '.join(emp.employee_skill_ids.mapped('skill_id.name')) if emp.employee_skill_ids else ''),
            # Interview section
            'interviewer': '#N/A',
            'selected_rejected': '#N/A',
            'dept_interview': val(emp.department_id.name if emp.department_id else ''),
            'date_joining': val(self._format_date(joining_date)),
            'final_salary': '#N/A',
            'selection_date': '#N/A',
            'reference': '#N/A',
        }
        return data

    def _generate_docx(self, data):
        """Generate DOCX bytes with the local Python generator."""
        try:
            return build_employee_profile_docx(data)
        except Exception as exc:
            raise UserError(_('DOCX generation failed:\n%s') % exc)
