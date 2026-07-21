from odoo import models
import datetime

class AttendanceReportXlsx(models.AbstractModel):
    _name = 'report.hr_attendance_gantt_enhanced.attendance_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizard):
        wizard = wizard.ensure_one()
        records = data.get('data') if isinstance(data, dict) else None
        if not records:
            # Fallback for direct report calls where the data payload is missing.
            records = wizard._prepare_report_payload().get('data', [])

        sheet = workbook.add_worksheet('Attendance Report')
        bold = workbook.add_format({'bold': True})
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})

        static_headers = [
            'Employee Code', 'Full Name', 'Employment Status', 'Company', 'Business Unit',
            'Department', 'Designation', 'Branch', 'Sub Branch', 'Card No', 'Father Name',
            'Age', 'Gender', 'Date of Joining'
        ]

        # NEW: keep ISO keys for data lookup, separate DD/MM/YYYY strings for display
        date_range_dates = [wizard.start_date + datetime.timedelta(days=x)
                            for x in range((wizard.end_date - wizard.start_date).days + 1)]
        date_keys = [str(d) for d in date_range_dates]  # lookup keys, unchanged
        date_headers = [d.strftime('%d-%m-%Y') for d in date_range_dates]

        summary_headers = [
            'Days P|P', 'Days P|A', 'Days A|P', 'Days A|A',
            'Expected Work Days', 'Present', 'Weekoff', 'Holiday', 'CL', 'CO', 'Comp-off', 'EL', 'SL',
            'Absent', 'Pay Days', 'Total',
            'Expected Working Hours', 'Actual Working Hours', 'Count of AR', 'Count of OD',
            'Count of Short Leave', 'Count of Early Late', 'Last Attendance Worked Hours',
            'Attendance State', 'Total Overtime', 'Remaining Leaves', 'Leaves Count',
            'Hours Previously Today', 'Hours Last Month', 'Allocation Count', 'Allocations Count',
            'Contracts Count', 'Resource Calendar', 'Expense Manager', 'Leave Manager'
        ]
        headers = static_headers + date_headers + summary_headers

        # Write headers
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)
        
        # Write data rows
        for row, record in enumerate(records, start=1):
            col = 0
            for h in static_headers:
                key = h.lower().replace(' ', '_')
                value = record.get(key, '')
                if key == 'date_of_joining' and value:
                    # value may arrive as a string (data is JSON-serialized for report download)
                    if isinstance(value, str):
                        try:
                            value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
                        except ValueError:
                            value = None
                    if value:
                        sheet.write_datetime(row, col, value, date_format)
                    else:
                        sheet.write(row, col, '')
                else:
                    sheet.write(row, col, value)
                col += 1

            for dk in date_keys:
                sheet.write(row, col, record.get(dk, ''))
                col += 1

            for h in summary_headers:
                key = h.lower().replace(' ', '_')
                sheet.write(row, col, record.get(key, ''))
                col += 1