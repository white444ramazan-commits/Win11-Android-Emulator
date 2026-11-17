# Experimental rootless QEMU mode

This branch adds a best-effort mode for devices where DroidVM cannot obtain Root.

## What it does

- Starts the DroidVM daemon inside an Android foreground service running as the application UID.
- Creates new virtual machines with the QEMU backend and the TCG software CPU emulator.
- Uses QEMU user-mode networking (SLIRP) instead of privileged TAP/bridge interfaces.
- Skips Root-only memory tuning, huge-page preparation and USB/TAP setup.

## What it does not do

- It does not grant access to `/dev/kvm`, `/dev/gunyah` or `/dev/gzvm`.
- It does not add a Shizuku privilege bypass. Shizuku's ADB-shell UID is not Root and does not automatically have device-node or SELinux permissions.
- It does not yet use Android Virtualization Framework (AVF). AVF is a separate backend and must be supported by the exact Android build and firmware.
- It does not support crosvm, hardware acceleration, TAP/bridged networking or USB passthrough in rootless mode.
- It does not guarantee Windows 11 performance. TCG translates guest CPU instructions in software and may be extremely slow on a tablet.

## How to test

1. Install the experimental APK from the GitHub Actions artifact.
2. Open the app. When the Root check fails, choose the option to continue without Root.
3. Continue through setup. The virtualization check should list software/QEMU mode.
4. Create a new VM. The editor should default to QEMU and Software (TCG); do not switch to crosvm or a hardware hypervisor.
5. Start with a small Linux ARM64 image first. A successful Linux boot is a better diagnostic than immediately allocating most of the tablet's RAM to Windows.
6. Only after QEMU TCG starts successfully, test a Windows 11 ARM64 image. Windows 11 requires considerably more memory and storage than a small Linux test guest.

If the foreground service does not start, collect Android logcat around tags `RootlessDroidVM`, `DaemonHelper`, `DroidVM` and `QemuBackendInstance`.

## Important

The patch is applied to the pinned DroidVM submodule during the build; the upstream submodule pointer is not moved. CI compilation does not prove that the service can run or that a guest can boot on a particular Android firmware. Test on the actual device before relying on this mode.
