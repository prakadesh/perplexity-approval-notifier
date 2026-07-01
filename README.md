# Perplexity Approval Notifier

> Never miss a Perplexity approval prompt again.

When you run an agentic task in [Perplexity Computer](https://www.perplexity.ai), it sometimes pauses and waits silently for your **Approve / Deny** input before continuing. If you switch to another window, you'll never know it's waiting — no sound, no alert, nothing.

This tool watches the Perplexity window in the background and fires an instant notification the moment that popup appears — and **keeps reminding you every 2 minutes** until you respond.

![Python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python) ![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey?logo=windows) ![License](https://img.shields.io/badge/license-MIT-green)

---

## How It Works

The watcher uses [`pywinauto`](https://pywinauto.readthedocs.io/) to scan all open Perplexity windows every 3 seconds. It fires an alert **only** when all three of these UI elements are present simultaneously:

| Element | What it means |
|---|---|
| `Awaiting response` | Perplexity is mid-task, waiting |
| `Approve` | The approval button is on screen |
| `Deny` | The deny button is on screen |

This 3-way co-presence check eliminates false positives from page content that may contain the words "Approve" or "Deny".

### Alert + Reminder Flow

```
Popup appears
     │
     ▼
🚨 Initial alert  →  Windows toast + phone push
     │
     │  (popup still not dismissed after 2 min)
     ▼
🔁 Reminder alert  →  Toast + push with elapsed time  ("waiting 2m 3s")
     │
     │  (every 2 min until dismissed)
     ▼
✅ Popup dismissed  →  Watcher resets, back to monitoring
```

When triggered, two alerts fire at once:
- 🔔 **Windows Toast** — native popup with sound, works even if the app is minimized
- 📱 **Phone Push** — instant notification via [ntfy.sh](https://ntfy.sh) (free, no account needed)

---

## Requirements

- Windows 10 / 11
- Python 3.8+
- Perplexity open in a browser (Chrome, Brave, Edge, etc.)
- Internet connection (for phone push via ntfy)

---

## Installation

```bash
git clone https://github.com/prakadesh/perplexity-approval-notifier
cd perplexity-approval-notifier
pip install -r requirements.txt
```

---

## Setup

### 1. Pick a unique ntfy topic name

Open `watcher.py` and change this line to something personal and unique:

```python
NTFY_TOPIC = "perplexity-yourname-alert"   # e.g. perplexity-john-2025
```

> Your topic name acts like a private channel. Anyone who knows it can subscribe, so make it non-obvious.

### 2. Install ntfy on your phone

| Platform | Link |
|---|---|
| Android | [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy) |
| iOS | [App Store](https://apps.apple.com/app/ntfy/id1625396347) |

Open the app → tap **+** → subscribe to your topic name (e.g. `perplexity-yourname-alert`).

### 3. Run the watcher

```bash
python watcher.py
```

Leave it running in the background. It uses minimal CPU (sleeps 3s between scans) and will alert you the moment Perplexity is waiting — then remind you every 2 minutes until you respond.

---

## Configuration

All config is at the top of `watcher.py`:

| Variable | Default | Description |
|---|---|---|
| `NTFY_TOPIC` | `perplexity-prakadesh-alert` | Your unique ntfy topic name |
| `NTFY_SERVER` | `https://ntfy.sh` | ntfy server URL (supports self-hosted) |
| `CHECK_INTERVAL` | `3` | Seconds between window scans |
| `REMINDER_INTERVAL` | `120` | Seconds before re-alerting if popup not dismissed |
| `REQUIRED_COMBO` | `{"Awaiting response", "Approve", "Deny"}` | All three must be present to fire alert |
| `MAX_BTN_LEN` | `30` | Max chars for a UI element to be treated as a button |

---

## CLI Reference

```
python watcher.py [options]
```

| Flag | Description |
|---|---|
| *(no flags)* | Normal run — silent background watcher |
| `--debug` | Show combo detection status per scan (clean summary) |
| `--verbose` | Dump all short UI elements per scan (for deep debugging) |
| `--dry-run` | Scan once and print result — no alerts fired |
| `--list-windows` | List all open windows on your system and exit |
| `--reminder N` | Override reminder interval to `N` seconds (default: 120) |

### Examples

```bash
# Remind every 30 seconds instead of 2 minutes
python watcher.py --reminder 30

# Debug mode with custom reminder
python watcher.py --debug --reminder 60
```

### First-time troubleshooting flow

```bash
# Step 1: Confirm Perplexity window is detected
python watcher.py --list-windows

# Step 2: Trigger an approval prompt in Perplexity, then run:
python watcher.py --dry-run

# Step 3: Watch live with status output
python watcher.py --debug

# Step 4: Normal run once confirmed working
python watcher.py
```

---

## Auto-Start on Boot (Optional)

To run automatically every time Windows starts:

1. Press `Win + R`, type `shell:startup`, press Enter
2. Create a shortcut in that folder pointing to:

```
pythonw.exe C:\full\path\to\watcher.py
```

> Use `pythonw.exe` (not `python.exe`) so no terminal window appears.

---

## Self-Hosted ntfy (Optional)

If you prefer not to use the public ntfy.sh server, you can self-host:

```bash
docker run -p 80:80 -v /var/cache/ntfy:/var/cache/ntfy binwiederhier/ntfy serve
```

Then update `NTFY_SERVER` in `watcher.py` to your server URL.

---

## FAQ

**Q: Does this work if Perplexity is open in multiple browser windows?**  
Yes. The watcher scans all windows titled "Perplexity" and checks each one.

**Q: Will it send duplicate alerts?**  
No. The initial alert fires once. After that, reminders fire on the `REMINDER_INTERVAL` schedule until the popup is dismissed.

**Q: Does it work with the Perplexity desktop app?**  
Yes, as long as the window title contains "Perplexity". Works with browser-based and Electron-based versions.

**Q: What if my browser window title is different?**  
Run `python watcher.py --list-windows` to see your exact window titles. If "Perplexity" doesn't appear, update the filter in `get_perplexity_windows()` in `watcher.py`.

**Q: Can I change the reminder interval?**  
Yes — either edit `REMINDER_INTERVAL` in `watcher.py`, or pass `--reminder N` on the command line.

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.

---

## License

MIT — see [LICENSE](LICENSE) for details.
