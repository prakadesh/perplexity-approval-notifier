import time
import requests
try:
    from winotify import Notification, audio
    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False
    print("[WARN] winotify not available. Windows toast notifications disabled.")

# ─────────────────────────────────────────────
# CONFIG — edit these
# ─────────────────────────────────────────────
NTFY_TOPIC = "perplexity-prakadesh-alert"   # change to your unique topic
NTFY_SERVER = "https://ntfy.sh"             # or self-hosted ntfy server
CHECK_INTERVAL = 3                          # seconds between checks
TRIGGER_TEXTS = ["Approve", "Deny", "waiting for input", "^Enter", "^Esc"]
# ─────────────────────────────────────────────


def check_perplexity_waiting() -> bool:
    """Scan Perplexity window UI elements for approval prompt text."""
    try:
        import pywinauto
        app = pywinauto.Application(backend="uia").connect(title_re=".*Perplexity.*", timeout=2)
        win = app.top_window()
        for elem in win.descendants():
            try:
                text = elem.window_text()
                if any(trigger in text for trigger in TRIGGER_TEXTS):
                    return True
            except Exception:
                pass
    except Exception as e:
        # Window not found or pywinauto error — not waiting
        pass
    return False


def send_toast(title: str, message: str):
    """Send a Windows toast notification."""
    if not WINOTIFY_AVAILABLE:
        return
    n = Notification(
        app_id="Perplexity Watcher",
        title=title,
        msg=message,
        duration="long"
    )
    n.set_audio(audio.Reminder, loop=False)
    n.show()


def send_phone_push(title: str, message: str):
    """Send a push notification to your phone via ntfy.sh."""
    try:
        requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Tags": "warning,bell",
                "Priority": "urgent"
            },
            timeout=5
        )
    except Exception as e:
        print(f"[ERROR] Failed to send ntfy push: {e}")


def main():
    print(f"[INFO] Perplexity Approval Watcher started.")
    print(f"[INFO] Monitoring for: {TRIGGER_TEXTS}")
    print(f"[INFO] ntfy topic: {NTFY_SERVER}/{NTFY_TOPIC}")
    print(f"[INFO] Press Ctrl+C to stop.\n")

    already_notified = False

    while True:
        waiting = check_perplexity_waiting()

        if waiting and not already_notified:
            print("[ALERT] Perplexity is waiting for your approval!")
            send_toast(
                title="⚠️ Perplexity Waiting!",
                message="Approval required — switch to the app and approve/deny."
            )
            send_phone_push(
                title="⚠️ Perplexity Needs You!",
                message="Approval prompt detected. Open Perplexity and approve/deny the action."
            )
            already_notified = True

        elif not waiting and already_notified:
            print("[INFO] Prompt resolved. Watching again...")
            already_notified = False

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
