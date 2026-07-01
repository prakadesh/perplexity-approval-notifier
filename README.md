# Perplexity Approval Notifier

A lightweight background watcher that detects when the **Perplexity desktop app** is waiting for your **Approve / Deny** input during an agentic task — and immediately alerts you via:

- 🔔 **Windows Toast Notification** (on-screen popup with sound)
- 📱 **Phone Push Notification** via [ntfy.sh](https://ntfy.sh) (free, no account needed)

No more silently stalled Perplexity sessions while you're working on something else.

---

## How It Works

The script uses `pywinauto` to scan the Perplexity window's UI elements every 3 seconds. When it detects trigger text like `Approve`, `Deny`, or `^Enter`, it fires both a toast and a phone notification.

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your ntfy Topic

Edit `watcher.py` and change:

```python
NTFY_TOPIC = "perplexity-prakadesh-alert"   # pick a unique topic name
```

### 3. Install ntfy on Your Phone

- [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- [iOS](https://apps.apple.com/app/ntfy/id1625396347)

Open the app → **Subscribe** to your topic (e.g. `perplexity-prakadesh-alert`).

### 4. Run the Watcher

```bash
python watcher.py
```

Keep it running in the background whenever you start a Perplexity agentic session.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `NTFY_TOPIC` | `perplexity-prakadesh-alert` | Your unique ntfy topic |
| `NTFY_SERVER` | `https://ntfy.sh` | ntfy server (or self-hosted) |
| `CHECK_INTERVAL` | `3` | Seconds between checks |
| `TRIGGER_TEXTS` | `["Approve", "Deny", ...]` | Texts to watch for in the window |

---

## Auto-Start on Boot (Windows)

To run automatically on startup, create a shortcut to:

```
pythonw.exe C:\path\to\watcher.py
```

Place it in: `shell:startup` (press Win+R, type `shell:startup`)

---

## Requirements

- Windows 10/11
- Python 3.8+
- Perplexity desktop app running
- Internet connection (for ntfy push)

---

## License

MIT
