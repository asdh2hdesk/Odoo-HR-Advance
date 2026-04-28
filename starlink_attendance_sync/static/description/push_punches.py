"""
StarLink → Odoo push agent (runs on the local PC at the client site).

Two modes:

    LIVE  (default, every 5 min via Task Scheduler)
        WHERE OFFICEPUNCH > live_pull_checkpoint  TOP 1000
        Catches: new punches happening right now.

    RETRO  (daily at 03:00 + ad-hoc before payroll close)
        WHERE OFFICEPUNCH >= NOW - RETRO_DAYS      (no TOP cap, no checkpoint)
        Catches: punches that managers ADDED to MachineRawPunch with a
                 past timestamp (e.g., end-of-month corrections).
        Idempotent: the (badge, punch_time, company) unique constraint
                 silently dedupes already-imported rows.

Both modes ingest into ``starlink.sync.log`` with ``defer_pairing=True``;
Odoo's live-refresh cron does the IN/OUT pairing.

Run examples:
    python push_punches.py                 # live mode
    python push_punches.py --retro         # 35-day re-scan (default RETRO_DAYS)
    python push_punches.py --retro --days 60   # custom window for month-end

Logs to:  C:\\StarlinkSync\\push.log
"""

import argparse
import logging
import os
import socket
import time
import xmlrpc.client
from datetime import datetime, timedelta

import pyodbc

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
URL = 'http://20.193.254.185:8070'
DB = 'german_main'
USERNAME = 'admin'
PASSWORD = 'Admin#TMT!@2026'

SQL_CONN = (
    r"DRIVER={SQL Server Native Client 10.0};"
    r"SERVER=HSML-PC\SQLEXPRESS;"
    r"DATABASE=StarSql;"
    r"UID=sa;"
    r"PWD=star@123;"
)

LIVE_BATCH_SIZE = 1000        # rows per live run
RETRO_BATCH_SIZE = 50000      # safety cap on retro pulls (35d × ~1000 punches/day)
RETRO_DAYS_DEFAULT = 35       # cover full payroll cycle
RETRY_ATTEMPTS = 3
RETRY_DELAY_S = 2
LOG_DIR = r'C:\StarlinkSync'
IST_OFFSET = timedelta(hours=5, minutes=30)

socket.setdefaulttimeout(120)

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'push.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('starlink_push')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description='StarLink → Odoo push agent')
mode_grp = parser.add_mutually_exclusive_group()
mode_grp.add_argument('--retro', action='store_true',
                      help='Retro mode: re-scan last N days, ignore live checkpoint.')
mode_grp.add_argument('--scrub', action='store_true',
                      help='Scrub mode: find Odoo logs whose SQL Server source row '
                           'was deleted/edited, flag them as ingestion_error.')
parser.add_argument('--days', type=int, default=RETRO_DAYS_DEFAULT,
                    help=f'Window in days for retro/scrub (default {RETRO_DAYS_DEFAULT}).')
parser.add_argument('--batch', type=int,
                    help='Override batch size (default: 1000 live, 50000 retro).')
args = parser.parse_args()

if args.retro:
    MODE = 'retro'
elif args.scrub:
    MODE = 'scrub'
else:
    MODE = 'live'
BATCH_SIZE = args.batch or (RETRO_BATCH_SIZE if args.retro else LIVE_BATCH_SIZE)


# ---------------------------------------------------------------------------
# Retry wrapper for XML-RPC transient errors
# ---------------------------------------------------------------------------
def with_retry(label, fn, *fargs, **fkwargs):
    """Retry a callable up to RETRY_ATTEMPTS on network/protocol errors."""
    last = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return fn(*fargs, **fkwargs)
        except (xmlrpc.client.ProtocolError, OSError, ConnectionError) as exc:
            last = exc
            log.warning(
                "%s attempt %d/%d failed: %s",
                label, attempt, RETRY_ATTEMPTS, exc,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_S * attempt)
    raise last


# ---------------------------------------------------------------------------
# Odoo connection
# ---------------------------------------------------------------------------
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = with_retry('authenticate', common.authenticate, DB, USERNAME, PASSWORD, {})
if not uid:
    log.critical("[%s] Odoo authentication failed; aborting", MODE)
    raise SystemExit(1)
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
log.info("[%s] Connected to Odoo as uid=%s", MODE, uid)


def odoo(model, method, oargs, okwargs=None):
    """Convenience wrapper around models.execute_kw with retry."""
    return with_retry(
        f'{model}.{method}',
        models.execute_kw,
        DB, uid, PASSWORD, model, method, oargs, okwargs or {},
    )


# ---------------------------------------------------------------------------
# Helper: push exception (never let it itself fail the run)
# ---------------------------------------------------------------------------
def push_exception(badge, punch_time, issue, company_id, notes=''):
    try:
        vals = {
            'badge_code': badge or '?',
            'issue_type': issue,
            'company_id': company_id,
            'resolution_notes': notes,
        }
        if punch_time:
            vals['punch_time'] = (
                punch_time.strftime('%Y-%m-%d %H:%M:%S')
                if isinstance(punch_time, datetime) else punch_time
            )
        odoo('starlink.punch.exception', 'create', [vals])
    except Exception as exc:           # noqa: BLE001
        log.error("push_exception failed (suppressed): %s", exc)


# ---------------------------------------------------------------------------
# Resolve company
# ---------------------------------------------------------------------------
companies = odoo(
    'res.company', 'search_read', [[]],
    {'fields': ['id', 'name'], 'limit': 1, 'order': 'id'},
)
if not companies:
    log.critical("[%s] No company found in Odoo", MODE)
    raise SystemExit(1)
COMPANY_ID = companies[0]['id']
log.info("[%s] Target company: id=%s name=%s", MODE, COMPANY_ID, companies[0]['name'])


# ---------------------------------------------------------------------------
# Scrub mode — runs to completion and exits
# ---------------------------------------------------------------------------
if MODE == 'scrub':
    since_ist = datetime.now() - timedelta(days=args.days)
    log.info("[scrub] Comparing window from %s (IST) for %d days",
             since_ist, args.days)

    # 1. Pull SQL Server set: {(badge, punch_time_ist) -> inout}
    try:
        conn = pyodbc.connect(SQL_CONN, timeout=30)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT RTRIM(CARDNO), OFFICEPUNCH, INOUT
            FROM MachineRawPunch
            WHERE OFFICEPUNCH >= ?
            """,
            since_ist,
        )
        sql_rows = cursor.fetchall()
        conn.close()
    except pyodbc.Error as exc:
        log.exception("[scrub] SQL Server fetch failed")
        push_exception('SYSTEM', datetime.now(), 'ingestion_error', COMPANY_ID,
                       f"[scrub] SQL Server unreachable: {exc}")
        raise SystemExit(2)

    sql_set = {}
    for r in sql_rows:
        badge = (r[0] or '').strip()
        dt = r[1]
        io = (r[2] or '').strip().upper()
        if badge and dt and io in ('I', 'O'):
            sql_set[(badge, dt.replace(microsecond=0))] = io
    log.info("[scrub] SQL has %d rows in window", len(sql_set))

    # 2. Pull Odoo set in same window (UTC stored)
    since_utc_str = (since_ist - IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S')
    odoo_logs = odoo(
        'starlink.sync.log', 'search_read',
        [[('punch_time', '>=', since_utc_str), ('company_id', '=', COMPANY_ID)]],
        {'fields': ['id', 'badge_code', 'punch_time', 'inout',
                    'sync_status', 'attendance_id'],
         'limit': 100000},
    )
    log.info("[scrub] Odoo has %d sync.log rows in window", len(odoo_logs))

    # 3. Compare
    deleted = edited = 0
    for olog in odoo_logs:
        # punch_time string → datetime, UTC → IST
        pt_utc = datetime.strptime(olog['punch_time'], '%Y-%m-%d %H:%M:%S')
        pt_ist = (pt_utc + IST_OFFSET).replace(microsecond=0)
        key = (olog['badge_code'], pt_ist)
        if key not in sql_set:
            deleted += 1
            push_exception(
                badge=olog['badge_code'], punch_time=olog['punch_time'],
                issue='ingestion_error', company_id=COMPANY_ID,
                notes=(f"[scrub] Source row deleted from MachineRawPunch. "
                       f"Odoo log id={olog['id']} status={olog['sync_status']} "
                       f"attendance_id={olog['attendance_id']}"),
            )
        elif sql_set[key] != olog['inout']:
            edited += 1
            push_exception(
                badge=olog['badge_code'], punch_time=olog['punch_time'],
                issue='ingestion_error', company_id=COMPANY_ID,
                notes=(f"[scrub] inout drift: SQL={sql_set[key]} "
                       f"Odoo={olog['inout']} (id={olog['id']})"),
            )

    log.info("[scrub] Done. odoo_rows=%d deleted=%d edited=%d",
             len(odoo_logs), deleted, edited)
    raise SystemExit(0)


# ---------------------------------------------------------------------------
# Determine the SQL window
# ---------------------------------------------------------------------------
cp_id = None
if MODE == 'live':
    cps = odoo(
        'starlink.sync.checkpoint', 'search_read',
        [[('name', '=', 'live_pull'), ('company_id', '=', COMPANY_ID)]],
        {'fields': ['id', 'last_sync_at'], 'limit': 1},
    )
    if cps and cps[0]['last_sync_at']:
        last_utc = datetime.strptime(cps[0]['last_sync_at'], '%Y-%m-%d %H:%M:%S')
        # Odoo stores UTC; SQL Server stores IST → convert
        since_ist = last_utc + IST_OFFSET
        cp_id = cps[0]['id']
    else:
        since_ist = datetime.now() - timedelta(days=1)
    log.info("[live] Pulling OFFICEPUNCH > %s (IST), TOP %d", since_ist, BATCH_SIZE)
else:
    # Retro mode: full N-day window, ignore live checkpoint
    since_ist = datetime.now() - timedelta(days=args.days)
    log.info("[retro] Pulling OFFICEPUNCH >= %s (IST), TOP %d (last %d days)",
             since_ist, BATCH_SIZE, args.days)


# ---------------------------------------------------------------------------
# Fetch from SQL Server
# ---------------------------------------------------------------------------
try:
    conn = pyodbc.connect(SQL_CONN, timeout=30)
    cursor = conn.cursor()
    if MODE == 'live':
        cursor.execute(
            f"""
            SELECT TOP {BATCH_SIZE}
                RTRIM(CARDNO), OFFICEPUNCH, INOUT, MACHINENO
            FROM MachineRawPunch
            WHERE OFFICEPUNCH > ?
            ORDER BY OFFICEPUNCH ASC
            """,
            since_ist,
        )
    else:
        cursor.execute(
            f"""
            SELECT TOP {BATCH_SIZE}
                RTRIM(CARDNO), OFFICEPUNCH, INOUT, MACHINENO
            FROM MachineRawPunch
            WHERE OFFICEPUNCH >= ?
            ORDER BY OFFICEPUNCH ASC
            """,
            since_ist,
        )
    rows = cursor.fetchall()
    conn.close()
    log.info("[%s] Fetched %d rows from SQL Server", MODE, len(rows))
except pyodbc.Error as exc:
    log.exception("[%s] SQL Server fetch failed", MODE)
    push_exception(
        badge='SYSTEM', punch_time=datetime.now(),
        issue='ingestion_error', company_id=COMPANY_ID,
        notes=f"[{MODE}] SQL Server unreachable: {exc}",
    )
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# Push each row
# ---------------------------------------------------------------------------
created = skipped_dupe = bad_rows = 0
last_pushed_ist = None

for row in rows:
    badge = (row[0] or '').strip()
    punch_dt_ist = row[1]
    inout = (row[2] or '').strip().upper()
    machine = str(row[3]) if len(row) > 3 and row[3] is not None else False

    if not badge or not punch_dt_ist or inout not in ('I', 'O'):
        bad_rows += 1
        push_exception(
            badge=badge or 'NULL',
            punch_time=punch_dt_ist or datetime.now(),
            issue='ingestion_error',
            company_id=COMPANY_ID,
            notes=f"[{MODE}] Malformed: badge={badge!r} dt={punch_dt_ist!r} io={inout!r}",
        )
        continue

    utc_str = (punch_dt_ist - IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S')
    vals = {
        'badge_code': badge,
        'punch_time': utc_str,
        'inout': inout,
        'machine_id': machine,
        'company_id': COMPANY_ID,
    }
    try:
        odoo(
            'starlink.sync.log', 'create',
            [vals],
            {'context': {'starlink_defer_pairing': True}},
        )
        created += 1
        last_pushed_ist = punch_dt_ist
    except xmlrpc.client.Fault as exc:
        msg = str(exc)
        if 'uniq_punch' in msg or 'duplicate' in msg.lower():
            skipped_dupe += 1
            last_pushed_ist = punch_dt_ist
        else:
            log.error("[%s] create failed for %s @ %s: %s",
                      MODE, badge, utc_str, exc)
            push_exception(
                badge=badge, punch_time=punch_dt_ist,
                issue='ingestion_error', company_id=COMPANY_ID,
                notes=f"[{MODE}] XML-RPC create failed: {msg[:200]}",
            )


# ---------------------------------------------------------------------------
# Update checkpoints
# ---------------------------------------------------------------------------
if MODE == 'live' and last_pushed_ist:
    last_utc_str = (last_pushed_ist - IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S')
    if cp_id:
        odoo('starlink.sync.checkpoint', 'write',
             [[cp_id], {'last_sync_at': last_utc_str}])
    else:
        odoo('starlink.sync.checkpoint', 'create',
             [{'name': 'live_pull', 'company_id': COMPANY_ID,
               'last_sync_at': last_utc_str}])
    log.info("[live] Checkpoint live_pull advanced to %s UTC", last_utc_str)

elif MODE == 'retro':
    # Track when the last retro sweep ran — does NOT affect the live checkpoint.
    retro_now = datetime.now() - IST_OFFSET   # UTC
    cps = odoo(
        'starlink.sync.checkpoint', 'search',
        [[('name', '=', 'retro_pull'), ('company_id', '=', COMPANY_ID)]],
        {'limit': 1},
    )
    retro_vals = {
        'last_sync_at': retro_now.strftime('%Y-%m-%d %H:%M:%S'),
        'retro_window_start': (
            (datetime.now() - timedelta(days=args.days) - IST_OFFSET)
            .strftime('%Y-%m-%d %H:%M:%S')
        ),
    }
    if cps:
        odoo('starlink.sync.checkpoint', 'write', [cps, retro_vals])
    else:
        odoo('starlink.sync.checkpoint', 'create',
             [{**retro_vals, 'name': 'retro_pull', 'company_id': COMPANY_ID}])
    log.info("[retro] Checkpoint retro_pull stamped at %s UTC", retro_vals['last_sync_at'])

    # Trigger Odoo to re-pair anything pending (catches retro inserts immediately)
    try:
        odoo('starlink.sync.engine', '_cron_live_refresh', [])
        log.info("[retro] Triggered Odoo live-refresh to pair retro punches")
    except Exception as exc:           # noqa: BLE001
        log.warning("[retro] Could not trigger live-refresh: %s", exc)

log.info(
    "[%s] Done. fetched=%d created=%d duplicates=%d bad_rows=%d",
    MODE, len(rows), created, skipped_dupe, bad_rows,
)
