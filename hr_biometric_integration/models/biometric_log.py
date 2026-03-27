from odoo import models, fields
from datetime import datetime
import pytz

class BiometricLog(models.Model):
    _name = 'biometric.log'
    _description = 'Biometric Logs'
    _order = 'punch_time desc'

    device_id = fields.Many2one('biometric.device')
    enroll_id = fields.Char()
    employee_id = fields.Many2one('hr.employee')
    punch_time = fields.Datetime()
    mode = fields.Integer()
    raw_json = fields.Text()

    def _convert_to_utc(self, time_str):
        ist = pytz.timezone('Asia/Kolkata')
        naive_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        ist_dt = ist.localize(naive_dt)
        return ist_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def create_log(self, device, rec):
        utc_time = self._convert_to_utc(rec['time'])

        # Duplicate check using enroll_id + device_id + punch_time
        existing = self.search([
            ('enroll_id', '=', str(rec['enrollid'])),
            ('device_id', '=', device.id),
            ('punch_time', '=', utc_time),
        ], limit=1)

        if existing:
            return

        employee = self.env['hr.employee'].search([
            ('biometric_id', '=', str(rec['enrollid']))
        ], limit=1)

        self.create({
            'device_id': device.id,
            'enroll_id': str(rec['enrollid']),
            'employee_id': employee.id if employee else False,
            'punch_time': utc_time,
            'mode': rec['mode'],
            'raw_json': str(rec),
        })

        if employee:
            self._process_attendance(device, employee, utc_time)

    def _process_attendance(self, device, employee, punch_dt):
        if device.device_type == 'in':
            open_attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], order='check_in desc', limit=1)

            if open_attendance:
                return

            self.env['hr.attendance'].create({
                'employee_id': employee.id,
                'check_in': punch_dt,
            })

        elif device.device_type == 'out':
            attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], order='check_in desc', limit=1)

            if attendance and punch_dt > attendance.check_in:
                attendance.check_out = punch_dt