import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api
from odoo.exceptions import UserError

class BiometricDevice(models.Model):
    _name = 'biometric.device'
    _description = 'Biometric Device'

    name = fields.Char(required=True)
    connection_type = fields.Selection([
        ('local', 'Local / Gateway'),
        ('etimeoffice', 'eTimeOffice Cloud API')
    ], required=True, default='local', string="Connection Type")
    ip_address = fields.Char(required=False)
    password = fields.Char(required=False)

    # eTimeOffice specific fields
    corporate_id = fields.Char(string="Corporate ID")
    etimeoffice_username = fields.Char(string="eTimeOffice Username")
    etimeoffice_password = fields.Char(string="eTimeOffice Password")
    etimeoffice_base_url = fields.Char(
        string="eTimeOffice Base URL",
        default="https://api.etimeoffice.com/api/",
    )
    etimeoffice_device_id = fields.Char(
        string="Machine ID Filter",
        help="Filter logs by Machine ID/Name (e.g. '1 - Paldi Rd...'). If blank, all logs are imported.",
    )

    device_type = fields.Selection([
        ('in', 'IN Device'),
        ('out', 'OUT Device')
    ], required=True)
    active = fields.Boolean(default=True)
    last_sync = fields.Datetime(string="Last Synced", readonly=True)

    @api.constrains('connection_type', 'ip_address', 'password', 'corporate_id', 'etimeoffice_username', 'etimeoffice_password')
    def _check_connection_credentials(self):
        for record in self:
            if record.connection_type == 'local':
                if not record.ip_address or not record.password:
                    raise UserError("IP Address and Password are required for local connections.")
            elif record.connection_type == 'etimeoffice':
                if not record.corporate_id or not record.etimeoffice_username or not record.etimeoffice_password:
                    raise UserError("Corporate ID, eTimeOffice Username, and eTimeOffice Password are required for eTimeOffice connections.")

    def action_test_connection(self):
        """Test connectivity.
        
        For local devices: indirectly using logs pushed by the gateway.
        For eTimeOffice: query the API directly with current credentials.
        """
        self.ensure_one()
        if self.connection_type == 'etimeoffice':
            return self._test_etimeoffice_connection()
        else:
            return self._test_local_connection()

    def _test_local_connection(self):
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

    def _test_etimeoffice_connection(self):
        url = f"{self.etimeoffice_base_url.rstrip('/')}/DownloadPunchDataMCID"
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(pytz.utc).astimezone(ist)
        from_date = (now_ist - timedelta(hours=1)).strftime('%d/%m/%Y_%H:%M')
        to_date = now_ist.strftime('%d/%m/%Y_%H:%M')

        url_with_params = f"{url}?Empcode=ALL&FromDate={from_date}&ToDate={to_date}"
        auth_username = f"{self.corporate_id}:{self.etimeoffice_username}:{self.etimeoffice_password}:true"

        try:
            response = requests.get(
                url_with_params,
                auth=HTTPBasicAuth(auth_username, ""),
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if not data.get("Error", True):
                    title = "eTimeOffice Connected"
                    msg = "Successfully authenticated and connected to eTimeOffice server."
                    notif_type = "success"
                else:
                    title = "eTimeOffice Connection Failed"
                    msg = data.get("Msg", "Unknown error returned by server.")
                    notif_type = "danger"
            else:
                title = "eTimeOffice Connection Failed"
                msg = f"HTTP Error {response.status_code}: {response.text}"
                notif_type = "danger"
        except Exception as e:
            title = "eTimeOffice Connection Error"
            msg = f"Failed to connect: {str(e)}"
            notif_type = "danger"

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
        self.ensure_one()
        if self.connection_type == 'etimeoffice':
            self._fetch_etimeoffice_logs()
        else:
            self._fetch_local_logs()

    def _fetch_local_logs(self):
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

    def _fetch_etimeoffice_logs(self):
        url = f"{self.etimeoffice_base_url.rstrip('/')}/DownloadPunchDataMCID"
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(pytz.utc).astimezone(ist)
        
        if self.last_sync:
            last_sync_ist = self.last_sync.replace(tzinfo=pytz.utc).astimezone(ist)
            from_date = (last_sync_ist - timedelta(hours=1)).strftime('%d/%m/%Y_%H:%M')
        else:
            from_date = (now_ist - timedelta(days=30)).strftime('%d/%m/%Y_%H:%M')
            
        to_date = now_ist.strftime('%d/%m/%Y_%H:%M')
        
        url_with_params = f"{url}?Empcode=ALL&FromDate={from_date}&ToDate={to_date}"
        auth_username = f"{self.corporate_id}:{self.etimeoffice_username}:{self.etimeoffice_password}:true"
        
        try:
            response = requests.get(
                url_with_params,
                auth=HTTPBasicAuth(auth_username, ""),
                timeout=30
            )
            if response.status_code != 200:
                return
            data = response.json()
        except Exception:
            return
            
        if not data or data.get("Error", True):
            return
            
        punch_records = data.get("PunchData", [])
        for punch in punch_records:
            emp_code = punch.get("Empcode")
            punch_date_str = punch.get("PunchDate")
            mcid = punch.get("mcid")
            
            if not emp_code or not punch_date_str:
                continue
                
            if self.etimeoffice_device_id and mcid:
                filter_val = self.etimeoffice_device_id.strip()
                # Check if it matches exactly, or if the filter value starts with this MCID (e.g. '1 - Paldi Rd...')
                if str(mcid) != filter_val and not filter_val.startswith(f"{str(mcid)} "):
                    continue
                    
            try:
                # Expecting format "DD/MM/YYYY HH:MM:SS" or "DD/MM/YYYY HH:MM"
                dt = datetime.strptime(punch_date_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                try:
                    dt = datetime.strptime(punch_date_str, "%d/%m/%Y %H:%M")
                except ValueError:
                    continue
                    
            time_ist_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            rec = {
                'enrollid': str(emp_code),
                'time': time_ist_str,
                'mode': 1,
            }
            self.env['biometric.log'].create_log(self, rec)
            
        # Update last_sync to now (UTC)
        self.last_sync = fields.Datetime.now()