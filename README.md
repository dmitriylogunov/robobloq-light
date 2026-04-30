# roboblq-light

Control ROBOBLOQ USB ambient LED strips - the kind shipped with the SyncLight Windows app - directly over HID. No SyncLight running, no proprietary software in the loop.

Reverse-engineered from SyncLight's Electron `app.asar`. Tested on the strip identifying as `VID=0x1A86 / PID=0xFE07`, manufacturer "ROBOBLOQ", product "USBHID".

## Why

SyncLight is the only first-party way to control these strips, and it has no API or CLI. This package lets you script colour changes - for example, a warm white at login and a deeper colour later in the evening, without having to open SyncLight.

## Install

```bash
pip install -e .
```

`hidapi` ships prebuilt wheels for Windows, so no compiler is needed.

## Quick start

```bash
rgblight probe                 # confirm the strip is found
rgblight brightness 80
rgblight color 255 220 180     # warm white
rgblight preset day            # same as above via named preset
rgblight preset night          # deep violet
rgblight off
```

Or from Python:

```python
from roboblq_light import Light

with Light.open() as light:
    light.set_brightness(80)
    light.set_color(60, 0, 160)
```

Important: SyncLight must not be running when you use this. SyncLight holds an exclusive HID handle and your writes will silently fail. Close it (and any tray helper) first.

## Run at Windows login

Schedule the script to run when you log in, with a small delay so the USB stack is ready:

```powershell
$action = New-ScheduledTaskAction -Execute "pythonw.exe" `
    -Argument "-m roboblq_light preset day"
$trigger = New-ScheduledTaskTrigger -AtLogon
$trigger.Delay = "PT15S"
Register-ScheduledTask -TaskName "AmbientLight" `
    -Action $action -Trigger $trigger -RunLevel Limited
```

Using `pythonw.exe` keeps the console window from flashing on screen at login.

## Protocol notes

The strip is a USB HID device with two interfaces. Interface 0 (MI_00, vendor-defined usage page 0xFF00) is where commands go. Interface 1 (MI_01) presents as a keyboard and is ignored.

Every packet uses the same frame:

```
+-----+-----+-----+-----+--------+ ... +----------+
| 'R' | 'B' | LEN |  ID |  CMD   | ... | CHECKSUM |
+-----+-----+-----+-----+--------+ ... +----------+
   0     1     2     3      4      ...    LEN-1
```

- Header: literal `RB` (0x52 0x42).
- LEN: total packet length including header and checksum.
- ID: 8-bit sequence counter, starts at 1, wraps at 254.
- CMD: action code (see `protocol.py` for the full list).
- CHECKSUM: sum of all preceding bytes mod 256.

### Implemented commands

| Command         | Code | Length | Notes                                                    |
| --------------- | ---- | ------ | -------------------------------------------------------- |
| `setBrightness` | 135  | 7      | Single byte payload, value 0-100.                        |
| `setSectionLED` | 134  | 6+5N   | N sections of `[index, R, G, B, flag]`. Flag is always 0xFF in observed traffic. |
| `turnOffLight`  | 151  | 6      | No payload.                                              |

### Empirical findings from a 3-section strip

- Sending one section with index 0 lights all three physical sections uniformly. The strip's firmware appears to broadcast unrecognised section indices to all LEDs.
- Per-LED addressing (different colours per section) is not yet implemented in this package. The protocol supports it via multiple Section entries in one packet — extending `Light.set_color` to accept a list of per-section colours is straightforward future work.
- The fifth byte of each section ("flag") is always 0xFF in SyncLight's traffic. Its meaning isn't yet clear; experiments are welcome.

### Other commands present in SyncLight (not yet wrapped)

`setLedEffect` (133), `setDynamicSpeed` (138), `setSyncScreen` (128), `setLampsAmount` (149), `setWhiteBright` (150), `setComputerRhythm` (152), several device-info readers. The packet builders in `protocol.py` can be extended to cover these — the framing and checksum logic is reusable.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests cover the pure protocol layer with captured packets from real device runs as ground truth. They don't require hardware.

## Scheduling at Windows login

The repo includes `setup-ambient-schedule.ps1`, which registers three Windows scheduled tasks so the strip changes colour automatically:

- **AmbientLight-Day** — applies the `day` preset at 7:00am every day.
- **AmbientLight-Night** — applies the `night` preset at 7:00pm every day.
- **AmbientLight-Login** — runs at logon, picks `day` or `night` based on the current hour. Has a 15-second delay so USB is ready before the script runs.

To install:

```powershell
.\setup-ambient-schedule.ps1
```

No admin rights needed — all three tasks run as your user, which is what gives them access to your session's USB devices.

To test the tasks without waiting for the schedule:

```powershell
Start-ScheduledTask -TaskName "AmbientLight-Day"
Start-ScheduledTask -TaskName "AmbientLight-Night"
Start-ScheduledTask -TaskName "AmbientLight-Login"
```

To remove the tasks:

```powershell
Unregister-ScheduledTask -TaskName "AmbientLight-Day"   -Confirm:$false
Unregister-ScheduledTask -TaskName "AmbientLight-Night" -Confirm:$false
Unregister-ScheduledTask -TaskName "AmbientLight-Login" -Confirm:$false
```

To change the schedule, edit the `$dayTime` and `$nightTime` variables at the top of the script and re-run it (the `-Force` flag overwrites existing tasks).

To inspect or manually disable the tasks, open Task Scheduler (`taskschd.msc`) and look for the three `AmbientLight-*` entries.

### Caveat: SyncLight autostart

If SyncLight is set to launch with Windows, it will grab an exclusive HID handle before the login task runs and the script's writes will silently no-op. Disable SyncLight's autostart via Task Manager's Startup tab, or in SyncLight's own settings.

## License

MIT.
