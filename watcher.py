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
NTFY_TOPIC     = "perplexity-prakadesh-alert"
NTFY_SERVER    = "https://ntfy.sh"
CHECK_INTERVAL = 3
MAX_BTN_LEN    = 30  # UI elements longer than this are page content, not buttons

# Alert is fired ONLY when ALL three of these are present in the same window.
# This matches the exact Perplexity approval popup pattern:
#   "Awaiting response" (step indicator) + "Approve" button + "Deny" button
REQUIRED_COMBO = {"Awaiting response", "Approve", "Deny"}
# ─────────────────────────────────────────────

DEBUG   = False
VERBOSE = False  # --verbose: dump all short elements (very noisy)


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str):
    icons = {"INFO": "ℹ️ ", "DEBUG": "🔍", "ALERT": "🚨",
             "WARN": "⚠️ ", "ERROR": "❌", "OK": "✅"}
    print(f"[{ts()}] {icons.get(level,'  ')} [{level}] {msg}")


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
    """
    Return a set of all short UI element texts from this window.
    Short = <= MAX_BTN_LEN chars, no sentence punctuation.
    These are button/label elements only.
    """
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
        # Check which REQUIRED_COMBO items were found
        for item in REQUIRED_COMBO:
            found = item in short_texts
            marker = "✅" if found else "❌"
            print(f"         {marker} REQUIRED: {repr(item)}")
        if VERBOSE:
            log("DEBUG", "  └─ All short elements (--verbose):")
            for t in all_short:
                print(f"           └─ {repr(t)}")

    return short_texts


def check_perplexity_waiting() -> bool:
    """
    Returns True ONLY when ALL items in REQUIRED_COMBO are present
    in the same Perplexity window at the same time.
    Pattern: 'Awaiting response' + 'Approve' + 'Deny' = real approval popup.
    """
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
            # All required elements found — real approval popup!
            log("ALERT", f"Popup confirmed in \"{title}\" — combo: {REQUIRED_COMBO}") if DEBUG else None
            return True
        else:
            if DEBUG:
                log("DEBUG", f"  └─ Combo incomplete, missing: {missing}")

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
    parser.add_argument("--verbose",      action="store_true", help="Dump ALL short elements per scan (very noisy)")
    parser.add_argument("--list-windows", action="store_true", help="List all open windows and exit")
    parser.add_argument("--dry-run",      action="store_true", help="Scan once, no alerts fired")
    args = parser.parse_args()

    DEBUG   = args.debug or args.verbose
    VERBOSE = args.verbose

    print()
    print("=" * 55)
    print("  Perplexity Approval Watcher")
    print("=" * 55)
    log("INFO", f"Debug    : {'ON' if DEBUG else 'OFF'}  | Verbose: {'ON' if VERBOSE else 'OFF'}")
    log("INFO", f"ntfy     : {NTFY_SERVER}/{NTFY_TOPIC}")
    log("INFO", f"Combo    : {REQUIRED_COMBO}  (ALL must be present)")
    log("INFO", f"Interval : {CHECK_INTERVAL}s")
    log("INFO", f"winotify : {'available' if WINOTIFY_AVAILABLE else 'NOT installed'}")
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

    log("INFO", "Watching... Press Ctrl+C to stop.\n")
    already_notified = False
    scan_count = 0

    while True:
        scan_count += 1
        log("DEBUG", f"--- Scan #{scan_count} ---") if DEBUG else None

        waiting = check_perplexity_waiting()

        if waiting and not already_notified:
            log("ALERT", "Approval popup confirmed! Sending notifications...")
            send_toast("Perplexity Waiting!",
                       "Approval required - switch to app and approve/deny.")
            send_phone_push("Perplexity Needs You!",
                            "Approval popup detected. Open Perplexity and approve/deny.")
            already_notified = True

        elif not waiting and already_notified:
            log("OK", "Popup gone - resuming watch.")
            already_notified = False

        elif not waiting and DEBUG:
            log("DEBUG", f"Combo incomplete. Sleeping...\n")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
