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
        """Test connectivity indirectly using logs pushed by the gateway.

                Since the Odoo server cannot reach 192.168.x.x directly, we treat a
                recent log from this device (via the on‑prem gateway) as proof that
                the device and gateway are both working.
                """
        self.ensure_one()

        # Look for most recent log for this device
        log = self.env['biometric.log'].search(
            [('device_id', '=', self.id)],
            order='punch_time desc',
            limit=1,
        )

        if not log:
            raise UserError(
                "No logs received yet from this device via the gateway.\n"
                "Please confirm the Windows gateway service is running and "
                "that this device IP is configured in its config.json."
            )

        # Optional: consider "recent" = last 24 hours
        now_utc = fields.Datetime.now()
        delta = now_utc - log.punch_time
        hours = delta.total_seconds() / 3600.0

        title = 'Gateway Connected'
        if hours <= 24:
            msg = (
                f"Last log from this device was received "
                f"{delta} ago at {log.punch_time} (UTC)."
            )
            notif_type = 'success'
        else:
            msg = (
                "Device has sent logs via gateway before, but not in the last "
                "24 hours.\n"
                f"Last log time: {log.punch_time} (UTC)."
            )
            notif_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': msg,
                'type': notif_type,
                'sticky': False,
            },
        }

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