import requests
from datetime import datetime, timedelta
import pytz
from odoo import models, fields
from odoo.exceptions import UserError

class BiometricDevice(models.Model):
    _name = 'biometric.device'
    _description = 'Biometric Device'

    name = fields.Char(required=True)
    ip_address = fields.Char(required=True)
    password = fields.Char(required=True)
    device_type = fields.Selection([
        ('in', 'IN Device'),
        ('out', 'OUT Device')
    ], required=True)
    active = fields.Boolean(default=True)
    last_sync = fields.Datetime(string="Last Synced", readonly=True)

    def action_test_connection(self):
        url = f"http://{self.ip_address}/api"
        payload = {"password": self.password, "cmd": "getlog", "index": 0}
        try:
            r = requests.post(url, json=payload, timeout=5)
            data = r.json()
            if r.status_code == 200 and data.get('result'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Successful',
                        'message': f"Device {data.get('sn', '')} is reachable.",
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError("Connection Failed! Check IP or password.")
        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Connection Error: {str(e)}")

    def sync_device_logs(self):
        for device in self.search([('active', '=', True)]):
            device._fetch_logs()

    def _fetch_logs(self):
        url = f"http://{self.ip_address}/api"
        ist = pytz.timezone('Asia/Kolkata')

        # Fetch from last 2 days to be safe, or from last_sync
        if self.last_sync:
            # Convert last_sync (UTC) to IST for device query
            last_sync_ist = self.last_sync.replace(
                tzinfo=pytz.utc).astimezone(ist)
            from_date = (last_sync_ist - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            # First time — fetch last 30 days
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

        index = 0
        while True:
            payload = {
                "password": self.password,
                "cmd": "getlog",
                "index": index,
                "from": from_date,
            }
            try:
                response = requests.post(url, json=payload, timeout=10)
                data = response.json()
            except Exception:
                break

            records = data.get("record", [])
            if not records:
                break

            for rec in records:
                self.env['biometric.log'].create_log(self, rec)

            to = data.get("to", 0)
            count = data.get("count", 0)

            if to + 1 >= count:
                break

            index = to + 1

        # Update last_sync to now (UTC)
        self.last_sync = fields.Datetime.now()