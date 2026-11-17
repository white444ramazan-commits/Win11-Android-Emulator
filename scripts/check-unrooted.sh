#!/system/bin/sh
# Read-only probe for non-root / Shizuku VM feasibility.
# This script does not request root and does not change device settings.
set +e

echo "=== Execution identity ==="
id
echo "Android API: $(getprop ro.build.version.sdk)"
echo "Android release: $(getprop ro.build.version.release)"
echo "ABI: $(getprop ro.product.cpu.abi)"
echo

echo "=== Hypervisor nodes visible to this process ==="
for node in /dev/kvm /dev/gunyah /dev/gzvm; do
  if [ -e "$node" ]; then
    ls -l "$node" 2>&1
    [ -r "$node" ] && readable=yes || readable=no
    [ -w "$node" ] && writable=yes || writable=no
    echo "access: read=$readable write=$writable"
  else
    echo "$node: absent"
  fi
done
echo

echo "=== Shizuku installation ==="
if command -v pm >/dev/null 2>&1; then
  pm path moe.shizuku.privileged.api 2>&1
else
  echo "Package Manager command unavailable"
fi
echo

echo "=== Virtualization-related Android services ==="
if command -v service >/dev/null 2>&1; then
  service list 2>/dev/null | grep -iE 'virtual|vm|hypervisor' || echo "No matching service names visible"
else
  echo "service command unavailable"
fi
echo

echo "=== Relevant system properties ==="
getprop 2>/dev/null | grep -iE 'virtual|hypervisor|kvm|gunyah|gzvm' || echo "No matching properties"
echo

echo "=== Result ==="
echo "This is a capability probe only. Node visibility does not prove that a VM can be created."
echo "Shizuku normally runs commands with Android shell identity, not UID 0."
echo "No settings, permissions, partitions, boot images, or files were changed."
