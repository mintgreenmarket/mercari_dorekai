"""
Active/Passive failover guard.
- Active PC updates heartbeat and runs the job on a schedule.
- Passive PC takes over if heartbeat is stale.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from datetime import datetime, timezone
from pathlib import Path

# === Settings ===
SHARED_DIR = Path(r"H:\マイドライブ\mercari_dorekai")
HEARTBEAT_FILE = SHARED_DIR / "heartbeat.json"
OWNER_FILE = SHARED_DIR / "active_owner.json"
LAST_RUN_FILE = SHARED_DIR / "last_run.json"

STALE_MINUTES = 15
HEARTBEAT_INTERVAL_SEC = 60
JOB_INTERVAL_MINUTES = 30

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)
JOB_COMMAND = [sys.executable, str(BASE_DIR / "1_mercari_csv_download.py")]

HOSTNAME = socket.gethostname()

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


def send_slack(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
    except Exception:
        pass

def notify(text: str) -> None:
    send_slack(text)
    # keep console quiet


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def is_stale(ts_iso: str, stale_minutes: int) -> bool:
    try:
        ts = datetime.fromisoformat(ts_iso)
    except Exception:
        return True
    now = datetime.now(timezone.utc)
    return (now - ts).total_seconds() > stale_minutes * 60


def update_heartbeat(role: str) -> None:
    write_json(HEARTBEAT_FILE, {
        "host": HOSTNAME,
        "role": role,
        "time": utc_now_iso()
    })


def take_ownership(role: str) -> None:
    write_json(OWNER_FILE, {
        "host": HOSTNAME,
        "role": role,
        "since": utc_now_iso()
    })
    notify(f"[failover] role={role} host={HOSTNAME}")


def has_ownership() -> bool:
    owner = read_json(OWNER_FILE)
    return owner.get("host") == HOSTNAME


def should_run_job() -> bool:
    state = read_json(LAST_RUN_FILE)
    last = state.get("last_run")
    if not last:
        return True
    try:
        ts = datetime.fromisoformat(last)
    except Exception:
        return True
    now = datetime.now(timezone.utc)
    return (now - ts).total_seconds() >= JOB_INTERVAL_MINUTES * 60


def mark_job_run() -> None:
    write_json(LAST_RUN_FILE, {
        "last_run": utc_now_iso(),
        "host": HOSTNAME
    })


def run_job() -> None:
    try:
        notify(f"[failover] job start host={HOSTNAME}")
        subprocess.run(JOB_COMMAND, check=False)
    finally:
        mark_job_run()
        notify(f"[failover] job end host={HOSTNAME}")


def main(role: str) -> None:
    if not SHARED_DIR.exists():
        raise SystemExit(f"Shared folder not found: {SHARED_DIR}")

    current_role = role
    if role == "active":
        take_ownership("active")

    while True:
        hb = read_json(HEARTBEAT_FILE)
        hb_time = hb.get("time", "")
        hb_host = hb.get("host", "")

        if current_role == "passive":
            if not hb_time or is_stale(hb_time, STALE_MINUTES):
                take_ownership("passive-takeover")
                current_role = "active"
        else:
            # Active: if another host has a fresh heartbeat, drop to passive
            if hb_host and hb_host != HOSTNAME and hb_time and not is_stale(hb_time, STALE_MINUTES):
                current_role = "passive"
            else:
                update_heartbeat("active")

                if should_run_job():
                    run_job()

        time.sleep(HEARTBEAT_INTERVAL_SEC)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["active", "passive"], required=True)
    args = parser.parse_args()
    main(args.role)
