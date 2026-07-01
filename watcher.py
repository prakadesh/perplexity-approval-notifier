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
# CONFIG — edit these
# ─────────────────────────────────────────────
NTFY_TOPIC      = "perplexity-prakadesh-alert"
NTFY_SERVER     = "https://ntfy.sh"
CHECK_INTERVAL  = 3
TRIGGER_TEXTS   = ["Approve", "Deny", "waiting for input", "^Enter", "^Esc"]
# ─────────────────────────────────────────────

# Debug flag — set via --debug CLI arg
DEBUG = False


def ts() -> str:
    """Timestamp prefix for all log lines."""
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str):
    icons = {"INFO": "ℹ️ ", "DEBUG": "🔍", "ALERT": "🚨", "WARN": "⚠️ ", "ERROR": "❌", "OK": "✅"}
    icon = icons.get(level, "  ")
    print(f"[{ts()}] {icon} [{level}] {msg}")


def get_all_windows():
    """Return list of all visible window titles on the system."""
    try:
        import pywinauto
        from pywinauto import Desktop
        windows = Desktop(backend="uia").windows()
        return [(w.window_text(), w.class_name()) for w in windows if w.window_text().strip()]
    except Exception as e:
        log("ERROR", f"Could not enumerate windows: {e}")
        return []


def check_perplexity_waiting() -> bool:
    """
    Scan Perplexity window UI elements for approval prompt text.
    In DEBUG mode, prints every element text found so you can tune TRIGGER_TEXTS.
    """
    try:
        import pywinauto
        app = pywinauto.Application(backend="uia").connect(title_re=".*Perplexity.*", timeout=2)
        win = app.top_window()
        win_title = win.window_text()

        log("DEBUG", f"Connected to window: \"{win_title}\"") if DEBUG else None

        all_texts = []
        matched_triggers = []

        for elem in win.descendants():
            try:
                text = elem.window_text().strip()
                if not text:
                    continue
                all_texts.append(text)
                matched = [t for t in TRIGGER_TEXTS if t in text]
                if matched:
                    matched_triggers.append((text, matched))
            except Exception:
                pass

        if DEBUG:
            log("DEBUG", f"Total UI elements with text: {len(all_texts)}")
            log("DEBUG", "─── All element texts found ───")
            for t in all_texts:
                print(f"         └─ {repr(t)}")
            if matched_triggers:
                log("DEBUG", "─── TRIGGER MATCHES ───")
                for text, triggers in matched_triggers:
                    print(f"         🎯 Text: {repr(text)}  →  Triggers: {triggers}")
            else:
                log("DEBUG", "No trigger texts matched in this scan.")

        return len(matched_triggers) > 0

    except pywinauto.application.ProcessNotFoundError:
        log("WARN", "Perplexity window not found — is the app running?") if DEBUG else None
        return False
    except Exception as e:
        log("ERROR", f"Unexpected error scanning window: {e}") if DEBUG else None
        return False


def list_open_windows():
    """Debug utility: print all open window titles so you can verify Perplexity's exact title."""
    log("DEBUG", "─── All open windows on this system ───")
    windows = get_all_windows()
    if not windows:
        print("         (none found or pywinauto error)")
    for title, cls in windows:
        print(f"         └─ \"{title}\"  [class: {cls}]")
    print()


def send_toast(title: str, message: str):
    if not WINOTIFY_AVAILABLE:
        log("WARN", "winotify not available — toast skipped.")
        return
    n = Notification(app_id="Perplexity Watcher", title=title, msg=message, duration="long")
    n.set_audio(audio.Reminder, loop=False)
    n.show()
    log("OK", "Windows toast sent.") if DEBUG else None


def send_phone_push(title: str, message: str):
    try:
        r = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Tags": "warning,bell", "Priority": "urgent"},
            timeout=5
        )
        if DEBUG:
            log("OK", f"ntfy push sent → HTTP {r.status_code}")
    except Exception as e:
        log("ERROR", f"ntfy push failed: {e}")


def main():
    global DEBUG

    parser = argparse.ArgumentParser(description="Perplexity Approval Watcher")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug output")
    parser.add_argument("--list-windows", action="store_true", help="List all open windows and exit")
    parser.add_argument("--dry-run", action="store_true", help="Scan once and print results without sending alerts")
    args = parser.parse_args()

    DEBUG = args.debug

    print()
    print("=" * 55)
    print("  Perplexity Approval Watcher")
    print("=" * 55)
    log("INFO", f"Debug mode   : {'ON' if DEBUG else 'OFF'  } (use --debug to enable)")
    log("INFO", f"ntfy topic   : {NTFY_SERVER}/{NTFY_TOPIC}")
    log("INFO", f"Trigger texts: {TRIGGER_TEXTS}")
    log("INFO", f"Poll interval: {CHECK_INTERVAL}s")
    log("INFO", f"winotify     : {'available' if WINOTIFY_AVAILABLE else 'NOT installed'}")
    print("=" * 55)
    print()

    # --list-windows: show all open windows and exit
    if args.list_windows:
        list_open_windows()
        return

    # --dry-run: one scan, print everything, no alerts
    if args.dry_run:
        log("INFO", "Dry-run mode — scanning once...")
        DEBUG = True
        result = check_perplexity_waiting()
        log("INFO", f"Dry-run result: {'APPROVAL PROMPT DETECTED' if result else 'Nothing detected'}")
        return

    log("INFO", "Watching... Press Ctrl+C to stop.\n")

    already_notified = False
    scan_count = 0

    while True:
        scan_count += 1
        if DEBUG:
            log("DEBUG", f"Scan #{scan_count}")

        waiting = check_perplexity_waiting()

        if waiting and not already_notified:
            log("ALERT", "Approval prompt detected! Firing notifications...")
            send_toast("⚠️ Perplexity Waiting!", "Approval required — switch to the app and approve/deny.")
            send_phone_push("⚠️ Perplexity Needs You!", "Approval prompt detected. Open Perplexity and approve/deny.")
            already_notified = True

        elif not waiting and already_notified:
            log("OK", "Prompt resolved — resuming watch.")
            already_notified = False

        elif not waiting and not already_notified and DEBUG:
            log("DEBUG", "No prompt detected. Sleeping...\n")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
