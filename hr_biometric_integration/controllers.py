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

        Expected JSON body (flat), or JSON-RPC::

            {"gateway_token": "...", "device": {...}, "records": [...]}

            {"jsonrpc": "2.0", "method": "call",
             "params": {"gateway_token": "...", "device": {...}, "records": [...]},
             "id": null}

        Odoo 18+ JSON handlers put arguments in ``request.params`` only for the
        ``params`` object; the gateway sends a flat body, so we merge from the
        dispatcher's parsed JSON.
        """
        body = getattr(getattr(request, 'dispatcher', None), 'jsonrequest', None) or {}
        if isinstance(body.get('params'), dict):
            payload = dict(body['params'], **kwargs)
        else:
            skip = {'jsonrpc', 'method', 'id'}
            base = {k: v for k, v in body.items() if k not in skip}
            payload = {**base, **kwargs}

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

