import subprocess
from argparse import Namespace

from caelestia.utils.paths import c_cache_dir


class Command:
    args: Namespace

    def __init__(self, args: Namespace) -> None:
        self.args = args

    def run(self) -> None:
        if self.args.show:
            # Print the ipc
            self.print_ipc()
        elif self.args.log:
            # Print the log
            self.print_log()
        elif self.args.kill:
            # Kill the shell
            self.shell("kill")
        elif self.args.message:
            # Send a message
            self.message(*self.args.message)
        else:
            # Start the shell
            args = ["qs", "-c", "caelestia", "-n"]
            if self.args.log_rules:
                args.append("--log-rules", self.args.log_rules)
            if self.args.daemon:
                args.append("-d")
                subprocess.run(args)
            else:
                shell = subprocess.Popen(args, stdout=subprocess.PIPE, universal_newlines=True)
                for line in shell.stdout:
                    if self.filter_log(line):
                        print(line, end="")

                # Auto-start lid monitor when shell starts (if on laptop)
                self._auto_start_lid_monitor()

    def shell(self, *args: list[str]) -> str:
        return subprocess.check_output(["qs", "-c", "caelestia", *args], text=True)

    def filter_log(self, line: str) -> bool:
        return f"Cannot open: file://{c_cache_dir}/imagecache/" not in line

    def print_ipc(self) -> None:
        print(self.shell("ipc", "show"), end="")

    def print_log(self) -> None:
        if self.args.log_rules:
            log = self.shell("log", "-r", self.args.log_rules)
        else:
            log = self.shell("log")
        # FIXME: remove when logging rules are added/warning is removed
        for line in log.splitlines():
            if self.filter_log(line):
                print(line)

    def message(self, *args: list[str]) -> None:
        print(self.shell("ipc", "call", *args), end="")

    def _auto_start_lid_monitor(self) -> None:
        """Automatically start lid monitor if on a laptop and not already running."""
        import os
        import subprocess
        from pathlib import Path

        # Check if this is a laptop (has lid device)
        lid_path = Path("/proc/acpi/button/lid/LID/state")
        if not lid_path.exists():
            return  # Not a laptop, skip

        # Check if lid monitor is already running
        pid_file = Path("/tmp/caelestia_lid_monitor.pid")
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)  # Check if process exists
                return  # Already running
            except (ValueError, ProcessLookupError):
                pid_file.unlink()  # Clean up stale PID file

        # Start lid monitor daemon silently
        try:
            subprocess.Popen([
                "caelestia", "lidmonitor", "--daemon"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            # Silently fail if caelestia command not available yet
            pass
