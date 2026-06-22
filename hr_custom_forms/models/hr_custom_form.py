from odoo import _, api, fields, models

# Default HTML content for Labour Colony Agreement
LABOUR_COLONY_AGREEMENT_DEFAULT_HTML = """
<div style="font-family: 'Noto Sans Devanagari', Arial, sans-serif; font-size: 12pt; line-height: 1.8;">
    <p style="text-align: justify;">
        कम्पनीके सभी कर्मचारी एवं मजदूर को सूचित किया जाता है की लेबर कोलोनी/ आवास में आप सभी को अनुशाशन बनाकर रखना है और निन्मलिखित बातो का जिम्मेदारीपूर्ण ध्यान रखना है।
    </p>
    <ol style="text-align: justify;">
        <li>लेबर कॉलोनी/ आवास में साफ सफाई का सम्पूर्ण ध्यान रखना है।</li>
        <li>कूड़ा या अन्य किसीभी प्रकार का कचरा सिर्फ और सिर्फ कूड़े दान में ही डालना है।कूड़ेदान का उपयोग अवश्य करना है ओर अन्य साथी कोभी इसका प्रयोग करने हेतु प्रेरित करना है।</li>
        <li>ऊँची आवाज़ में बात नहीं करना हे व् किसी अन्यसह-कर्मचारी के काममें या आराममें दखल न पहुंचे उस बातका ध्यान रखना है।</li>
        <li>गुजरात राज्य में दारूबन्धी है।दारू पीना, रखनायाबेचनागैर क़ानूनी है।इस बात को ध्यान में रखते हुए लेबर कॉलोनीमें कोईभी कर्मचारी या मज़दूर या अन्यकोई भी बहार के व्यक्तिको दारूलाना या दारुका का सेवन न करने की कड़ी चेतावनी दिजाती है। अगर कोई भी कर्मचारी या मजदूर एसे किसीभी प्रकार के नशीले पदार्थो का सेवन करता हुआपकड़ा जाएगा तो उसके खिलाफ सख्त से सख्त कार्यवाही की जाएगी।</li>
        <li>कोई भी कर्मचारी या मज़दूरलेबर कॉलोनी में कोई भी अवेध काम करेगा तो उसकी सम्पूर्ण जवाबदारी उस व्यक्ति की खुद की रहेगी। इसके लिए कम्पनी की कोई भी ज़िम्मेदारी नहींरहेगी।</li>
        <li>दारूया अन्य किसीभी तरह के नशीले पदार्थ के सेवनके कारणअगर किसीभी कर्मचारी या मज़दूर को कोईभी बीमारी होती हे याउसके साथ कोई भी हादसा होता है, तो उसकी सम्पूर्ण जिम्मेद्दारी उसकर्मचारी या मज़दूरकी अपनी खुद की रहेगी।</li>
        <li>ऊपरदी गई सभी सूचनाओ का जिम्मेदारी पूर्वक पालन करे।</li>
    </ol>
</div>
"""


class HrCustomFormBase(models.AbstractModel):
    _name = "hr.custom.form.base"
    _description = "HR Custom Form Base"
    _abstract = True

    _sequence_code = False

    name = fields.Char(
        string="Document Reference",
        required=True,
        default=lambda self: _("New"),
        copy=False,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        check_company=True,
    )
    employee_code = fields.Char(string="Employee Code")
    father_name = fields.Char(string="Father Name")
    joining_date = fields.Date(string="Joining Date")
    form_date = fields.Date(
        string="Document Date",
        required=True,
        default=fields.Date.context_today,
    )
    department_id = fields.Many2one("hr.department", string="Department")
    job_id = fields.Many2one("hr.job", string="Job Position")

    def _prepare_employee_related_vals(self, vals):
        employee_id = vals.get("employee_id")
        if not employee_id:
            return

        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return

        related_values = {}
        if not vals.get("employee_code") and employee.employee_code:
            related_values["employee_code"] = employee.employee_code
        if not vals.get("father_name") and employee.father_name:
            related_values["father_name"] = employee.father_name
        if not vals.get("joining_date") and (employee.joining_date or employee.join_date):
            related_values["joining_date"] = employee.joining_date or employee.join_date
        if not vals.get("department_id") and employee.department_id:
            related_values["department_id"] = employee.department_id.id
        if not vals.get("job_id") and employee.job_id:
            related_values["job_id"] = employee.job_id.id
        if not vals.get("company_id") and employee.company_id:
            related_values["company_id"] = employee.company_id.id

        vals.update({key: value for key, value in related_values.items() if value})

    def _get_sequence_code(self):
        return getattr(self, "_sequence_code", False) or self._name

    def _next_sequence(self, company_id):
        seq_code = self._get_sequence_code()
        seq_env = self.env["ir.sequence"]
        if company_id:
            company = self.env["res.company"].browse(company_id)
            seq_env = seq_env.with_company(company)
        return seq_env.next_by_code(seq_code) or _("New")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._prepare_employee_related_vals(vals)
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") in ("New", _("New")):
                vals["name"] = self._next_sequence(vals.get("company_id"))
        return super().create(vals_list)

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.employee_code = employee.employee_code or False
            record.father_name = employee.father_name or False
            record.joining_date = employee.joining_date or employee.join_date or False
            record.department_id = employee.department_id or False
            record.job_id = employee.job_id or False
            record.company_id = employee.company_id or record.company_id

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for record in self:
            if record.employee_id and record.employee_id.company_id != record.company_id:
                record.employee_id = False


class HrCustomFormEr1(models.Model):
    _name = "hr.custom.form.er1"
    _description = "Exchange Return (ER1)"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.er1"

    quarter_ended = fields.Char(
        string="Quarter Ended",
        required=True,
    )
    employer_name = fields.Char(string="Name of Employer")
    employer_address = fields.Text(string="Address of Employer")
    office_type = fields.Selection(
        [   
            ("none", " "),
            ("head", "Head Office"),
            ("branch", "Branch Office"),
        ],
        string="Office Type",
        # default="head",
        required=True,
    )
    business_nature = fields.Char(string="Nature of Business / Principal Activity")
    shortage_open_count = fields.Char(string="Number of Unfilled Vacancies / Posts")
    employment_line_ids = fields.One2many(
        "hr.custom.form.er1.employment.line",
        "form_id",
        string="Employment Details",
    )
    vacancy_line_ids = fields.One2many(
        "hr.custom.form.er1.vacancy.line",
        "form_id",
        string="Vacancies",
    )
    shortage_line_ids = fields.One2many(
        "hr.custom.form.er1.shortage.line",
        "form_id",
        string="Manpower Shortages",
    )

    def _set_default_employer_details(self, vals):
        company_id = vals.get("company_id") or self.env.company.id
        if not company_id:
            return
        company = self.env["res.company"].browse(company_id)
        if not company:
            return
        if not vals.get("employer_name") and company.name:
            vals["employer_name"] = company.name
        if not vals.get("employer_address") and company.partner_id:
            vals["employer_address"] = company.partner_id._display_address()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._set_default_employer_details(vals)
        return super().create(vals_list)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        super()._onchange_company_id()
        for record in self:
            company = record.company_id
            if not company:
                continue
            if not record.employer_name and company.name:
                record.employer_name = company.name
            if not record.employer_address and company.partner_id:
                record.employer_address = company.partner_id._display_address()


class HrCustomFormD(models.Model):
    _name = "hr.custom.form.formd"
    _description = "Form D"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.formd"

    formd_date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    month_year = fields.Char(string="Month and Year")
    total_workers = fields.Integer(string="Total Number of Workers")
    company_address = fields.Text(string="Company Address", compute="_compute_company_address", store=True)
    line_ids = fields.One2many(
        "hr.custom.form.formd.line",
        "form_id",
        string="Wage Lines",
    )

    @api.depends("company_id")
    def _compute_company_address(self):
        for record in self:
            if record.company_id and record.company_id.partner_id:
                record.company_address = record.company_id.partner_id._display_address()
            else:
                record.company_address = False

    @api.onchange('company_id')
    def _onchange_company_id(self):
        super()._onchange_company_id()
        for record in self:
            if record.company_id:
                employees = self.env['hr.employee'].search([('company_id', '=', record.company_id.id)])
                record.total_workers = len(employees)
                
                from collections import defaultdict
                job_counts = defaultdict(lambda: {'men': 0, 'women': 0, 'basic': 0.0})
                for emp in employees:
                    job_id = emp.job_id.id if emp.job_id else False
                    contract = emp.contract_id if hasattr(emp, 'contract_id') else False
                    wage = contract.wage if contract else 0.0
                    
                    if emp.gender == 'male':
                        job_counts[job_id]['men'] += 1
                    else:
                        job_counts[job_id]['women'] += 1
                    job_counts[job_id]['basic'] += wage
                
                lines = [(5, 0, 0)] # clear existing
                for job, counts in job_counts.items():
                    total_people = counts['men'] + counts['women']
                    avg_basic = counts['basic'] / total_people if total_people > 0 else 0.0
                    lines.append((0, 0, {
                        'category_id': job,
                        'men_employed': counts['men'],
                        'women_employed': counts['women'],
                        'basic_wages': avg_basic,
                    }))
                record.line_ids = lines


class HrCustomFormMinimumWageNotice(models.Model):
    _name = "hr.custom.form.mw_notice"
    _description = "Minimum Wages Registers"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.mw_notice"

    company_address = fields.Text(string="Company Address", compute="_compute_company_address", store=True)
    notice_line_ids = fields.One2many(
        "hr.custom.form.mw.notice.line",
        "notice_id",
        string="Minimum Wages Entries",
    )

    @api.depends("company_id")
    def _compute_company_address(self):
        for record in self:
            if record.company_id and record.company_id.partner_id:
                record.company_address = record.company_id.partner_id._display_address()
            else:
                record.company_address = False


class HrCustomFormTwo(models.Model):
    _name = "hr.custom.form.form2"
    _description = "Form 2 (Revised)"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.form2"

    father_husband_name = fields.Char(string="Father's / Husband Name")
    spouse_name = fields.Char(string="Spouse Name")
    date_of_birth = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    marital_status = fields.Selection(
        [
            ("single", "Single"),
            ("married", "Married"),
            ("widowed", "Widowed"),
            ("divorced", "Divorced"),
        ],
        string="Marital Status",
    )
    account_number = fields.Char(string="Account Number")
    permanent_address = fields.Text(string="Permanent Address")
    temporary_address = fields.Text(string="Temporary Address")
    date_of_joining = fields.Date(string="Date of Joining")
    part_a_line_ids = fields.One2many(
        "hr.custom.form.form2.part.a.line",
        "form_id",
        string="Part A Nominees",
    )
    part_b_family_line_ids = fields.One2many(
        "hr.custom.form.form2.part.b.family.line",
        "form_id",
        string="Part B Family Members",
    )
    part_b_nominee_line_ids = fields.One2many(
        "hr.custom.form.form2.part.b.nominee.line",
        "form_id",
        string="Part B Nominees",
    )
    eps_part_b_date = fields.Date(string="Part B (EPS) Date")

    def _prepare_employee_related_vals(self, vals):
        super()._prepare_employee_related_vals(vals)
        employee_id = vals.get("employee_id")
        if not employee_id:
            return
        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return
        if not vals.get("father_husband_name"):
            vals["father_husband_name"] = employee.father_name or False
        if not vals.get("date_of_birth"):
            vals["date_of_birth"] = employee.birthday or False
        if not vals.get("gender") and employee.gender:
            vals["gender"] = employee.gender
        if not vals.get("marital_status") and employee.marital:
            vals["marital_status"] = employee.marital
        if not vals.get("date_of_joining"):
            vals["date_of_joining"] = employee.joining_date or employee.join_date or False
        if not vals.get("permanent_address") and employee.private_street:
            vals["permanent_address"] = employee.private_street
        if not vals.get("temporary_address") and employee.address_id:
            vals["temporary_address"] = employee.address_id._display_address()
        if hasattr(employee, "bank_account_id") and employee.bank_account_id:
            if not vals.get("account_number"):
                vals["account_number"] = employee.bank_account_id.acc_number or False
        if not vals.get("spouse_name"):
            spouse = employee.family_ids.filtered(lambda f: f.relation == 'spouse')
            vals["spouse_name"] = employee.spouse_complete_name if hasattr(employee, 'spouse_complete_name') and employee.spouse_complete_name else (spouse[0].name if spouse else False)
        
        if vals.get("employee_id") and not vals.get("part_b_family_line_ids"):
            family_lines = []
            for idx, member in enumerate(employee.family_ids, start=1):
                family_lines.append((0, 0, {
                    'sequence': idx,
                    'member_name': member.name,
                    'relationship': dict(member._fields['relation'].selection).get(member.relation, member.relation),
                    'address': member.address or '',
                }))
            if family_lines:
                vals["part_b_family_line_ids"] = family_lines

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        super()._onchange_employee_id()
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.father_husband_name = employee.father_name or False
            record.date_of_birth = employee.birthday or False
            record.gender = employee.gender or False
            record.marital_status = employee.marital or False
            record.date_of_joining = employee.joining_date or employee.join_date or False
            if employee.private_street:
                record.permanent_address = employee.private_street
            if employee.address_id:
                record.temporary_address = employee.address_id._display_address()
            if hasattr(employee, "bank_account_id") and employee.bank_account_id:
                record.account_number = employee.bank_account_id.acc_number or False
            
            spouse = employee.family_ids.filtered(lambda f: f.relation == 'spouse')
            record.spouse_name = employee.spouse_complete_name if hasattr(employee, 'spouse_complete_name') and employee.spouse_complete_name else (spouse[0].name if spouse else False)
            
            # Populate family lines
            lines = [(5, 0, 0)]
            for idx, member in enumerate(employee.family_ids, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'member_name': member.name,
                    'relationship': dict(member._fields['relation'].selection).get(member.relation, member.relation),
                    'address': member.address or '',
                }))
            record.part_b_family_line_ids = lines


class HrCustomFormEleven(models.Model):
    _name = "hr.custom.form.form11"
    _description = "Form 11 (Composite Declaration Form)"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.form11"

    form_number = fields.Char(string="No.")
    spouse_name = fields.Char(string="Spouse Name")
    date_of_birth = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
    )
    marital_status = fields.Selection(
        [("single", "Single"), ("married", "Married"), ("widowed", "Widowed"), ("divorced", "Divorced")],
        string="Marital Status",
    )
    email = fields.Char(string="Email")
    mobile = fields.Char(string="Mobile")
    present_joining_date = fields.Date(string="Date of Joining (Current)")
    bank_account_no = fields.Char(string="Bank Account No.")
    bank_ifsc = fields.Char(string="IFSC Code")
    aadhaar_number = fields.Char(string="AADHAR Number")
    pan_number = fields.Char(string="PAN")
    member_epf_before = fields.Selection([("yes", "Yes"), ("no", "No")], string="Earlier EPF Member")
    member_eps_before = fields.Selection([("yes", "Yes"), ("no", "No")], string="Earlier EPS Member")
    prev_unexempted_line_ids = fields.One2many(
        "hr.custom.form.form11.prev.unexempted",
        "form_id",
        string="Previous Employment (Un-exempted)",
    )
    prev_exempted_line_ids = fields.One2many(
        "hr.custom.form.form11.prev.exempted",
        "form_id",
        string="Previous Employment (Exempted)",
    )
    international_worker = fields.Selection([("no", "No"), ("yes", "Yes")], string="International Worker", default="no")
    origin_country = fields.Char(string="Country of Origin")
    passport_no = fields.Char(string="Passport No.")
    passport_valid_from = fields.Date(string="Passport Valid From")
    passport_valid_to = fields.Date(string="Passport Valid To")

    def _prepare_employee_related_vals(self, vals):
        super()._prepare_employee_related_vals(vals)
        employee_id = vals.get("employee_id")
        if not employee_id:
            return
        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return
        if not vals.get("date_of_birth"):
            vals["date_of_birth"] = employee.birthday or False
        if not vals.get("gender") and employee.gender:
            vals["gender"] = employee.gender
        if not vals.get("marital_status") and employee.marital:
            vals["marital_status"] = employee.marital
        if not vals.get("email"):
            vals["email"] = employee.work_email or employee.private_email or False
        if not vals.get("mobile"):
            vals["mobile"] = employee.mobile_phone or employee.work_phone or False
        if not vals.get("present_joining_date"):
            vals["present_joining_date"] = employee.joining_date or employee.join_date or False
        if not vals.get("aadhaar_number"):
            vals["aadhaar_number"] = employee.identification_id or False
        if not vals.get("pan_number"):
            if hasattr(employee, 'pan') and employee.pan:
                vals["pan_number"] = employee.pan
            elif hasattr(employee, 'l10n_in_pan') and employee.l10n_in_pan:
                vals["pan_number"] = employee.l10n_in_pan
            else:
                vals["pan_number"] = False
            
        if not vals.get("spouse_name"):
            spouse = employee.family_ids.filtered(lambda f: f.relation == 'spouse')
            vals["spouse_name"] = employee.spouse_complete_name if hasattr(employee, 'spouse_complete_name') and employee.spouse_complete_name else (spouse[0].name if spouse else False)

        if hasattr(employee, "bank_account_id") and employee.bank_account_id:
            if not vals.get("bank_account_no"):
                vals["bank_account_no"] = employee.bank_account_id.acc_number or False
            if not vals.get("bank_ifsc") and employee.bank_account_id.bank_id and hasattr(employee.bank_account_id.bank_id, 'bic'):
                vals["bank_ifsc"] = employee.bank_account_id.bank_id.bic or False

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        super()._onchange_employee_id()
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.date_of_birth = employee.birthday or False
            record.gender = employee.gender or False
            record.marital_status = employee.marital or False
            record.email = employee.work_email or employee.private_email or False
            record.mobile = employee.mobile_phone or employee.work_phone or False
            record.present_joining_date = employee.joining_date or employee.join_date or False
            record.aadhaar_number = employee.identification_id or False
            if hasattr(employee, 'pan') and employee.pan:
                record.pan_number = employee.pan
            elif hasattr(employee, 'l10n_in_pan') and employee.l10n_in_pan:
                record.pan_number = employee.l10n_in_pan
            else:
                record.pan_number = False
                
            spouse = employee.family_ids.filtered(lambda f: f.relation == 'spouse')
            record.spouse_name = employee.spouse_complete_name if hasattr(employee, 'spouse_complete_name') and employee.spouse_complete_name else (spouse[0].name if spouse else False)
            if hasattr(employee, "bank_account_id") and employee.bank_account_id:
                record.bank_account_no = employee.bank_account_id.acc_number or False
                if employee.bank_account_id.bank_id and hasattr(employee.bank_account_id.bank_id, 'bic'):
                    record.bank_ifsc = employee.bank_account_id.bank_id.bic or False


class HrCustomFormFifteenG(models.Model):
    _name = "hr.custom.form.form15g"
    _description = "Form 15G"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.form15g"

    place = fields.Char(string="Place")
    declaration_date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    assessee_name = fields.Char(string="Name of Assessee")
    assessee_pan = fields.Char(string="PAN of Assessee")
    assessee_status = fields.Char(string="Status")
    previous_year = fields.Char(string="Previous Year")
    residential_status = fields.Char(string="Residential Status")
    address_flat = fields.Char(string="Flat / Door / Block No.")
    address_premises = fields.Char(string="Name of Premises")
    address_road = fields.Char(string="Road / Street / Lane")
    address_area = fields.Char(string="Area / Locality")
    address_city = fields.Char(string="Town / City / District")
    address_state = fields.Char(string="State")
    address_pin = fields.Char(string="PIN")
    contact_email = fields.Char(string="Email")
    contact_phone = fields.Char(string="Telephone / Mobile")
    assessed_to_tax = fields.Selection([("yes", "Yes"), ("no", "No")], string="Assessed to Tax")
    latest_assessment_year = fields.Char(string="Latest Assessment Year")
    estimated_income = fields.Float(string="Estimated Income (Declaration)")
    estimated_total_income = fields.Float(string="Estimated Total Income")
    other_form15g_count = fields.Integer(string="Total No. of other Form 15G")
    other_form15g_amount = fields.Float(string="Aggregate amount of income for prior Form 15G")
    other_form15g_details = fields.Text(string="Details of other Form 15G filed")
    income_detail_ids = fields.One2many(
        "hr.custom.form.form15g.income.line",
        "form_id",
        string="Income Details",
    )
    payer_name = fields.Char(string="Name of person responsible for paying")
    payer_uid = fields.Char(string="Unique Identification No.")
    payer_pan = fields.Char(string="PAN of person responsible for paying")
    payer_address = fields.Text(string="Complete Address")
    payer_tan = fields.Char(string="TAN")
    payer_email = fields.Char(string="Payer Email")
    payer_phone = fields.Char(string="Payer Telephone / Mobile")
    payer_income_amount = fields.Float(string="Amount of income paid")
    declaration_received_date = fields.Date(string="Declaration Received On")
    income_paid_date = fields.Date(string="Income Paid / Credited On")

    def _prepare_employee_related_vals(self, vals):
        super()._prepare_employee_related_vals(vals)
        employee_id = vals.get("employee_id")
        if not employee_id:
            return
        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return
        if not vals.get("assessee_name"):
            vals["assessee_name"] = employee.name or False
        if not vals.get("assessee_pan"):
            if hasattr(employee, 'pan') and employee.pan:
                vals["assessee_pan"] = employee.pan
            elif hasattr(employee, 'l10n_in_pan') and employee.l10n_in_pan:
                vals["assessee_pan"] = employee.l10n_in_pan
            else:
                vals["assessee_pan"] = False
        if not vals.get("contact_email"):
            vals["contact_email"] = employee.work_email or employee.private_email or False
        if not vals.get("contact_phone"):
            vals["contact_phone"] = employee.mobile_phone or employee.work_phone or False
        if employee.address_id:
            if not vals.get("address_city"):
                vals["address_city"] = employee.address_id.city or False
            if not vals.get("address_state") and employee.address_id.state_id:
                vals["address_state"] = employee.address_id.state_id.name or False
            if not vals.get("address_pin"):
                vals["address_pin"] = employee.address_id.zip or False

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        super()._onchange_employee_id()
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.assessee_name = employee.name or False
            if hasattr(employee, 'pan') and employee.pan:
                record.assessee_pan = employee.pan
            elif hasattr(employee, 'l10n_in_pan') and employee.l10n_in_pan:
                record.assessee_pan = employee.l10n_in_pan
            else:
                record.assessee_pan = False
            record.contact_email = employee.work_email or employee.private_email or False
            record.contact_phone = employee.mobile_phone or employee.work_phone or False
            if employee.address_id:
                record.address_city = employee.address_id.city or False
                if employee.address_id.state_id:
                    record.address_state = employee.address_id.state_id.name or False
                record.address_pin = employee.address_id.zip or False


class HrCustomFormLeaveApplication(models.Model):
    _name = "hr.custom.form.leave_application"
    _description = "Leave Application Form"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.leave_application"

    leave_request_date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    leave_reason = fields.Text(string="Reason for Leave")
    leave_days = fields.Float(string="Days")
    leave_from = fields.Date(string="From Date")
    leave_to = fields.Date(string="To Date")
    manager_remarks = fields.Text(string="Manager Remarks")
    approval_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        default="pending",
    )
    permanent_address = fields.Text(string="Permanent Address")
    contact_number = fields.Char(string="Mobile Number")

    def _prepare_employee_related_vals(self, vals):
        super()._prepare_employee_related_vals(vals)
        employee_id = vals.get("employee_id")
        if not employee_id:
            return
        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return
        if not vals.get("permanent_address") and employee.private_street:
            vals["permanent_address"] = employee.private_street
        if not vals.get("contact_number"):
            vals["contact_number"] = employee.mobile_phone or employee.work_phone or False

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        super()._onchange_employee_id()
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            if employee.private_street:
                record.permanent_address = employee.private_street
            record.contact_number = employee.mobile_phone or employee.work_phone or False


class HrCustomFormResignationLetter(models.Model):
    _name = "hr.custom.form.resignation_letter"
    _description = "Resignation Letter"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.resignation_letter"

    resignation_date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    resignation_description = fields.Text(string="Description")


class HrCustomFormCoverLetter(models.Model):
    _name = "hr.custom.form.cover_letter"
    _description = "Exchange Return Covering Letter"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.cover_letter"

    er_date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    er_to_address = fields.Text(string="To Address")
    er_subject = fields.Char(string="Subject")
    er_body = fields.Text(string="Body")
    er_quarter_end_date = fields.Date(string="Quarter Ending Date")


class HrCustomFormEr1EmploymentLine(models.Model):
    _name = "hr.custom.form.er1.employment.line"
    _description = "ER1 Employment Detail"

    form_id = fields.Many2one("hr.custom.form.er1", string="ER1 Form", ondelete="cascade")
    manpower_name = fields.Char(string="Man Power")
    prev_quarter_count = fields.Integer(string="Previous Quarter (Last Working Day)", default=0)
    current_quarter_count = fields.Integer(string="Reporting Quarter (Last Working Day)", default=0)


class HrCustomFormEr1VacancyLine(models.Model):
    _name = "hr.custom.form.er1.vacancy.line"
    _description = "ER1 Vacancy Detail"

    form_id = fields.Many2one("hr.custom.form.er1", string="ER1 Form", ondelete="cascade")
    occurred = fields.Integer(string="Occurred", default=0)
    notified_local = fields.Integer(string="Notified to Local Employment Exchange", default=0)
    notified_central = fields.Integer(string="Notified to Central Employment Exchange", default=0)
    filled_count = fields.Integer(string="Filled", default=0)
    source = fields.Char(string="Source (from which filled)")


class HrCustomFormEr1ShortageLine(models.Model):
    _name = "hr.custom.form.er1.shortage.line"
    _description = "ER1 Manpower Shortage Detail"

    form_id = fields.Many2one("hr.custom.form.er1", string="ER1 Form", ondelete="cascade")
    occupation_name = fields.Char(string="Occupation / Designation")
    essential_qualification = fields.Char(string="Essential Qualifications Prescribed")
    essential_experience = fields.Char(string="Essential Experience")
    experience_not_required = fields.Char(string="Experience Not Necessary")


class HrCustomFormFormDLine(models.Model):
    _name = "hr.custom.form.formd.line"
    _description = "Form D Wage Line"

    form_id = fields.Many2one("hr.custom.form.formd", string="Form D", ondelete="cascade")
    category_id = fields.Many2one("hr.job", string="Category of Workers")
    work_description = fields.Char(string="Brief Description of Work")
    men_employed = fields.Integer(string="No. of men employed")
    women_employed = fields.Integer(string="No. of women employed")
    remuneration_rate = fields.Char(string="Rate of remuneration paid")
    basic_wages = fields.Float(string="Basic Wages or Salary")
    part_da = fields.Float(string="D.A")
    part_hra = fields.Float(string="H.R.A")
    part_other_allowances = fields.Float(string="Other Allowances")
    part_cash_value = fields.Float(string="Cash value of concessional supply")


class HrCustomFormMwNoticeLine(models.Model):
    _name = "hr.custom.form.mw.notice.line"
    _description = "Minimum Wage Notice Line"

    notice_id = fields.Many2one("hr.custom.form.mw_notice", string="Notice", ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", string="Employee", check_company=True)
    father_name = fields.Char(string="Father / Husband Name")
    gender = fields.Selection([("male", "Male"), ("female", "Female"), ("other", "Other")], string="Gender")
    department_id = fields.Many2one("hr.department", string="Department")
    absence_date = fields.Date(string="Absence from duty (Date)")
    damages_description = fields.Text(string="Damages or Loss caused")
    damages_date = fields.Date(string="Damages date")
    showed_cause = fields.Selection([("yes", "Yes"), ("no", "No")], string="Worker showed cause?")
    show_cause_date = fields.Date(string="Show cause date")
    deduction_date = fields.Date(string="Date of deduction")
    deduction_amount = fields.Float(string="Amount of deduction")
    installment_count = fields.Integer(string="Number of installments")
    realisation_date = fields.Date(string="Date total realised")
    remarks = fields.Text(string="Remarks")

    @api.onchange("employee_id")
    def _onchange_employee(self):
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.father_name = employee.father_name or False
            record.gender = employee.gender or False
            record.department_id = employee.department_id or False


class HrCustomFormTwoPartALine(models.Model):
    _name = "hr.custom.form.form2.part.a.line"
    _description = "Form 2 Part A Line"

    form_id = fields.Many2one("hr.custom.form.form2", string="Form 2", ondelete="cascade")
    nominee_name = fields.Char(string="Name of nominee")
    nominee_address = fields.Text(string="Address")
    relationship = fields.Char(string="Relationship with member")
    date_of_birth = fields.Date(string="Date of Birth")
    share_amount = fields.Char(string="Share of accumulations")
    guardian_details = fields.Text(string="Guardian details (if nominee minor)")


class HrCustomFormTwoPartBFamilyLine(models.Model):
    _name = "hr.custom.form.form2.part.b.family.line"
    _description = "Form 2 Part B Family Line"

    form_id = fields.Many2one("hr.custom.form.form2", string="Form 2", ondelete="cascade")
    sequence = fields.Integer(string="S. No.")
    member_name = fields.Char(string="Name of family member")
    address = fields.Text(string="Address")
    date_of_birth = fields.Date(string="Date of Birth")
    relationship = fields.Char(string="Relationship with member")


class HrCustomFormTwoPartBNomineeLine(models.Model):
    _name = "hr.custom.form.form2.part.b.nominee.line"
    _description = "Form 2 Part B Nominee Line"

    form_id = fields.Many2one("hr.custom.form.form2", string="Form 2", ondelete="cascade")
    nominee_name = fields.Char(string="Name of nominee")
    nominee_address = fields.Text(string="Address")
    date_of_birth = fields.Date(string="Date of Birth")
    relationship = fields.Char(string="Relationship with member")


class HrCustomForm11PreviousUnexempted(models.Model):
    _name = "hr.custom.form.form11.prev.unexempted"
    _description = "Form 11 Previous Employment (Un-exempted)"

    form_id = fields.Many2one("hr.custom.form.form11", string="Form 11", ondelete="cascade")
    establishment = fields.Char(string="Establishment Name & Address")
    uan = fields.Char(string="Universal Account Number")
    pf_account = fields.Char(string="PF Account Number")
    joining_date = fields.Date(string="Date of joining")
    exit_date = fields.Date(string="Date of exit")
    scheme_certificate = fields.Char(string="Scheme Certificate No.")
    ppo_number = fields.Char(string="PPO Number")
    ncp_days = fields.Integer(string="NCP Days")


class HrCustomForm11PreviousExempted(models.Model):
    _name = "hr.custom.form.form11.prev.exempted"
    _description = "Form 11 Previous Employment (Exempted)"

    form_id = fields.Many2one("hr.custom.form.form11", string="Form 11", ondelete="cascade")
    trust_name = fields.Char(string="Name & Address of Trust")
    uan = fields.Char(string="UAN")
    eps_account = fields.Char(string="Member EPS A/c Number")
    joining_date = fields.Date(string="Date of joining")
    exit_date = fields.Date(string="Date of exit")
    scheme_certificate = fields.Char(string="Scheme Certificate No.")
    ncp_days = fields.Integer(string="NCP Days")


class HrCustomForm15GIncomeLine(models.Model):
    _name = "hr.custom.form.form15g.income.line"
    _description = "Form 15G Income Detail"

    form_id = fields.Many2one("hr.custom.form.form15g", string="Form 15G", ondelete="cascade")
    sequence = fields.Integer(string="Sl. No.")
    investment_identification = fields.Char(string="Investment / Account Identification")
    income_nature = fields.Char(string="Nature of income")
    deduction_section = fields.Char(string="Section")
    income_amount = fields.Float(string="Amount of income")


class HrCustomFormEsicDeclaration(models.Model):
    _name = "hr.custom.form.esic_declaration"
    _description = "ESIC Declaration Form"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.esic_declaration"

    esic_employee_name = fields.Char(string="Employee Name")
    esic_date_of_birth = fields.Date(string="Date of Birth")
    esic_father_name = fields.Char(string="Father Name")
    esic_gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
    )
    esic_marital_status = fields.Selection(
        [("single", "Single"), ("married", "Married"), ("widowed", "Widowed"), ("divorced", "Divorced")],
        string="Marital Status",
    )
    esic_present_address = fields.Text(string="Present Address")
    esic_permanent_address = fields.Text(string="Permanent Address")
    esic_date_of_joining = fields.Date(string="Date of Joining")
    esic_mobile_number = fields.Char(string="Mobile Number")
    # Bank Details
    esic_bank_name = fields.Char(string="Name of Bank")
    esic_bank_account_no = fields.Char(string="Bank Account Number")
    esic_bank_ifsc = fields.Char(string="IFSC Code")
    esic_bank_micr = fields.Char(string="MICR Number")
    # One2many fields
    family_line_ids = fields.One2many(
        "hr.custom.form.esic.family.line",
        "form_id",
        string="Family Details",
    )
    nominee_line_ids = fields.One2many(
        "hr.custom.form.esic.nominee.line",
        "form_id",
        string="Nominee Details",
    )

    def _prepare_employee_related_vals(self, vals):
        super()._prepare_employee_related_vals(vals)
        employee_id = vals.get("employee_id")
        if not employee_id:
            return
        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return
        if not vals.get("esic_employee_name"):
            vals["esic_employee_name"] = employee.name or False
        if not vals.get("esic_date_of_birth"):
            vals["esic_date_of_birth"] = employee.birthday or False
        if not vals.get("esic_father_name"):
            vals["esic_father_name"] = employee.father_name or False
        if not vals.get("esic_gender") and employee.gender:
            vals["esic_gender"] = employee.gender
        if not vals.get("esic_marital_status") and employee.marital:
            vals["esic_marital_status"] = employee.marital
        if not vals.get("esic_present_address") and employee.address_id:
            vals["esic_present_address"] = employee.address_id._display_address()
        if not vals.get("esic_permanent_address") and employee.private_street:
            vals["esic_permanent_address"] = employee.private_street
        if not vals.get("esic_date_of_joining"):
            vals["esic_date_of_joining"] = employee.joining_date or employee.join_date or False
        if not vals.get("esic_mobile_number"):
            vals["esic_mobile_number"] = employee.mobile_phone or employee.work_phone or False
        # Bank details
        if hasattr(employee, "bank_account_id") and employee.bank_account_id:
            if not vals.get("esic_bank_account_no"):
                vals["esic_bank_account_no"] = employee.bank_account_id.acc_number or False
            if not vals.get("esic_bank_name") and employee.bank_account_id.bank_id:
                vals["esic_bank_name"] = employee.bank_account_id.bank_id.name or False
            if not vals.get("esic_bank_ifsc") and employee.bank_account_id.bank_id and hasattr(employee.bank_account_id.bank_id, 'bic'):
                vals["esic_bank_ifsc"] = employee.bank_account_id.bank_id.bic or False
                
        if vals.get("employee_id") and not vals.get("family_line_ids"):
            family_lines = []
            for idx, member in enumerate(employee.family_ids, start=1):
                family_lines.append((0, 0, {
                    'sequence': idx,
                    'family_member_name': member.name,
                    'relation': dict(member._fields['relation'].selection).get(member.relation, member.relation),
                }))
            if family_lines:
                vals["family_line_ids"] = family_lines

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        super()._onchange_employee_id()
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.esic_employee_name = employee.name or False
            record.esic_date_of_birth = employee.birthday or False
            record.esic_father_name = employee.father_name or False
            record.esic_gender = employee.gender or False
            record.esic_marital_status = employee.marital or False
            if employee.address_id:
                record.esic_present_address = employee.address_id._display_address()
            if employee.private_street:
                record.esic_permanent_address = employee.private_street
            record.esic_date_of_joining = employee.joining_date or employee.join_date or False
            record.esic_mobile_number = employee.mobile_phone or employee.work_phone or False
            if hasattr(employee, "bank_account_id") and employee.bank_account_id:
                record.esic_bank_account_no = employee.bank_account_id.acc_number or False
                if employee.bank_account_id.bank_id:
                    record.esic_bank_name = employee.bank_account_id.bank_id.name or False
                    if hasattr(employee.bank_account_id.bank_id, 'bic'):
                        record.esic_bank_ifsc = employee.bank_account_id.bank_id.bic or False
                        
            # Populate ESIC family lines
            lines = [(5, 0, 0)]
            for idx, member in enumerate(employee.family_ids, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'family_member_name': member.name,
                    'relation': dict(member._fields['relation'].selection).get(member.relation, member.relation),
                }))
            record.family_line_ids = lines


class HrCustomFormEsicFamilyLine(models.Model):
    _name = "hr.custom.form.esic.family.line"
    _description = "ESIC Family Detail"

    form_id = fields.Many2one("hr.custom.form.esic_declaration", string="ESIC Form", ondelete="cascade")
    sequence = fields.Integer(string="Sr. No.")
    family_member_name = fields.Char(string="Family Member's Name")
    relation = fields.Char(string="Relation With Employee")
    date_of_birth = fields.Date(string="Date of Birth")
    residing_with_ip = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Whether Residing with IP?",
    )
    residence_state = fields.Char(string="State (If Not Residing)")
    residence_district = fields.Char(string="District (If Not Residing)")
    aadhaar_no = fields.Char(string="Aadhar No.")


class HrCustomFormEsicNomineeLine(models.Model):
    _name = "hr.custom.form.esic.nominee.line"
    _description = "ESIC Nominee Detail"

    form_id = fields.Many2one("hr.custom.form.esic_declaration", string="ESIC Form", ondelete="cascade")
    nominee_name = fields.Char(string="Name of Nominee")
    relation = fields.Char(string="Relation With Employee")
    nominee_address = fields.Text(string="Address of Nominee")
    contact_no = fields.Char(string="Contact No.")


class HrCustomFormPf(models.Model):
    _name = "hr.custom.form.pf"
    _description = "PF Form"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.pf"

    pf_line_ids = fields.One2many(
        "hr.custom.form.pf.line",
        "form_id",
        string="PF Details",
    )


class HrCustomFormPfLine(models.Model):
    _name = "hr.custom.form.pf.line"
    _description = "PF Form Line"

    form_id = fields.Many2one("hr.custom.form.pf", string="PF Form", ondelete="cascade")
    sequence = fields.Integer(string="Sr. No.")
    old_uan_no = fields.Char(string="Old UAN No. (if new Employees Have)")
    dol_prev_employment = fields.Date(string="DOL of Previous Employment")
    personal_title = fields.Selection(
        [("mr", "Mr."), ("ms", "Ms."), ("mrs", "Mrs.")],
        string="Personal Title",
    )
    employee_id = fields.Many2one("hr.employee", string="Name", check_company=True)
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
    )
    date_of_birth = fields.Date(string="Date of Birth")
    father_husband_name = fields.Char(string="Father's / Husband Name")
    relation = fields.Selection(
        [("father", "Father"), ("husband", "Husband")],
        string="Relation",
    )
    marital_status = fields.Selection(
        [("single", "Single"), ("married", "Married"), ("widowed", "Widowed"), ("divorced", "Divorced")],
        string="Marital Status",
    )
    date_of_joining = fields.Date(string="Date of Joining")
    mobile_number = fields.Char(string="Mobile Number")
    pan_number = fields.Char(string="PAN Number")
    pan_card_name = fields.Char(string="Name as per PAN Card")
    aadhaar_number = fields.Char(string="Aadhar Number")
    aadhaar_name = fields.Char(string="Name as per Aadhar")
    pf_wage_type = fields.Selection(
        [
            ("pf_wages", "PF Wages"),
            ("pf_salary", "PF Salary"),
            ("pf_deductible_salary", "PF Deductible Salary"),
        ],
        string="PF Wages / PF Salary / PF Deductible Salary",
    )
    pension_applicable = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is Pension Contribution Applicable",
    )

    @api.onchange("employee_id")
    def _onchange_employee(self):
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.gender = employee.gender or False
            record.date_of_birth = employee.birthday or False
            record.father_husband_name = employee.father_name or False
            record.marital_status = employee.marital or False
            record.date_of_joining = employee.joining_date or employee.join_date or False
            record.mobile_number = employee.mobile_phone or employee.work_phone or False
            if hasattr(employee, "identification_id"):
                record.aadhaar_number = employee.identification_id or False
            if hasattr(employee, "pan") and employee.pan:
                record.pan_number = employee.pan
            elif hasattr(employee, "l10n_in_pan") and employee.l10n_in_pan:
                record.pan_number = employee.l10n_in_pan
            else:
                record.pan_number = False
                
            if hasattr(employee, "uan"):
                record.old_uan_no = employee.uan or False


class HrRelationship(models.Model):
    _name = "hr.relationship"
    _description = "Relationship Master"
    _order = "sequence, name"

    name = fields.Char(string="Relationship", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)


class HrCustomFormNominationF(models.Model):
    _name = "hr.custom.form.nomination_f"
    _description = "Nomination Form 'F'"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.nomination_f"

    # Statement Page Fields
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    caste_id = fields.Many2one("hr.caste", string="Caste")
    marital_status = fields.Selection(
        [
            ("single", "Single"),
            ("married", "Married"),
            ("widowed", "Widowed"),
            ("divorced", "Divorced"),
        ],
        string="Marital Status",
    )
    post_held = fields.Char(string="Post held with Ticket or Serial No., if any")
    permanent_address = fields.Text(string="Permanent Address")

    # Location Fields
    village = fields.Char(string="Village")
    thana = fields.Char(string="Thana")
    sub_division = fields.Char(string="Sub-division")
    post_office = fields.Char(string="Post Office")
    district = fields.Char(string="District")
    state = fields.Char(string="State")

    # Nomination Context
    nomination_context = fields.Html(
        string="Nomination Context",
        default=lambda self: self._get_default_nomination_context(),
    )

    def _get_default_nomination_context(self):
        """Return default nomination context text."""
        return """
<p>1. Shri _______________________ whose particulars are given in the statement below,</p>
<p>hereby nominate the person(s) mentioned below to receive the gratuity payable after my death as also the gratuity standing to my credit in the event of my death before that amount has become payable, or having become payable has not been paid and direct that the said amount of gratuity shall be paid in proportion indicated against the name(s) of the nominee(s).</p>
<p>2. I hereby certify that the person(s) mentioned is a/are member(s) of my family within the meaning of clause (h) of section (2) of the Payment of Gratuity Act, 1972.</p>
<p>3. I hereby declare that I have no family within the meaning of clause (h) of section (2) of the said Act.</p>
<p>4. (a) My father/mother/parents is/are not dependent on me.<br/>
   (b) My husband's father/mother/parents is/are not dependent on my husband.</p>
<p>5. I have excluded my husband from my family by a notice dated the ………………… to the Controlling Authority in terms of the proviso to clause (h) of section 2 of the said Act.</p>
<p>6. Nomination made herein invalidates my previous nomination.</p>
"""

    def _get_nomination_context_with_employee(self, employee_name):
        """Return nomination context with employee name filled in."""
        return f"""
<p>1. Shri <strong> {employee_name} </strong> whose particulars are given in the statement below,</p>
<p>hereby nominate the person(s) mentioned below to receive the gratuity payable after my death as also the gratuity standing to my credit in the event of my death before that amount has become payable, or having become payable has not been paid and direct that the said amount of gratuity shall be paid in proportion indicated against the name(s) of the nominee(s).</p>
<p>2. I hereby certify that the person(s) mentioned is a/are member(s) of my family within the meaning of clause (h) of section (2) of the Payment of Gratuity Act, 1972.</p>
<p>3. I hereby declare that I have no family within the meaning of clause (h) of section (2) of the said Act.</p>
<p>4. (a) My father/mother/parents is/are not dependent on me.<br/>
   (b) My husband's father/mother/parents is/are not dependent on my husband.</p>
<p>5. I have excluded my husband from my family by a notice dated the ………………… to the Controlling Authority in terms of the proviso to clause (h) of section 2 of the said Act.</p>
<p>6. Nomination made herein invalidates my previous nomination.</p>
"""

    # One2many fields
    nominee_line_ids = fields.One2many(
        "hr.custom.form.nomination_f.nominee.line",
        "form_id",
        string="Nominees",
    )
    witness_line_ids = fields.One2many(
        "hr.custom.form.nomination_f.witness.line",
        "form_id",
        string="Witnesses",
    )

    def _prepare_employee_related_vals(self, vals):
        super()._prepare_employee_related_vals(vals)
        employee_id = vals.get("employee_id")
        if not employee_id:
            return
        employee = self.env["hr.employee"].browse(employee_id)
        if not employee:
            return
        if not vals.get("gender") and employee.gender:
            vals["gender"] = employee.gender
        if not vals.get("marital_status") and employee.marital:
            vals["marital_status"] = employee.marital
        if not vals.get("permanent_address") and employee.private_street:
            vals["permanent_address"] = employee.private_street
        if not vals.get("caste_id") and employee.caste_id:
            vals["caste_id"] = employee.caste_id.id

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        super()._onchange_employee_id()
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            # Ensure employee_code is updated
            record.employee_code = employee.employee_code or False
            record.gender = employee.gender or False
            record.marital_status = employee.marital or False
            record.caste_id = employee.caste_id or False
            if employee.private_street:
                record.permanent_address = employee.private_street
            # Update nomination context with employee name
            record.nomination_context = record._get_nomination_context_with_employee(employee.name)


class HrCustomFormNominationFNomineeLine(models.Model):
    _name = "hr.custom.form.nomination_f.nominee.line"
    _description = "Nomination Form 'F' Nominee Line"

    form_id = fields.Many2one(
        "hr.custom.form.nomination_f",
        string="Nomination Form",
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Sr. No.", default=10)
    nominee_name_address = fields.Text(
        string="Name in full with full address of nominee(s)",
        required=True,
    )
    relationship_id = fields.Many2one(
        "hr.relationship",
        string="Relationship with the employee",
    )
    age = fields.Char(string="Age of nominee")
    share_percentage = fields.Float(
        string="Proportion by which the gratuity will be shared (%)",
        help="Percentage of gratuity to be shared with this nominee",
    )


class HrCustomFormNominationFWitnessLine(models.Model):
    _name = "hr.custom.form.nomination_f.witness.line"
    _description = "Nomination Form 'F' Witness Line"

    form_id = fields.Many2one(
        "hr.custom.form.nomination_f",
        string="Nomination Form",
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Sr. No.", default=10)
    witness_name = fields.Char(string="Witness Name", required=True)
    witness_address = fields.Text(string="Witness Full Address", required=True)


class HrCustomFormDeptAttendance(models.Model):
    _name = "hr.custom.form.dept_attendance"
    _description = "Department Wise Attendance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "form_date desc, name desc"

    _sequence_code = "hr.custom.form.dept_attendance"

    name = fields.Char(
        string="Document Reference",
        required=True,
        default=lambda self: _("New"),
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    form_date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Document creation date (auto-filled with today's date)",
    )
    night_date = fields.Date(
        string="Night Date",
        tracking=True,
        help="Date for night shift attendance",
    )
    day_date = fields.Date(
        string="Day Date",
        tracking=True,
        help="Date for day shift attendance",
    )
    line_ids = fields.One2many(
        "hr.custom.form.dept_attendance.line",
        "form_id",
        string="Department Attendance Lines",
    )
    total_night = fields.Integer(
        string="Total Night",
        compute="_compute_totals",
        store=True,
        help="Sum of all night shift counts",
    )
    total_day = fields.Integer(
        string="Total Day",
        compute="_compute_totals",
        store=True,
        help="Sum of all day shift counts",
    )
    total_attendance = fields.Integer(
        string="Grand Total",
        compute="_compute_totals",
        store=True,
        help="Sum of all attendance counts",
    )

    @api.depends("line_ids.night_count", "line_ids.day_count", "line_ids.total_count")
    def _compute_totals(self):
        for record in self:
            record.total_night = sum(record.line_ids.mapped("night_count"))
            record.total_day = sum(record.line_ids.mapped("day_count"))
            record.total_attendance = sum(record.line_ids.mapped("total_count"))

    def _next_sequence(self, company_id):
        seq_code = self._sequence_code
        seq_env = self.env["ir.sequence"]
        if company_id:
            company = self.env["res.company"].browse(company_id)
            seq_env = seq_env.with_company(company)
        return seq_env.next_by_code(seq_code) or _("New")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") in ("New", _("New")):
                vals["name"] = self._next_sequence(vals.get("company_id"))
        return super().create(vals_list)


class HrCustomFormDeptAttendanceLine(models.Model):
    _name = "hr.custom.form.dept_attendance.line"
    _description = "Department Wise Attendance Line"
    _order = "sequence, id"

    form_id = fields.Many2one(
        "hr.custom.form.dept_attendance",
        string="Department Attendance Form",
        ondelete="cascade",
        required=True,
    )
    sequence = fields.Integer(string="S.No.", default=10)
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        required=True,
    )
    description = fields.Text(
        string="Description",
        help="Additional notes or description for this department's attendance",
    )
    night_count = fields.Integer(
        string="Night",
        default=0,
        help="Number of employees present in night shift",
    )
    day_count = fields.Integer(
        string="Day",
        default=0,
        help="Number of employees present in day shift",
    )
    total_count = fields.Integer(
        string="Total",
        compute="_compute_total_count",
        store=True,
        help="Total attendance count (Night + Day)",
    )

    @api.depends("night_count", "day_count")
    def _compute_total_count(self):
        for line in self:
            line.total_count = line.night_count + line.day_count


class HrCustomFormLabourColonyAgreement(models.Model):
    _name = "hr.custom.form.labour_colony_agreement"
    _description = "Labour Colony Agreement"
    _inherit = "hr.custom.form.base"

    _sequence_code = "hr.custom.form.labour_colony_agreement"

    location = fields.Char(
        string="Location",
        help="Location/Colony name (e.g., VIRAMGAM)",
    )
    agreement_content = fields.Html(
        string="Policy for Accommodation / Residence provided by the Company",
        default=LABOUR_COLONY_AGREEMENT_DEFAULT_HTML,
        help="Content of the Labour Colony Agreement policy in Hindi",
    )
    agreement_content_hindi_title = fields.Char(
        string="Hindi Title",
        default="कंपनीद्वाराप्रदानकीगईआवास / निवासकेलिएनीति",
        help="Hindi title for the policy",
    )