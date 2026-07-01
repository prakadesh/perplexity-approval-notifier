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

# EXACT trigger texts that only appear on the approval popup BUTTONS.
# These are short, button-level strings. Do NOT put long phrases here
# or they will match against page content text.
# The approval popup shows: button "Approve" + hint "^Enter"
#                           button "Deny"    + hint "^Esc"
TRIGGER_TEXTS   = ["Approve", "Deny", "^Enter", "^Esc"]

# Maximum character length for a UI element to be treated as a BUTTON.
# Real buttons are short (< 30 chars). Long text is page content — skip it.
MAX_TRIGGER_LEN = 30
# ─────────────────────────────────────────────

DEBUG = False


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str):
    icons = {"INFO": "ℹ️ ", "DEBUG": "🔍", "ALERT": "🚨", "WARN": "⚠️ ", "ERROR": "❌", "OK": "✅"}
    icon = icons.get(level, "  ")
    print(f"[{ts()}] {icon} [{level}] {msg}")


def get_perplexity_windows():
    """Return all windows whose title is exactly or contains 'Perplexity'."""
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


def is_approval_button(text: str) -> tuple:
    """
    Check if a UI element text looks like an approval BUTTON, not page content.
    Rules:
      1. Text must be short (<= MAX_TRIGGER_LEN chars) — buttons are short labels.
      2. Text must exactly match or contain a trigger word.
      3. Text must not contain sentence punctuation (., !, ?) — buttons don't.
    Returns (matched: bool, trigger_word: str)
    """
    if len(text) > MAX_TRIGGER_LEN:
        return False, ""
    # Reject anything that looks like a sentence
    if any(c in text for c in [".", "!", "?", ",", "\n"]):
        return False, ""
    for trigger in TRIGGER_TEXTS:
        # Exact match OR the text IS the trigger word (e.g. text == "Approve")
        if text == trigger or text.strip() == trigger:
            return True, trigger
    return False, ""


def scan_window_for_triggers(win) -> list:
    """
    Scan window descendants. Only flag SHORT button-like elements.
    Returns list of (element_text, trigger_word) tuples.
    """
    hits = []
    button_candidates = []
    skipped_long = 0

    try:
        for elem in win.descendants():
            try:
                text = elem.window_text().strip()
                if not text:
                    continue

                matched, trigger = is_approval_button(text)

                if matched:
                    hits.append((text, trigger))
                    button_candidates.append((text, "MATCH"))
                elif len(text) <= MAX_TRIGGER_LEN:
                    button_candidates.append((text, "short-no-match"))
                else:
                    skipped_long += 1

            except Exception:
                pass
    except Exception as e:
        log("ERROR", f"Error scanning descendants: {e}")

    if DEBUG:
        log("DEBUG", f"  └─ Short UI elements (buttons/labels): {len(button_candidates)}  |  Skipped long text: {skipped_long}")
        log("DEBUG", "  └─ Short elements:")
        for text, status in button_candidates:
            marker = "  🎯 MATCH" if status == "MATCH" else ""
            print(f"           [{status}] {repr(text)}{marker}")
        if not hits:
            log("DEBUG", "  └─ No approval buttons found in this window.")

    return hits


def check_perplexity_waiting() -> bool:
    """Scan ALL Perplexity windows. Return True only if a real approval button is found."""
    windows = get_perplexity_windows()

    if not windows:
        log("WARN", "No Perplexity window found — is the app open?") if DEBUG else None
        return False

    for i, win in enumerate(windows):
        title = win.window_text()
        if DEBUG:
            log("DEBUG", f"Scanning window [{i+1}/{len(windows)}]: \"{title}\"")
        hits = scan_window_for_triggers(win)
        if hits:
            log("ALERT", f"Approval button detected in \"{title}\": {hits}") if DEBUG else None
            return True

    return False


def list_open_windows():
    """Debug utility: list all open windows."""
    try:
        from pywinauto import Desktop
        log("DEBUG", "─── All open windows on this system ───")
        windows = Desktop(backend="uia").windows()
        visible = [w for w in windows if w.window_text().strip()]
        for w in visible:
            marker = "  ⭐" if "Perplexity" in w.window_text() else ""
            print(f"         └─ \"{w.window_text()}\"  [class: {w.class_name()}]{marker}")
        print()
        log("INFO", "Perplexity windows highlighted with ⭐")
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
    """Send push via ntfy. Uses ASCII-safe strings to avoid latin-1 codec errors."""
    try:
        # Strip emoji from title/message to avoid encoding issues in HTTP headers
        safe_title   = title.encode("ascii", errors="ignore").decode("ascii")
        safe_message = message.encode("utf-8")  # body is bytes, utf-8 safe

        r = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=safe_message,
            headers={
                "Title":    safe_title,
                "Tags":     "warning,bell",
                "Priority": "urgent",
                "Content-Type": "text/plain; charset=utf-8"
            },
            timeout=5
        )
        log("OK", f"ntfy push sent -> HTTP {r.status_code}") if DEBUG else None
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
    log("INFO", f"Debug mode     : {'ON' if DEBUG else 'OFF'}  (--debug to enable)")
    log("INFO", f"ntfy topic     : {NTFY_SERVER}/{NTFY_TOPIC}")
    log("INFO", f"Trigger texts  : {TRIGGER_TEXTS}")
    log("INFO", f"Max btn length : {MAX_TRIGGER_LEN} chars (longer = page content, ignored)")
    log("INFO", f"Poll interval  : {CHECK_INTERVAL}s")
    log("INFO", f"winotify       : {'available' if WINOTIFY_AVAILABLE else 'NOT installed'}")
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
        log("INFO", f"Dry-run result: {'APPROVAL PROMPT DETECTED' if result else 'Nothing detected - no approval prompt visible'}")
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
            send_toast("Perplexity Waiting!", "Approval required - switch to app and approve/deny.")
            send_phone_push("Perplexity Needs You!", "Approval prompt detected. Open Perplexity and approve/deny the action.")
            already_notified = True

        elif not waiting and already_notified:
            log("OK", "Prompt resolved - resuming watch.")
            already_notified = False

        elif not waiting and not already_notified and DEBUG:
            log("DEBUG", "No approval button detected. Sleeping...\n")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
