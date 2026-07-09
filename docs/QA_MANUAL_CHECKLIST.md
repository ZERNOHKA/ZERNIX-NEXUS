# Manual QA Checklist

Run these checks on a non-production Windows machine or VM. Create a system restore point before testing optimization actions.

## Preconditions

1. Start the app with Administrator rights: `python main.py` or the built `.exe`.
2. Activate a valid license if license validation is enabled.
3. Close unnecessary apps before testing gaming presets.

## A. Gaming Turbo Preset

1. Open **Advanced -> Profiles**.
2. Apply **Gaming Turbo**.
3. Confirm the app log has no Python exceptions.
4. Optional: run `powercfg /getactivescheme` and check that Windows moved to a high-performance power plan.

## B. Dashboard Session Boost

1. Press **Session Boost** on the dashboard.
2. Confirm the FaceIT-sensitive action warning if it appears.
3. Check that steps complete in order: backup, adaptive CS2 profile, system boost, network optimization, and optional kernel latency profile.
4. If CS2 is not running, kernel latency should be skipped gracefully.

## C. Work / Restore

1. Apply **Work / Restore** or press **Session Rollback** on the dashboard.
2. Confirm the power plan moves back toward Balanced.
3. Confirm the kernel latency profile is released if it was active.
4. Optional registry spot-check:
   - `HKLM\...\PriorityControl\Win32PrioritySeparation`
   - `HKCU\Control Panel\Mouse`

## D. CyberSport Confirmation Flow

1. Apply **CyberSport**.
2. Confirm the FaceIT warning if it appears.
3. A second warning about VBS and `bcdedit` should appear.
4. Cancel once and confirm the preset does not run.

## E. Strict Release Build

```powershell
.\build_protected.ps1 -StrictObfuscation
```

Expected behavior: the build exits with code `2` if PyArmor falls back to plain source files. For a real release, use a PyArmor license/configuration that fully protects the selected modules.

## Rollback Notes

- CS2 `autoexec.cfg` edits should be backed up manually or through Steam Cloud awareness.
- `netsh` TCP changes from **Network Fix** are not fully reverted by registry rollback.
- See [AUDIT_MATRIX.md](AUDIT_MATRIX.md) for detailed action coverage.
