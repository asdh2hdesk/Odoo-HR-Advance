# -*- coding: utf-8 -*-
"""Time Office <-> Odoo HR Attendance synchronization engine.

Architecture
------------
``TimeOfficeAdapter`` is a plain Python class (not an Odoo model) that
knows how to talk HTTP to *one* Time Office vendor's REST API: how to
authenticate, which endpoints to call and how to map the vendor's JSON
shape onto a normalized punch dict::

    {"employee_code": str, "check_in": datetime|None,
     "check_out": datetime|None, "raw": dict}

To support a different vendor in the future, only this adapter class
needs to change (endpoint URLs + ``_normalize_record``); the
``timeoffice.attendance.sync`` model and the rest of the module never
need to know about vendor-specific payload shapes.

``TimeOfficeAttendanceSync`` is the Odoo model that owns the business
logic: reading configuration, orchestrating a sync run, mapping punches
to employees, creating/updating ``hr.attendance`` records without
duplicates, and writing ``attendance.sync.log`` rows.
"""
import logging
import time
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - very old urllib3
    Retry = None

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"


class TimeOfficeAPIError(Exception):
    """Raised for any failure talking to the Time Office API.

    ``code`` is one of: unauthorized, forbidden, not_found, timeout,
    server_error, network_error, invalid_json, unknown.
    """

    def __init__(self, message, code="unknown", status_code=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class TimeOfficeAdapter:
    """Thin REST client for the Time Office API.

    Vendor-specific integrations should subclass this and override
    ``_normalize_record`` / endpoint building if the payload shape
    differs from the default one documented in the module README.
    """

    def __init__(
        self,
        base_url,
        auth_type="api_key",
        username=None,
        password=None,
        api_key=None,
        bearer_token=None,
        attendance_endpoint="/api/attendance",
        employee_endpoint="/api/employees",
        company_code=None,
        timeout=DEFAULT_TIMEOUT,
        max_retries=DEFAULT_MAX_RETRIES,
    ):
        if not base_url:
            raise TimeOfficeAPIError(
                _("Time Office API Base URL is not configured."),
                code="not_configured",
            )
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type or "api_key"
        self.username = username
        self.password = password
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.attendance_endpoint = attendance_endpoint or "/api/attendance"
        self.employee_endpoint = employee_endpoint or "/api/employees"
        self.company_code = company_code
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.max_retries = max_retries or DEFAULT_MAX_RETRIES
        self.session = requests.Session()
        if Retry is not None:
            retry = Retry(
                total=self.max_retries,
                backoff_factor=0.5,
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=frozenset(["GET", "POST"]),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def authenticate(self):
        """Prepare the session so subsequent calls are authenticated.

        Returns True on success. Raises TimeOfficeAPIError on failure.
        """
        try:
            if self.auth_type == "basic":
                if not (self.username and self.password):
                    raise TimeOfficeAPIError(
                        _("Username and Password are required for Basic "
                          "Authentication."),
                        code="not_configured",
                    )
                self.session.auth = (self.username, self.password)
            elif self.auth_type == "jwt":
                if not self.bearer_token:
                    raise TimeOfficeAPIError(
                        _("Bearer Token is required for JWT "
                          "Authentication."),
                        code="not_configured",
                    )
                self.session.headers.update(self.get_headers())
            elif self.auth_type == "api_key":
                if not self.api_key:
                    raise TimeOfficeAPIError(
                        _("API Key is required for API Key "
                          "Authentication."),
                        code="not_configured",
                    )
                self.session.headers.update(self.get_headers())
            else:
                raise TimeOfficeAPIError(
                    _("Unsupported authentication type: %s") % self.auth_type,
                    code="not_configured",
                )
        except TimeOfficeAPIError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise TimeOfficeAPIError(str(exc), code="unknown") from exc
        return True

    def get_headers(self):
        """Build the (non-auth-library) headers required for this
        session's authentication type."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.auth_type == "api_key" and self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.auth_type == "jwt" and self.bearer_token:
            headers["Authorization"] = "Bearer %s" % self.bearer_token
        if self.company_code:
            headers["X-Company-Code"] = self.company_code
        return headers

    # ------------------------------------------------------------------
    # Low level request helper
    # ------------------------------------------------------------------
    def _url(self, endpoint):
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return "%s/%s" % (self.base_url, endpoint.lstrip("/"))

    def _request(self, method, endpoint, params=None, json_body=None):
        url = self._url(endpoint)
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise TimeOfficeAPIError(
                _("Request to %s timed out after %s seconds.")
                % (url, self.timeout),
                code="timeout",
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise TimeOfficeAPIError(
                _("Could not reach the Time Office server at %s.") % url,
                code="network_error",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise TimeOfficeAPIError(str(exc), code="network_error") from exc

        if response.status_code == 401:
            raise TimeOfficeAPIError(
                _("Invalid credentials (401 Unauthorized)."),
                code="unauthorized",
                status_code=401,
            )
        if response.status_code == 403:
            raise TimeOfficeAPIError(
                _("Access forbidden (403 Forbidden)."),
                code="forbidden",
                status_code=403,
            )
        if response.status_code == 404:
            raise TimeOfficeAPIError(
                _("Endpoint not found (404): %s") % url,
                code="not_found",
                status_code=404,
            )
        if response.status_code == 408:
            raise TimeOfficeAPIError(
                _("Server reported a request timeout (408)."),
                code="timeout",
                status_code=408,
            )
        if response.status_code >= 500:
            raise TimeOfficeAPIError(
                _("Time Office server error (%s).") % response.status_code,
                code="server_error",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise TimeOfficeAPIError(
                _("Unexpected HTTP error (%s): %s")
                % (response.status_code, response.text[:300]),
                code="unknown",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise TimeOfficeAPIError(
                _("Could not parse JSON response from %s.") % url,
                code="invalid_json",
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def test_connection(self):
        """Lightweight call used by the 'Test Connection' button.

        Tries the employee endpoint with a tiny page size; any
        response that isn't an auth/network error counts as success.
        """
        self.authenticate()
        self._request(
            "GET", self.employee_endpoint, params={"limit": 1, "page": 1}
        )
        return True

    def get_employee(self, employee_code):
        """Fetch a single employee's details from the Time Office API
        (optional enrichment / validation hook for future vendors)."""
        self.authenticate()
        return self._request(
            "GET", self.employee_endpoint, params={"employee_code": employee_code}
        )

    def get_attendance(self, since=None):
        """Fetch attendance punches created/updated after ``since``
        (a naive UTC datetime). Returns a normalized list of dicts.
        """
        self.authenticate()
        params = {}
        if since:
            params["since"] = since.strftime(DATETIME_FMT)
        if self.company_code:
            params["company_code"] = self.company_code
        payload = self._request("GET", self.attendance_endpoint, params=params)
        records = self._extract_records(payload)
        normalized = []
        for raw in records:
            try:
                normalized.append(self._normalize_record(raw))
            except (KeyError, ValueError, TypeError) as exc:
                _logger.warning(
                    "Time Office: could not normalize record %s (%s)",
                    raw,
                    exc,
                )
        return normalized

    # ------------------------------------------------------------------
    # Mapping helpers - override per vendor if needed
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_records(payload):
        """Vendors wrap the list differently (bare list, {"data": [...]},
        {"results": [...]}, ...). Normalize to a plain list here."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "results", "records", "attendance"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return []

    @staticmethod
    def _parse_dt(value):
        if not value:
            return None
        value = value.replace("Z", "")
        for fmt in (DATETIME_FMT, "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt)
            except ValueError:
                continue
        raise ValueError("Unrecognized datetime format: %s" % value)

    def _normalize_record(self, raw):
        """Map one vendor JSON record to the normalized punch dict.

        Default mapping matches the module's documented payload:
        ``{"employee_code": ..., "check_in": ..., "check_out": ...}``.
        Override this method for a vendor with a different shape.
        """
        employee_code = raw.get("employee_code") or raw.get("emp_code")
        if not employee_code:
            raise KeyError("employee_code")
        return {
            "employee_code": str(employee_code),
            "check_in": self._parse_dt(raw.get("check_in")),
            "check_out": self._parse_dt(raw.get("check_out")),
            "raw": raw,
        }


class TimeOfficeAttendanceSync(models.Model):
    """Business logic: configuration access, sync orchestration and
    employee/attendance matching. Exposed to cron, the 'Sync Now'
    button and the 'Test Connection' button."""

    _name = "timeoffice.attendance.sync"
    _description = "Time Office Attendance Sync Engine"

    # ------------------------------------------------------------------
    # Configuration access (ir.config_parameter, set via res.config.settings)
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(
            "timeoffice_attendance_sync.%s" % key, default
        )

    @api.model
    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "timeoffice_attendance_sync.%s" % key, value or ""
        )

    @api.model
    def _build_adapter(self):
        return TimeOfficeAdapter(
            base_url=self._get_param("api_base_url"),
            auth_type=self._get_param("auth_type", "api_key"),
            username=self._get_param("username"),
            password=self._get_param("password"),
            api_key=self._get_param("api_key"),
            bearer_token=self._get_param("bearer_token"),
            attendance_endpoint=self._get_param(
                "attendance_endpoint", "/api/attendance"
            ),
            employee_endpoint=self._get_param(
                "employee_endpoint", "/api/employees"
            ),
            company_code=self._get_param("company_code"),
        )

    # ------------------------------------------------------------------
    # Test Connection
    # ------------------------------------------------------------------
    @api.model
    def test_connection(self):
        """Returns (success: bool, message: str)."""
        try:
            adapter = self._build_adapter()
            adapter.test_connection()
            return True, _("Connection Successful")
        except TimeOfficeAPIError as exc:
            _logger.warning("Time Office test connection failed: %s", exc)
            return False, self._friendly_error(exc)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("Time Office test connection unexpected error")
            return False, _("Unexpected error: %s") % exc

    @api.model
    def _friendly_error(self, exc):
        mapping = {
            "unauthorized": _("Invalid Credentials"),
            "forbidden": _("Access Forbidden"),
            "not_found": _("Endpoint Not Found"),
            "timeout": _("Server Unreachable (Timeout)"),
            "network_error": _("Server Unreachable"),
            "server_error": _("Time Office Server Error"),
            "invalid_json": _("Invalid Response From Server"),
            "not_configured": exc.message,
        }
        return mapping.get(exc.code, exc.message)

    # ------------------------------------------------------------------
    # Sync orchestration
    # ------------------------------------------------------------------
    @api.model
    def sync_attendance(self, manual=False):
        """Run one synchronization pass. Never raises to the caller for
        per-record problems; only configuration-level failures (bad
        credentials, unreachable server) abort the whole run - and even
        then the exception is caught by cron_sync_attendance().

        Returns a summary dict: imported / skipped / failed / duration.
        """
        start = time.time()
        summary = {"imported": 0, "skipped": 0, "failed": 0, "duration": 0.0}

        try:
            adapter = self._build_adapter()
            adapter.authenticate()
        except TimeOfficeAPIError as exc:
            _logger.error("Time Office sync aborted: %s", exc)
            self._log_run_error(exc)
            summary["duration"] = time.time() - start
            summary["error"] = self._friendly_error(exc)
            return summary

        last_sync = self._get_last_sync_datetime()
        try:
            punches = adapter.get_attendance(since=last_sync)
        except TimeOfficeAPIError as exc:
            _logger.error("Time Office sync fetch failed: %s", exc)
            self._log_run_error(exc)
            summary["duration"] = time.time() - start
            summary["error"] = self._friendly_error(exc)
            return summary

        _logger.info(
            "Time Office sync: %s punch(es) fetched since %s (manual=%s)",
            len(punches),
            last_sync,
            manual,
        )

        for punch in punches:
            status = self._process_punch(punch)
            summary[status] = summary.get(status, 0) + 1

        self._set_param("last_sync_time", fields.Datetime.now())
        summary["duration"] = round(time.time() - start, 2)
        _logger.info(
            "Time Office sync finished: imported=%s skipped=%s failed=%s "
            "duration=%ss",
            summary["imported"],
            summary["skipped"],
            summary["failed"],
            summary["duration"],
        )
        return summary

    @api.model
    def _get_last_sync_datetime(self):
        raw = self._get_param("last_sync_time")
        if not raw:
            return None
        try:
            return fields.Datetime.from_string(raw)
        except Exception:  # pragma: no cover - defensive
            return None

    @api.model
    def _log_run_error(self, exc):
        self.env["attendance.sync.log"].sudo().create(
            {
                "status": "failed",
                "error_message": self._friendly_error(exc),
                "sync_time": fields.Datetime.now(),
            }
        )

    # ------------------------------------------------------------------
    # Per-punch processing
    # ------------------------------------------------------------------
    @api.model
    def _process_punch(self, punch):
        """Match employee, create/update hr.attendance, write a sync
        log row. Returns 'imported', 'skipped' or 'failed'."""
        Log = self.env["attendance.sync.log"].sudo()
        employee_code = punch.get("employee_code")
        check_in = punch.get("check_in")
        check_out = punch.get("check_out")
        log_vals = {
            "employee_code": employee_code,
            "check_in": check_in,
            "check_out": check_out,
            "api_response": str(punch.get("raw")),
            "sync_time": fields.Datetime.now(),
        }

        employee = self._find_employee(employee_code)
        if not employee:
            log_vals.update(
                status="failed",
                error_message=_(
                    "No employee found with biometric_code '%s'."
                )
                % employee_code,
            )
            Log.create(log_vals)
            _logger.error(
                "Time Office sync: unmapped employee_code=%s", employee_code
            )
            return "failed"
        log_vals["employee_id"] = employee.id

        if not check_in and not check_out:
            log_vals.update(
                status="failed",
                error_message=_("Record has neither check_in nor check_out."),
            )
            Log.create(log_vals)
            return "failed"

        try:
            attendance, created = self._create_or_update_attendance(
                employee, check_in, check_out
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception(
                "Time Office sync: failed to write attendance for %s",
                employee_code,
            )
            log_vals.update(status="failed", error_message=str(exc))
            Log.create(log_vals)
            return "failed"

        if attendance is None:
            # Duplicate check-in with nothing new to update.
            log_vals["status"] = "skipped"
            Log.create(log_vals)
            return "skipped"

        log_vals.update(status="success", attendance_id=attendance.id)
        Log.create(log_vals)
        return "imported"

    @api.model
    def _find_employee(self, employee_code):
        if not employee_code:
            return None
        return (
            self.env["hr.employee"]
            .sudo()
            .search([("biometric_code", "=", employee_code)], limit=1)
        )

    @api.model
    def _create_or_update_attendance(self, employee, check_in, check_out):
        """Create or update hr.attendance for one punch, handling:
        - duplicate check-ins (skip)
        - a checkout arriving for an existing open check-in (update)
        - overnight shifts / multiple punches (a new open attendance
          is only opened if the employee has no currently open one)
        - missing checkout (record is created open, closed by a later
          sync when the checkout punch arrives)

        Returns (attendance_record_or_None, created_bool).
        """
        Attendance = self.env["hr.attendance"].sudo()

        if check_in:
            duplicate = Attendance.search(
                [
                    ("employee_id", "=", employee.id),
                    ("check_in", "=", check_in),
                ],
                limit=1,
            )
            if duplicate:
                if check_out and not duplicate.check_out:
                    duplicate.write({"check_out": check_out})
                    return duplicate, False
                # Already imported and nothing new - skip.
                return None, False

            vals = {"employee_id": employee.id, "check_in": check_in}
            if check_out:
                vals["check_out"] = check_out
            attendance = Attendance.create(vals)
            return attendance, True

        # Only a check_out was received (e.g. late punch for an
        # overnight shift): attach it to the employee's currently
        # open attendance, if any.
        open_attendance = Attendance.search(
            [("employee_id", "=", employee.id), ("check_out", "=", False)],
            order="check_in desc",
            limit=1,
        )
        if open_attendance:
            open_attendance.write({"check_out": check_out})
            return open_attendance, False

        _logger.warning(
            "Time Office sync: check_out received for employee %s with "
            "no open attendance; ignoring.",
            employee.id,
        )
        return None, False

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------
    @api.model
    def cron_sync_attendance(self):
        """Scheduled entry point. Must never let one bad run take the
        scheduler down."""
        if self._get_param("enable_auto_sync", "1") not in ("1", "True", "true"):
            _logger.info("Time Office: automatic sync is disabled, skipping.")
            return
        try:
            self.sync_attendance(manual=False)
        except Exception:  # pragma: no cover - safety net for the cron
            _logger.exception(
                "Time Office cron sync failed with an unexpected error"
            )

    # ------------------------------------------------------------------
    # Dashboard helpers
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self):
        Log = self.env["attendance.sync.log"].sudo()
        today_start = fields.Datetime.to_string(
            datetime.combine(fields.Date.today(), datetime.min.time())
        )
        imported_today = Log.search_count(
            [("status", "=", "success"), ("sync_time", ">=", today_start)]
        )
        failed_records = Log.search_count(
            [("status", "=", "failed"), ("sync_time", ">=", today_start)]
        )
        last_sync = self._get_param("last_sync_time") or _("Never")
        return {
            "imported_today": imported_today,
            "failed_records": failed_records,
            "last_sync_time": last_sync,
            "pending_records": 0,
        }
