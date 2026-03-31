from odoo import http
from odoo.http import request


class BiometricGatewayController(http.Controller):

    @http.route(
        '/biometric/gateway/push_logs',
        type='json',
        auth='none',
        csrf=False,
        methods=['POST'],
    )
    def biometric_gateway_push_logs(self, **kwargs):
        """Endpoint for on‑prem gateway to push device logs.

        Expected JSON body:
        {
            "gateway_token": "...",
            "device": {...},
            "records": [...]
        }
        """
        payload = request.jsonrequest or {}

        token = payload.get('gateway_token')
        expected = request.env['ir.config_parameter'].sudo().get_param(
            'biometric.gateway_token'
        )

        if not expected or token != expected:
            return {
                'status': 'error',
                'message': 'Invalid gateway token',
            }

        device_data = payload.get('device') or {}
        records = payload.get('records') or []

        # Delegate to model logic (handles device creation, dedup, attendance)
        request.env['biometric.log'].sudo().process_gateway_payload(
            device_data, records
        )

        return {
            'status': 'ok',
            'message': f'Processed {len(records)} records',
        }

