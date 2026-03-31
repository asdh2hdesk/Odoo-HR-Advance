Biometric Gateway – Windows Service
==================================

Overview
--------
This gateway runs on a Windows machine INSIDE the client LAN (same network as the biometric devices).
It polls each biometric device via its HTTP /api endpoint and pushes logs to the cloud Odoo server.

Odoo never connects directly to 192.168.x.x devices. Instead:
- Gateway → devices: HTTP on LAN (e.g. http://192.168.20.141/api)
- Gateway → Odoo: HTTP/HTTPS to /biometric/gateway/push_logs

Folder layout on the Windows machine
------------------------------------
Recommended runtime folder: C:\BiometricGateway\

Files:
- C:\BiometricGateway\config.json        → gateway configuration (edit this)
- C:\BiometricGateway\gateway_core.py    → polling & push logic
- C:\BiometricGateway\gateway_service.py → Windows service wrapper
- C:\BiometricGateway\gateway_state.json → auto-created state (last sync per device)

In the Odoo module (for version control) you can store templates in:
hr_biometric_integration/gateway_client/
- config.example.json
- gateway_core.py
- gateway_service.py
- README_gateway.txt

Windows prerequisites
---------------------
1. Install Python 3.x (64-bit) on the gateway machine.
2. Install dependencies in an elevated command prompt:

   pip install requests pywin32

3. (Sometimes required) finalize pywin32:

   python -m pip install --upgrade pip
   python -m pip install pywin32
   python Scripts/pywin32_postinstall.py -install

4. Copy the gateway files from the Odoo addon to C:\BiometricGateway\:
   - config.example.json → rename to config.json
   - gateway_core.py
   - gateway_service.py

Configure config.json
---------------------
Example:

{
  "odoo_url": "http://20.193.254.185:8069",
  "odoo_token": "VERY_LONG_RANDOM_SECRET",
  "poll_interval_seconds": 60,
  "devices": [
    {
      "name": "Punch IN",
      "ip": "192.168.20.141",
      "password": "device_password_here",
      "type": "in"
    },
    {
      "name": "Punch OUT",
      "ip": "192.168.20.142",
      "password": "device_password_here",
      "type": "out"
    }
  ]
}

Important:
- odoo_url: base URL of the Odoo server.
- odoo_token: must match the value stored in Odoo system parameter "biometric.gateway_token".
- poll_interval_seconds: how often to poll each device.
- devices: list of all biometric devices reachable from this Windows machine.

Odoo configuration
------------------
1. Install / update the HR_BIO_INT module.
2. Ensure the controller route exists:
   /biometric/gateway/push_logs  (type='json', auth='none')
3. In Odoo: Settings → Technical → System Parameters:
   - Create key: biometric.gateway_token
   - Value: SAME SECRET used in config.json under "odoo_token".

4. The controller delegates records to:
   env['biometric.log'].process_gateway_payload(device, records)
   which uses existing duplicate checks and attendance logic.

Installing the Windows service
------------------------------
Run an elevated command prompt in C:\BiometricGateway\:

1) Install the service:

   python gateway_service.py install

2) Start the service:

   python gateway_service.py start

3) To stop / remove later:

   python gateway_service.py stop
   python gateway_service.py remove

You can also manage "BiometricGatewayService" from:
- Start → Run → services.msc

Testing before using as a service
---------------------------------
You can run the gateway loop directly for debugging:

1) Ensure config.json is valid.
2) From C:\BiometricGateway\:

   python gateway_core.py

This runs a loop that polls devices and pushes to Odoo.
Press Ctrl+C to stop.

Basic verification steps
------------------------
1. From the gateway machine, confirm you can reach devices:

   - ping 192.168.20.141
   - (optional) curl http://192.168.20.141/api  (or use a browser/Postman)

2. From the gateway machine, confirm you can reach Odoo:

   - Browse to the odoo_url (e.g. http://20.193.254.185:8069/)

3. Start the service and watch Odoo logs:
   - You should see POST requests to /biometric/gateway/push_logs.
   - New biometric.log records and HR attendance should appear.

Troubleshooting
---------------
- If no logs appear:
  - Check Windows Event Viewer and Odoo logs.
  - Verify biometric.gateway_token in Odoo matches odoo_token in config.json.
  - Confirm the gateway machine has internet access to the Odoo URL.
  - Confirm devices respond on their /api endpoint and credentials are correct.

- If you change config.json:
  - Restart the Windows service to reload the configuration.

Security notes
--------------
- Keep config.json and the gateway_token secret.
- Prefer HTTPS for odoo_url in production (with valid TLS cert).
- Optionally restrict the Odoo route /biometric/gateway/push_logs by firewall
  (allow only the client gateway’s public IP).

End of README