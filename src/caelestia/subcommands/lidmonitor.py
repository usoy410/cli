import os
import subprocess
import time
import signal
from argparse import Namespace
from pathlib import Path

# Simple logging function to avoid dependency issues
def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

# Simple notify function to avoid dependency issues
def notify(title, message, icon="dialog-information"):
    try:
        subprocess.run(["notify-send", "-i", icon, title, message],
                      capture_output=True, timeout=2)
    except Exception:
        pass  # Ignore notification failures


class Command:
    """Monitor laptop lid events and automatically lock when lid is closed."""

    args: Namespace
    lid_state_path: Path
    running: bool = False
    pid_file: Path

    def __init__(self, args: Namespace) -> None:
        self.args = args
        self.lid_state_path = Path("/proc/acpi/button/lid/LID/state")
        self.pid_file = Path("/tmp/caelestia_lid_monitor.pid")

    def run(self) -> None:
        if self.args.daemon:
            self.start_daemon()
        elif self.args.stop:
            self.stop_daemon()
        elif self.args.status:
            self.show_status()
        else:
            self.monitor_lid()

    def start_daemon(self) -> None:
        """Start the lid monitor as a daemon process."""
        if self.is_daemon_running():
            print("Lid monitor daemon is already running")
            return

        # Fork to background
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process
                print(f"Lid monitor started as daemon (PID: {pid})")
                if self.args.notify:
                    notify("Lid Monitor", "Automatic lid locking enabled", "security-high")
                return
        except OSError as e:
            error_msg = f"Failed to fork daemon: {e}"
            print(error_msg)
            if self.args.notify:
                notify("Lid Monitor Error", error_msg, "dialog-error")
            return

        # Child process continues as daemon
        os.setsid()
        os.chdir('/')
        os.umask(0)

        # Write PID file
        self.pid_file.write_text(str(os.getpid()))

        # Start monitoring
        self.monitor_lid()

    def stop_daemon(self) -> None:
        """Stop the lid monitor daemon."""
        if not self.pid_file.exists():
            print("No lid monitor daemon found")
            return

        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)

            # Wait for process to stop
            for _ in range(10):
                try:
                    os.kill(pid, 0)  # Check if process exists
                    time.sleep(0.5)
                except ProcessLookupError:
                    break
            else:
                # Force kill if still running
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            self.cleanup()
            print("Lid monitor daemon stopped")
            if self.args.notify:
                notify("Lid Monitor", "Automatic lid locking disabled", "security-low")

        except (ValueError, ProcessLookupError, PermissionError) as e:
            print(f"Failed to stop daemon: {e}")
            self.cleanup()  # Clean up stale PID file

    def show_status(self) -> None:
        """Show the current status of the lid monitor."""
        if self.is_daemon_running():
            pid = int(self.pid_file.read_text().strip())
            print(f"Lid monitor daemon: RUNNING (PID: {pid})")
            print("Automatic locking: ENABLED")
        else:
            print("Lid monitor daemon: STOPPED")
            print("Automatic locking: DISABLED")

        # Show current lid state
        try:
            lid_state = self.get_lid_state()
            print(f"Current lid state: {lid_state}")
        except Exception as e:
            print(f"Could not read lid state: {e}")

    def is_daemon_running(self) -> bool:
        """Check if the lid monitor daemon is currently running."""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ValueError, ProcessLookupError):
            self.cleanup()  # Clean up stale PID file
            return False

    def get_lid_state(self) -> str:
        """Get the current lid state (open/closed)."""
        if not self.lid_state_path.exists():
            raise FileNotFoundError("Lid state file not found - this may not be a laptop")

        content = self.lid_state_path.read_text().strip()
        # Parse the state from "state:      open" format
        state_line = [line for line in content.split('\n') if 'state:' in line]
        if state_line:
            return state_line[0].split(':')[1].strip()
        return "unknown"

    def monitor_lid(self) -> None:
        """Monitor lid events and lock when closed."""
        if not self.lid_state_path.exists():
            log_message("ERROR: Lid state file not found - this may not be a laptop or ACPI is not available")
            return

        log_message("Starting lid monitoring...")
        self.running = True
        last_state = None

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            log_message("Received shutdown signal")
            self.running = False

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        try:
            while self.running:
                try:
                    current_state = self.get_lid_state()

                    # Check for state change
                    if last_state is not None and last_state != current_state:
                        log_message(f"Lid state changed: {last_state} -> {current_state}")

                        if current_state == "closed":
                            if not self.trigger_lock():
                                log_message("WARNING: Failed to trigger lock - system may be unprotected!")
                        elif current_state == "open":
                            log_message("Lid opened")

                    last_state = current_state
                    time.sleep(0.5)  # Check every 500ms

                except Exception as e:
                    log_message(f"Error reading lid state: {e}")
                    time.sleep(1)  # Wait longer on error

        except KeyboardInterrupt:
            log_message("Lid monitoring stopped by user")
        finally:
            self.running = False
            self.cleanup()

    def trigger_lock(self) -> bool:
        """Trigger the screen lock using the same mechanism as Super+L keybind."""
        try:
            log_message("Lid closed - triggering lock")

            # Method 1: Use hyprctl global dispatch (same as Super+L keybind)
            try:
                log_message("Trying hyprctl global dispatch (same as Super+L)")
                result = subprocess.run([
                    "hyprctl", "dispatch", "global", "caelestia:lock"
                ], capture_output=True, text=True, timeout=5)

                if result.returncode == 0:
                    log_message("Lock triggered successfully via hyprctl global dispatch")
                    return True
                else:
                    log_message(f"Hyprctl global dispatch failed: {result.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log_message(f"Hyprctl global dispatch not available: {e}")

            # Method 2: Try Caelestia shell lock command
            try:
                log_message("Trying Caelestia shell fallback")
                result2 = subprocess.run([
                    "caelestia", "shell", "caelestia:lock"
                ], capture_output=True, text=True, timeout=5)

                if result2.returncode == 0:
                    log_message("Lock triggered successfully via Caelestia shell")
                    return True
                else:
                    log_message(f"Caelestia shell lock failed: {result2.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log_message(f"Caelestia shell not available: {e}")

            # Method 3: Try hyprctl exec dispatch
            try:
                log_message("Trying hyprctl exec dispatch")
                result3 = subprocess.run([
                    "hyprctl", "dispatch", "exec", "caelestia shell caelestia:lock"
                ], capture_output=True, text=True, timeout=5)

                if result3.returncode == 0:
                    log_message("Lock triggered successfully via hyprctl exec")
                    return True
                else:
                    log_message(f"Hyprctl exec dispatch failed: {result3.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log_message(f"Hyprctl exec not available: {e}")

            # Method 4: Try loginctl (system-level session locking)
            try:
                log_message("Trying loginctl session lock")
                result4 = subprocess.run([
                    "loginctl", "lock-session"
                ], capture_output=True, text=True, timeout=5)

                if result4.returncode == 0:
                    log_message("Lock triggered successfully via loginctl")
                    return True
                else:
                    log_message(f"Loginctl failed: {result4.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log_message(f"Loginctl not available: {e}")

            # Method 5: Try swaylock (if available)
            try:
                log_message("Trying swaylock as last resort")
                result5 = subprocess.run([
                    "swaylock"
                ], capture_output=True, text=True, timeout=2)

                if result5.returncode == 0:
                    log_message("Lock triggered successfully via swaylock")
                    return True
                else:
                    log_message(f"Swaylock failed: {result5.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log_message(f"Swaylock not available: {e}")

        except Exception as e:
            log_message(f"Unexpected error triggering lock: {e}")

        log_message("WARNING: All lock methods failed - system may be unprotected!")
        return False

    def cleanup(self) -> None:
        """Clean up PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()


def main():
    """Main entry point for caelestia lidmonitor subcommand."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor laptop lid events and auto-lock")
    parser.add_argument("-d", "--daemon", action="store_true", help="start as daemon")
    parser.add_argument("-s", "--stop", action="store_true", help="stop daemon")
    parser.add_argument("--status", action="store_true", help="show status")
    parser.add_argument("-m", "--monitor", action="store_true", help="start monitoring (foreground)")
    parser.add_argument("-n", "--notify", action="store_true", help="send notifications on state changes")

    args = parser.parse_args()

    monitor = Command(args)
    monitor.run()




if __name__ == "__main__":
    main()
