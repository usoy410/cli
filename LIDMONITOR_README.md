# Lid Monitor

The lid monitor automatically locks your screen when you close your laptop lid, providing security when you leave your device unattended.

## Features

- **Automatic locking**: Locks the screen immediately when the lid is closed
- **Daemon mode**: Runs in the background as a system service
- **Multiple fallback mechanisms**: Uses Caelestia shell lock, hyprctl fallback
- **Status monitoring**: Check if the monitor is running and current lid state
- **Graceful shutdown**: Proper signal handling for clean daemon management

## Usage

### Start the lid monitor daemon

```bash
caelestia lidmonitor --daemon
```

### Stop the lid monitor daemon

```bash
caelestia lidmonitor --stop
```

### Check status

```bash
caelestia lidmonitor --status
```

### Monitor in foreground (for testing)

```bash
caelestia lidmonitor --monitor
```

### Enable notifications

```bash
caelestia lidmonitor --daemon --notify
```

## How it works

The lid monitor:

1. **Reads lid state** from `/proc/acpi/button/lid/LID/state`
2. **Monitors for changes** every 500ms
3. **Triggers lock** when lid state changes from "open" to "closed"
4. **Uses multiple fallbacks** if the primary lock method fails

## Lock mechanisms (in order of preference)

1. **Hyprctl global dispatch**: `hyprctl dispatch global caelestia:lock` (same as Super+L)
2. **Caelestia shell**: `caelestia shell caelestia:lock`
3. **Hyprctl exec dispatch**: `hyprctl dispatch exec "caelestia shell caelestia:lock"`
4. **Loginctl**: `loginctl lock-session` (system-level session locking)
5. **Swaylock**: `swaylock` (fallback screen locker)

## System integration

### Automatic (Recommended)

**The lid monitor starts automatically** when you launch the Caelestia shell on laptops. No configuration needed!

### Manual Control (Optional)

If you need manual control, you can still use:

```bash
caelestia lidmonitor --daemon   # Start manually
caelestia lidmonitor --stop     # Stop manually
caelestia lidmonitor --status   # Check status
```

### Legacy Hyprland Config

For users who prefer manual configuration, add to `~/.config/hypr/hyprland.conf`:

```bash
exec-once = caelestia lidmonitor --daemon
```

### Systemd service (optional)

For system-wide integration, you can create a systemd user service:

```bash
# ~/.config/systemd/user/caelestia-lidmonitor.service
[Unit]
Description=Caelestia Lid Monitor
After=hyprland.service

[Service]
Type=simple
ExecStart=caelestia lidmonitor --monitor
Restart=always
RestartSec=5

[Install]
WantedBy=hyprland.service
```

Enable and start:

```bash
systemctl --user enable caelestia-lidmonitor.service
systemctl --user start caelestia-lidmonitor.service
```

## Troubleshooting

### Lid state not detected

- Check if `/proc/acpi/button/lid/LID/state` exists
- Verify ACPI is enabled in your kernel
- This feature only works on laptops with lid sensors

### Lock not working

- Ensure Caelestia shell is properly configured
- Check that your lock command (`caelestia:lock`) works manually
- Verify Hyprland is running and accessible

### Daemon not starting

- Check system logs: `journalctl --user -u caelestia-lidmonitor.service`
- Ensure proper permissions for PID file location
- Try running in foreground first to debug

## Security considerations

- The monitor runs with your user privileges
- Lock commands are executed as your user
- No elevated permissions required
- PID file stored in `/tmp/` for security

## Dependencies

- Linux with ACPI support
- Caelestia CLI installed and configured
- Hyprland window manager
- Python 3.13+
