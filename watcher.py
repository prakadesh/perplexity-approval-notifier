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

DEBUG = False


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str):
    icons = {"INFO": "ℹ️ ", "DEBUG": "🔍", "ALERT": "🚨", "WARN": "⚠️ ", "ERROR": "❌", "OK": "✅"}
    icon = icons.get(level, "  ")
    print(f"[{ts()}] {icon} [{level}] {msg}")


def get_perplexity_windows():
    """
    Return all windows whose title matches Perplexity.
    Uses Desktop().windows() to safely handle multiple matches
    instead of Application.connect() which throws on ambiguity.
    """
    try:
        from pywinauto import Desktop
        all_wins = Desktop(backend="uia").windows()
        matched = [w for w in all_wins if "Perplexity" in w.window_text()]
        if DEBUG:
            log("DEBUG", f"Found {len(matched)} Perplexity window(s):")
            for i, w in enumerate(matched):
                print(f"         [{i+1}] \"{w.window_text()}\"  [class: {w.class_name()}]  [handle: {w.handle}]")
        return matched
    except Exception as e:
        log("ERROR", f"Could not enumerate Perplexity windows: {e}")
        return []


def scan_window_for_triggers(win) -> list:
    """
    Scan a single window's UI descendants for trigger texts.
    Returns list of (element_text, matched_triggers) tuples.
    """
    hits = []
    all_texts = []
    try:
        for elem in win.descendants():
            try:
                text = elem.window_text().strip()
                if not text:
                    continue
                all_texts.append(text)
                matched = [t for t in TRIGGER_TEXTS if t in text]
                if matched:
                    hits.append((text, matched))
            except Exception:
                pass
    except Exception as e:
        log("ERROR", f"Error scanning descendants: {e}")

    if DEBUG:
        log("DEBUG", f"  └─ {len(all_texts)} UI elements found")
        for t in all_texts:
            print(f"           └─ {repr(t)}")
        if hits:
            log("DEBUG", f"  └─ 🎯 TRIGGER MATCHES:")
            for text, triggers in hits:
                print(f"           🎯 {repr(text)}  →  {triggers}")
        else:
            log("DEBUG", "  └─ No triggers matched in this window.")

    return hits


def check_perplexity_waiting() -> bool:
    """
    Scan ALL Perplexity windows for approval prompt.
    Returns True if any window has a trigger match.
    """
    windows = get_perplexity_windows()

    if not windows:
        if DEBUG:
            log("WARN", "No Perplexity window found — is the app open?")
        return False

    for i, win in enumerate(windows):
        title = win.window_text()
        if DEBUG:
            log("DEBUG", f"Scanning window [{i+1}/{len(windows)}]: \"{title}\"")
        hits = scan_window_for_triggers(win)
        if hits:
            log("ALERT", f"Trigger found in window \"{title}\"!") if DEBUG else None
            return True

    return False


def list_open_windows():
    """Debug utility: list all open windows."""
    try:
        from pywinauto import Desktop
        log("DEBUG", "─── All open windows on this system ───")
        windows = Desktop(backend="uia").windows()
        visible = [w for w in windows if w.window_text().strip()]
        if not visible:
            print("         (none found)")
        for w in visible:
            marker = "  ⭐" if "Perplexity" in w.window_text() else ""
            print(f"         └─ \"{w.window_text()}\"  [class: {w.class_name()}]{marker}")
        print()
        log("INFO", f"Perplexity windows highlighted with ⭐ above.")
    except Exception as e:
        log("ERROR", f"Could not list windows: {e}")


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
        log("OK", f"ntfy push sent → HTTP {r.status_code}") if DEBUG else None
    except Exception as e:
        log("ERROR", f"ntfy push failed: {e}")


def main():
    global DEBUG

    parser = argparse.ArgumentParser(description="Perplexity Approval Watcher")
    parser.add_argument("--debug",        action="store_true", help="Verbose debug output")
    parser.add_argument("--list-windows", action="store_true", help="List all open windows and exit")
    parser.add_argument("--dry-run",      action="store_true", help="Scan once, no alerts")
    args = parser.parse_args()
    DEBUG = args.debug

    print()
    print("=" * 55)
    print("  Perplexity Approval Watcher")
    print("=" * 55)
    log("INFO", f"Debug mode   : {'ON' if DEBUG else 'OFF'}  (--debug to enable)")
    log("INFO", f"ntfy topic   : {NTFY_SERVER}/{NTFY_TOPIC}")
    log("INFO", f"Trigger texts: {TRIGGER_TEXTS}")
    log("INFO", f"Poll interval: {CHECK_INTERVAL}s")
    log("INFO", f"winotify     : {'available' if WINOTIFY_AVAILABLE else 'NOT installed'}")
    print("=" * 55)
    print()

    if args.list_windows:
        list_open_windows()
        return

    if args.dry_run:
        log("INFO", "Dry-run: scanning all Perplexity windows once...")
        DEBUG = True
        result = check_perplexity_waiting()
        print()
        log("INFO", f"Dry-run result: {'\U0001f6a8 APPROVAL PROMPT DETECTED' if result else '✅ Nothing detected — no prompt visible'}")
        return

    log("INFO", "Watching all Perplexity windows... Press Ctrl+C to stop.\n")

    already_notified = False
    scan_count = 0

    while True:
        scan_count += 1
        if DEBUG:
            log("DEBUG", f"--- Scan #{scan_count} ---")

        waiting = check_perplexity_waiting()

        if waiting and not already_notified:
            log("ALERT", "Approval prompt detected! Firing notifications...")
            send_toast("⚠️ Perplexity Waiting!", "Approval required — switch to app and approve/deny.")
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
