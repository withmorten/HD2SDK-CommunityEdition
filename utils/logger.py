import os
from datetime import datetime

# Global log file handle
_log_file = None
_log_path = None

def SetLogFile(path):
    """Set the log file path. Pass None to disable file logging.
    Uses line buffering and immediate flush for interrupt safety."""
    global _log_file, _log_path
    CloseLogFile()
    if path:
        _log_path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Use line buffering (buffering=1) for immediate writes
        _log_file = open(path, 'w', encoding='utf-8', buffering=1)
        _log_file.write(f"=== HD2SDK:CE Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        _log_file.write(f"=== Log path: {path} ===\n\n")
        _force_flush()

def _force_flush():
    """Force flush log file to disk (survives interrupts)."""
    global _log_file
    if _log_file:
        try:
            _log_file.flush()
            os.fsync(_log_file.fileno())  # Force OS to write to disk
        except:
            pass

def CloseLogFile():
    """Close the log file if open."""
    global _log_file, _log_path
    if _log_file:
        try:
            _force_flush()
            _log_file.close()
        except:
            pass
        _log_file = None
    _log_path = None

def GetLogPath():
    """Get the current log file path."""
    return _log_path

def PrettyPrint(msg, type="info"): # Inspired by FortnitePorting
    global _log_file
    reset = u"\u001b[0m"
    color = reset
    match type.lower():
        case "info":
            color = u"\u001b[36m"
        case "warn" | "warning":
            color = u"\u001b[33m"
        case "error":
            color = u"\u001b[31m"
        case _:
            pass
    print(f"{color}[HD2SDK:CE]{reset} {msg}")

    # Also write to log file if set - with forced disk write for interrupt safety
    if _log_file:
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            _log_file.write(f"[{timestamp}] {msg}\n")
            _force_flush()
        except:
            pass