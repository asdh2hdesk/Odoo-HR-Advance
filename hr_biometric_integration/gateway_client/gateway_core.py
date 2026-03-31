import json
import time
import pathlib
from typing import Dict, Any, List, Optional

import requests

# Adjust this on Windows if needed; in the addon keep it as documentation
BASE_DIR = pathlib.Path(r"C:\BiometricGateway")
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "gateway_state.json"


def load_config() -> Dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    with STATE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]) -> None:
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def fetch_device_logs(device: Dict[str, Any], last_from: Optional[str]) -> List[Dict[str, Any]]:
    """Pull logs from one biometric device using its /api endpoint."""
    url = f"http://{device['ip']}/api"
    index = 0
    all_records: List[Dict[str, Any]] = []

    while True:
        payload: Dict[str, Any] = {
            "password": device["password"],
            "cmd": "getlog",
            "index": index,
        }
        if last_from:
            payload["from"] = last_from

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            # device unreachable or bad response, stop this cycle
            break

        records = data.get("record", [])
        if not records:
            break

        all_records.extend(records)

        to_idx = data.get("to", 0)
        count = data.get("count", 0)
        if to_idx + 1 >= count:
            break
        index = to_idx + 1

    return all_records


def push_to_odoo(odoo_url: str, token: str, device: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    """Send collected records to Odoo gateway controller."""
    if not records:
        return

    payload = {
        "gateway_token": token,
        "device": {
            "name": device["name"],
            "ip": device["ip"],
            "type": device["type"],
        },
        "records": records,
    }

    url = f"{odoo_url.rstrip('/')}/biometric/gateway/push_logs"
    requests.post(url, json=payload, timeout=20)


def run_once() -> None:
    """Run one full poll cycle across all devices."""
    cfg = load_config()
    state = load_state()

    odoo_url = cfg["odoo_url"]
    token = cfg["odoo_token"]

    for device in cfg.get("devices", []):
        key = device["ip"]
        last_from = state.get(key, {}).get("from")

        records = fetch_device_logs(device, last_from)

        if records:
            # adjust if your device uses a different field than "time"
            last_time = records[-1].get("time") or records[-1].get("timestamp")
            if last_time:
                state[key] = {"from": last_time}

        try:
            push_to_odoo(odoo_url, token, device, records)
        except Exception:
            # in real code, log the error somewhere
            pass

    save_state(state)


def main_loop() -> None:
    """Standalone runner (useful for debugging without Windows service)."""
    while True:
        try:
            cfg = load_config()
            interval = int(cfg.get("poll_interval_seconds", 60))
        except Exception:
            interval = 60

        run_once()
        time.sleep(interval)


if __name__ == "__main__":
    main_loop()