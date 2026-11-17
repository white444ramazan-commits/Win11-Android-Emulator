# Redmi Pad 2 Pro — compatibility check

## Device profile

| Component | Device specification |
|---|---|
| SoC | Qualcomm Snapdragon 7s Gen 4 / SM7635 Pro |
| CPU | 8 cores: 1× Cortex-A720 up to 2.7 GHz, 3× A720 up to 2.4 GHz, 4× A520 up to 1.8 GHz |
| GPU | Adreno 810 |
| RAM | 8 GB LPDDR4X (user-reported configuration) |
| Storage | 128 GB (user-reported configuration; UFS 2.2 family) |
| Display | 12.1-inch, 2560×1600, up to 120 Hz |
| Architecture | 64-bit ARM |

Xiaomi's global FAQ identifies the SoC as SM7635 Pro, the CPU as 64-bit Cortex-A720/A520, and the GPU as Adreno 810. Regional memory/storage SKUs can differ.

## Critical virtualization requirement

The current DroidVM README requires Android 13+, root access, and one usable hypervisor device: `/dev/kvm`, `/dev/gunyah`, or `/dev/gzvm`. Its listed Qualcomm devices start at Snapdragon 8 Gen 3 (SM8650) with Gunyah. Redmi Pad 2 Pro / Snapdragon 7s Gen 4 is not listed as a supported device.

That does not prove KVM is absent from this exact firmware. It means we must test the running kernel instead of assuming compatibility from the CPU name. Merely seeing a device node is not enough; the engine must also be able to open it and create a VM.

## Run the diagnostic

1. Enable USB debugging on the tablet and connect it to a computer with Android Platform Tools, or copy `scripts/check-device.sh` onto the tablet.
2. Run the script as root:

```bash
adb push scripts/check-device.sh /data/local/tmp/check-device.sh
adb shell su -c 'sh /data/local/tmp/check-device.sh'
```

3. Send back the complete output. Do not post serial numbers, account details, or other personal identifiers.

The script only reads system information and checks device-node permissions. It does not change partitions, kernel settings, boot images, or files.

## Windows 11 VM resource constraints

Microsoft's current VM requirements list at least 4 GB guest RAM, 64 GB guest storage, two virtual processors, and a Generation 2 / UEFI-style VM with TPM 2.0 and Secure Boot where applicable. With 8 GB total tablet RAM, assigning 4 GB to Windows may leave little headroom for Android. Expect to close other apps and possible memory pressure.

Use a dynamic virtual disk and keep substantial free space on the tablet. The virtual disk's 64 GB maximum is not instantly consumed by a sparse image, but the used space grows as Windows is installed and updated.

## Expected next decision

- If the diagnostic shows an accessible KVM/Gunyah node, test the runtime with the engine's own compatibility probe before creating a Windows disk.
- If no usable hypervisor is exposed, this device cannot use the fast virtualization path. A QEMU TCG fallback would require a separately built and tested Android-native backend and is likely to be substantially slower; do not assume it will be usable for Windows 11.
- Do not flash a generic kernel, boot image, or third-party virtualization module as a workaround.


## Rootless test path (experimental)

The experimental branch can start the QEMU daemon as the app UID when `su` is unavailable. It forces QEMU TCG, disables root-only memory tuning and TAP setup, and uses QEMU user networking. Create a VM with the QEMU backend and software hypervisor. Existing VMs configured for crosvm or hardware hypervisors must be recreated or changed to QEMU/Software. Performance can be too low for a usable Windows 11 desktop. USB passthrough and bridged networking are not supported in this mode.

The mode has not been validated on physical hardware. A successful APK build only verifies compilation, not guest boot or service survival on a Xiaomi firmware.
