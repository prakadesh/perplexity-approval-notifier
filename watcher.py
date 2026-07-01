import time
import argparse
import requests
from datetime import datetime

try:
    from winotify import Notification, audio
    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
NTFY_TOPIC        = "perplexity-prakadesh-alert"
NTFY_SERVER       = "https://ntfy.sh"
CHECK_INTERVAL    = 3      # seconds between scans
REMINDER_INTERVAL = 120    # seconds — re-alert if popup still not dismissed
MAX_BTN_LEN       = 30     # UI elements longer than this are page content

# Alert fires ONLY when ALL three are present in the same window at once.
REQUIRED_COMBO = {"Awaiting response", "Approve", "Deny"}
# ─────────────────────────────────────────────

DEBUG   = False
VERBOSE = False


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str):
    icons = {"INFO": "ℹ️ ", "DEBUG": "🔍", "ALERT": "🚨",
             "WARN": "⚠️ ", "ERROR": "❌", "OK": "✅", "REMIND": "🔁"}
    print(f"[{ts()}] {icons.get(level, '  ')} [{level}] {msg}")


def get_perplexity_windows():
    try:
        from pywinauto import Desktop
        matched = [w for w in Desktop(backend="uia").windows()
                   if "Perplexity" in w.window_text()]
        if DEBUG:
            log("DEBUG", f"Found {len(matched)} Perplexity window(s):")
            for i, w in enumerate(matched):
                print(f"         [{i+1}] \"{w.window_text()}\"  "
                      f"[class: {w.class_name()}]  [handle: {w.handle}]")
        return matched
    except Exception as e:
        log("ERROR", f"Could not enumerate windows: {e}")
        return []


def collect_short_texts(win) -> set:
    short_texts = set()
    skipped = 0
    all_short = []
    try:
        for elem in win.descendants():
            try:
                text = elem.window_text().strip()
                if not text:
                    continue
                if len(text) > MAX_BTN_LEN or any(c in text for c in [".", "!", "?", "\n"]):
                    skipped += 1
                    continue
                short_texts.add(text)
                all_short.append(text)
            except Exception:
                pass
    except Exception as e:
        log("ERROR", f"Error scanning descendants: {e}")

    if DEBUG:
        log("DEBUG", f"  └─ {len(short_texts)} short elements | {skipped} long/sentence skipped")
        for item in REQUIRED_COMBO:
            marker = "✅" if item in short_texts else "❌"
            print(f"         {marker} REQUIRED: {repr(item)}")
        if VERBOSE:
            log("DEBUG", "  └─ All short elements (--verbose):")
            for t in all_short:
                print(f"           └─ {repr(t)}")
    return short_texts


def check_perplexity_waiting() -> bool:
    windows = get_perplexity_windows()
    if not windows:
        log("WARN", "No Perplexity window open.") if DEBUG else None
        return False
    for i, win in enumerate(windows):
        title = win.window_text()
        if DEBUG:
            log("DEBUG", f"Scanning window [{i+1}/{len(windows)}]: \"{title}\"")
        short_texts = collect_short_texts(win)
        missing = REQUIRED_COMBO - short_texts
        if not missing:
            log("ALERT", f"Popup confirmed in \"{title}\"") if DEBUG else None
            return True
        else:
            log("DEBUG", f"  └─ Combo incomplete, missing: {missing}") if DEBUG else None
    return False


def list_open_windows():
    try:
        from pywinauto import Desktop
        log("DEBUG", "─── All open windows ───")
        for w in Desktop(backend="uia").windows():
            t = w.window_text().strip()
            if not t:
                continue
            marker = "  ⭐" if "Perplexity" in t else ""
            print(f"         └─ \"{t}\"  [class: {w.class_name()}]{marker}")
        print()
        log("INFO", "Perplexity windows marked with ⭐")
    except Exception as e:
        log("ERROR", f"Could not list windows: {e}")


def send_toast(title: str, message: str):
    if not WINOTIFY_AVAILABLE:
        log("WARN", "winotify unavailable — toast skipped.")
        return
    n = Notification(app_id="Perplexity Watcher", title=title, msg=message, duration="long")
    n.set_audio(audio.Reminder, loop=False)
    n.show()
    log("OK", "Toast sent.") if DEBUG else None


def send_phone_push(title: str, message: str):
    try:
        r = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":        title.encode("ascii", errors="ignore").decode("ascii"),
                "Tags":         "warning,bell",
                "Priority":     "urgent",
                "Content-Type": "text/plain; charset=utf-8"
            },
            timeout=5
        )
        log("OK", f"ntfy push -> HTTP {r.status_code}") if DEBUG else None
    except Exception as e:
        log("ERROR", f"ntfy push failed: {e}")


def main():
    global DEBUG, VERBOSE

    parser = argparse.ArgumentParser(description="Perplexity Approval Watcher")
    parser.add_argument("--debug",        action="store_true", help="Show combo detection status per scan")
    parser.add_argument("--verbose",      action="store_true", help="Dump ALL short elements per scan")
    parser.add_argument("--list-windows", action="store_true", help="List all open windows and exit")
    parser.add_argument("--dry-run",      action="store_true", help="Scan once, no alerts fired")
    parser.add_argument("--reminder",     type=int, default=REMINDER_INTERVAL,
                        help=f"Seconds before re-alerting if popup not dismissed (default: {REMINDER_INTERVAL})")
    args = parser.parse_args()

    DEBUG   = args.debug or args.verbose
    VERBOSE = args.verbose
    reminder_interval = args.reminder

    print()
    print("=" * 55)
    print("  Perplexity Approval Watcher")
    print("=" * 55)
    log("INFO", f"Debug       : {'ON' if DEBUG else 'OFF'}  | Verbose: {'ON' if VERBOSE else 'OFF'}")
    log("INFO", f"ntfy        : {NTFY_SERVER}/{NTFY_TOPIC}")
    log("INFO", f"Combo       : {REQUIRED_COMBO}")
    log("INFO", f"Interval    : {CHECK_INTERVAL}s  | Reminder: every {reminder_interval}s if not dismissed")
    log("INFO", f"winotify    : {'available' if WINOTIFY_AVAILABLE else 'NOT installed'}")
    print("=" * 55)
    print()

    if args.list_windows:
        list_open_windows()
        return

    if args.dry_run:
        log("INFO", "Dry-run: scanning once...")
        DEBUG = True
        result = check_perplexity_waiting()
        print()
        log("INFO", f"Result: {'APPROVAL POPUP DETECTED' if result else 'No popup visible'}")
        return

    log("INFO", f"Watching... Reminder fires every {reminder_interval}s if popup persists. Ctrl+C to stop.\n")

    already_notified    = False
    alert_fired_at      = None   # timestamp when first alert was sent
    last_reminder_at    = None   # timestamp of last reminder
    scan_count          = 0

    while True:
        scan_count += 1
        log("DEBUG", f"--- Scan #{scan_count} ---") if DEBUG else None

        waiting = check_perplexity_waiting()
        now     = time.time()

        if waiting:
            if not already_notified:
                # ── First alert ──
                log("ALERT", "Approval popup detected! Sending initial alert...")
                send_toast("Perplexity Waiting!",
                           "Approval required - switch to app and approve/deny.")
                send_phone_push("Perplexity Needs You!",
                                "Approval popup detected. Open Perplexity and approve/deny.")
                already_notified = True
                alert_fired_at   = now
                last_reminder_at = now

            else:
                # ── Already alerted — check if reminder interval has passed ──
                time_waiting = now - alert_fired_at
                time_since_reminder = now - last_reminder_at

                if time_since_reminder >= reminder_interval:
                    elapsed_min = int(time_waiting // 60)
                    elapsed_sec = int(time_waiting % 60)
                    elapsed_str = f"{elapsed_min}m {elapsed_sec}s" if elapsed_min else f"{elapsed_sec}s"
                    log("REMIND", f"Popup still active after {elapsed_str}! Sending reminder...")
                    send_toast(
                        "Still Waiting! Perplexity",
                        f"Approval popup has been waiting {elapsed_str} - please respond!"
                    )
                    send_phone_push(
                        "Reminder: Perplexity Still Waiting!",
                        f"Approval popup has been open for {elapsed_str}. Open Perplexity and approve/deny."
                    )
                    last_reminder_at = now
                elif DEBUG:
                    remaining = int(reminder_interval - time_since_reminder)
                    log("DEBUG", f"Popup still active. Next reminder in {remaining}s.")

        else:
            if already_notified:
                log("OK", "Popup dismissed - resuming watch.")
                already_notified = False
                alert_fired_at   = None
                last_reminder_at = None
            elif DEBUG:
                log("DEBUG", "No popup. Sleeping...\n")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
