import win32serviceutil
import win32service
import win32event
import servicemanager
import time

from gateway_core import run_once, load_config

class BiometricGatewayService(win32serviceutil.ServiceFramework):
    _svc_name_ = "BiometricGatewayService"
    _svc_display_name_ = "Biometric Gateway Service"
    _svc_description_ = "Syncs biometric devices on LAN with cloud Odoo."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        self.main()

    def main(self):
        while self.running:
            try:
                run_once()
                cfg = load_config()
                sleep_sec = int(cfg.get("poll_interval_seconds", 60))
            except Exception:
                sleep_sec = 60

            # Wait with ability to stop early
            rc = win32event.WaitForSingleObject(self.stop_event, sleep_sec * 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(BiometricGatewayService)