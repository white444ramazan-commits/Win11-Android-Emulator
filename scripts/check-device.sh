#!/system/bin/sh
# Read-only diagnostic for Android VM host capabilities.
set +e

echo '=== Android device ==='
echo "UID: $(id -u 2>/dev/null)"
echo "Android: $(getprop ro.build.version.release) (API $(getprop ro.build.version.sdk))"
echo "Device: $(getprop ro.product.manufacturer) $(getprop ro.product.model) ($(getprop ro.product.device))"
echo "ABI: $(getprop ro.product.cpu.abi)"
echo "Kernel: $(uname -a)"
echo

if [ "$(id -u 2>/dev/null)" != "0" ]; then
  echo 'WARNING: not running as root. Re-run with: su -c "sh /path/to/check-device.sh"'
fi

echo '=== Virtualization device nodes ==='
for node in /dev/kvm /dev/gunyah /dev/gzvm; do
  if [ -e "$node" ]; then
    ls -l "$node"
    if [ -r "$node" ] && [ -w "$node" ]; then
      echo "$node: present and readable/writable for this process"
    else
      echo "$node: present but not readable/writable for this process"
    fi
  else
    echo "$node: MISSING"
  fi
done
echo

echo '=== Related properties ==='
getprop | grep -iE 'hypervisor|kvm|gunyah|gzvm|virtual' 
echo

echo '=== Kernel misc devices ==='
if [ -r /proc/misc ]; then grep -iE 'kvm|gunyah|gzvm' /proc/misc; else echo '/proc/misc unavailable'; fi
echo

echo '=== SELinux ==='
getenforce 2>/dev/null
echo

echo 'Diagnostic complete. No system settings or partitions were changed.'
