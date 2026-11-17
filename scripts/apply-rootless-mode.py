#!/usr/bin/env python3
"""Apply the experimental rootless QEMU path to the pinned DroidVM submodule.

The patch is deliberately applied at build time so the upstream submodule remains pinned and
unchanged. Every replacement is guarded: if the pinned upstream source changes, the build fails
instead of silently producing an APK without the requested behavior.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "engine" / "DroidVM" / "app" / "src" / "main"
JAVA = APP / "java" / "cn" / "classfun" / "droidvm"


def replace_once(relative: str, old: str, new: str) -> None:
    path = APP / relative
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise SystemExit(
            f"rootless patch expected exactly one match in {path} "
            f"but found {count}; refusing to apply a partial patch"
        )
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def add_import(relative: str, anchor: str, import_line: str) -> None:
    path = APP / relative
    source = path.read_text(encoding="utf-8")
    if import_line in source:
        return
    if source.count(anchor) != 1:
        raise SystemExit(f"cannot locate import anchor in {path}")
    path.write_text(source.replace(anchor, anchor + import_line, 1), encoding="utf-8")


# Shared mode flag. The UI process sets it after detecting that su is unavailable;
# the daemon service sets the same flag before entering the daemon loop.
execution_mode = JAVA / "lib" / "utils" / "ExecutionMode.java"
execution_mode.write_text("""// SPDX-License-Identifier: GPL-3.0-or-later
package cn.classfun.droidvm.lib.utils;

/** Process-wide execution mode for the experimental unprivileged QEMU path. */
public final class ExecutionMode {
    private static volatile boolean rootless =
        "1".equals(System.getenv("DROIDVM_ROOTLESS"))
            || Boolean.getBoolean("droidvm.rootless");

    private ExecutionMode() { }

    public static boolean isRootless() {
        return rootless
            || "1".equals(System.getenv("DROIDVM_ROOTLESS"))
            || Boolean.getBoolean("droidvm.rootless");
    }

    public static void setRootless(boolean enabled) {
        rootless = enabled;
        System.setProperty("droidvm.rootless", enabled ? "true" : "false");
    }
}
""", encoding="utf-8")

# Run commands as the current app UID in rootless mode, not through libsu's su shell.
replace_once(
    "java/cn/classfun/droidvm/lib/utils/RunUtils.java",
    """return (Os.getuid() == 0) ?
            SystemRunContext.getContext() :
            RootRunContext.getContext();""",
    """return (Os.getuid() == 0 || ExecutionMode.isRootless()) ?
            SystemRunContext.getContext() :
            RootRunContext.getContext();"""
)

# Detect Root at daemon start. With no Root, start an in-process foreground service.
add_import("java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
           "import android.os.Handler;\n",
           "import android.content.Intent;\nimport android.os.Build;\n")
add_import("java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
           "import java.util.function.Consumer;\n",
           "import java.io.File;\n")
add_import("java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
           "import cn.classfun.droidvm.daemon.Daemon;\n",
           "import cn.classfun.droidvm.daemon.RootlessDaemonService;\n")
add_import("java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
           "import cn.classfun.droidvm.lib.ui.UIContext;\n",
           "import cn.classfun.droidvm.lib.utils.ExecutionMode;\n")
add_import("java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
           "import androidx.annotation.Nullable;\n",
           "import com.topjohnwu.superuser.Shell;\n")

replace_once(
    "java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
    """    public boolean startDaemon(boolean force) {
        var zipPath = getDaemonZipPath();""",
    """    public boolean startDaemon(boolean force) {
        boolean hasRoot;
        try {
            hasRoot = Shell.getShell().isRoot();
        } catch (Exception e) {
            Log.w(TAG, "Root check failed; selecting unprivileged mode", e);
            hasRoot = false;
        }
        if (!hasRoot) {
            ExecutionMode.setRootless(true);
            return startRootlessDaemon(force);
        }
        ExecutionMode.setRootless(false);
        var zipPath = getDaemonZipPath();"""
)

replace_once(
    "java/cn/classfun/droidvm/lib/daemon/DaemonHelper.java",
    """    public boolean stopDaemon() {
        Log.i(TAG, "Stopping daemon");""",
    """    /**
     * Starts the manager daemon inside an app-owned foreground service. In this mode QEMU
     * is restricted to TCG, user-mode networking and app-private files; root-only features
     * such as TAP networking and USB passthrough are not available.
     */
    private boolean startRootlessDaemon(boolean force) {
        if (isDaemonRunning()) {
            if (force) {
                Log.e(TAG, "Cannot force-restart an existing daemon without Root");
                return false;
            }
            DaemonConnection.getInstance().connect();
            return true;
        }

        // A root daemon may be invisible through /proc to an unprivileged app. Never start
        // a second daemon while a PID from a still-existing process is present.
        var pidFile = new File(getPidFile());
        if (pidFile.exists()) {
            try {
                int oldPid = Integer.parseInt(shellReadFile(getPidFile()).trim());
                if (oldPid > 1 && new File("/proc/" + oldPid).exists()) {
                    Log.e(TAG, "A daemon process already exists but cannot be inspected without Root");
                    return false;
                }
            } catch (Exception e) {
                Log.w(TAG, "Could not validate stale daemon PID file", e);
                return false;
            }
            if (!pidFile.delete()) {
                Log.e(TAG, "Could not remove stale daemon PID file");
                return false;
            }
        }
        new File(getTokenFile()).delete();
        new File(getPortFile()).delete();
        new File(pathJoin(DATA_DIR, "run")).mkdirs();
        new File(pathJoin(DATA_DIR, "cache")).mkdirs();

        var appContext = ctx.getContext().getApplicationContext();
        var serviceIntent = new Intent(appContext, RootlessDaemonService.class);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                appContext.startForegroundService(serviceIntent);
            else
                appContext.startService(serviceIntent);
        } catch (Exception e) {
            Log.e(TAG, "Failed to start the unprivileged VM service", e);
            return false;
        }

        long deadline = System.currentTimeMillis() + 15000;
        while (System.currentTimeMillis() < deadline) {
            if (new File(getPortFile()).isFile()) {
                Log.i(TAG, "Unprivileged DroidVM daemon is listening");
                DaemonConnection.getInstance().connect();
                return true;
            }
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        Log.e(TAG, "Unprivileged daemon did not publish its IPC port; see rootless-daemon logcat");
        appContext.stopService(serviceIntent);
        return false;
    }

    public boolean stopDaemon() {
        Log.i(TAG, "Stopping daemon");"""
)

# New service keeps the app-UID daemon alive while the user is running a guest VM.
service_path = JAVA / "daemon" / "RootlessDaemonService.java"
service_path.write_text("""// SPDX-License-Identifier: GPL-3.0-or-later
package cn.classfun.droidvm.daemon;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;

import cn.classfun.droidvm.R;
import cn.classfun.droidvm.lib.utils.ExecutionMode;

/** Foreground host for the restricted, app-UID DroidVM daemon. */
public final class RootlessDaemonService extends Service {
    private static final String TAG = "RootlessDroidVM";
    private static final String CHANNEL_ID = "droidvm_rootless_vm";
    private static final int NOTIFICATION_ID = 7314;
    private Thread daemonThread;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        createNotificationChannel();
        var notification = new Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_daemon_running)
            .setContentTitle(getString(R.string.app_name))
            .setContentText("QEMU software mode is running without Root")
            .setOngoing(true)
            .build();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }

        if (daemonThread == null) {
            daemonThread = new Thread(() -> {
                ExecutionMode.setRootless(true);
                try {
                    Daemon.main();
                } catch (Throwable t) {
                    Log.e(TAG, "Unprivileged daemon stopped unexpectedly", t);
                } finally {
                    stopSelf();
                }
            }, "DroidVM-Rootless-Daemon");
            daemonThread.start();
        }
        return START_NOT_STICKY;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        var manager = getSystemService(NotificationManager.class);
        if (manager == null) return;
        manager.createNotificationChannel(new NotificationChannel(
            CHANNEL_ID, "Virtual machine", NotificationManager.IMPORTANCE_LOW));
    }

    @Override
    public void onDestroy() {
        stopForeground(true);
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
""", encoding="utf-8")

# Declare the foreground service. SPECIAL_USE is explicit: the service exists only to host
# a user-requested local VM, not to disguise background work as data synchronization.
replace_once(
    "AndroidManifest.xml",
    """    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />""",
    """    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />"""
)
# Insert the service just before the first activity declaration.
replace_once(
    "AndroidManifest.xml",
    '        <activity\n            android:name=".ui.SplashActivity"',
    '        <service\n            android:name=".daemon.RootlessDaemonService"\n            android:exported="false"\n            android:foregroundServiceType="specialUse">\n            <property\n                android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"\n                android:value="Keeps a user-started local virtual machine running" />\n        </service>\n\n        <activity\n            android:name=".ui.SplashActivity"'
)

# In rootless mode, only show software acceleration as an available hypervisor.
replace_once(
    "java/cn/classfun/droidvm/lib/store/vm/VMHypervisor.java",
    """import cn.classfun.droidvm.lib.store.enums.StringEnum;""",
    """import cn.classfun.droidvm.lib.store.enums.StringEnum;
import cn.classfun.droidvm.lib.utils.ExecutionMode;"""
)
replace_once(
    "java/cn/classfun/droidvm/lib/store/vm/VMHypervisor.java",
    """    public boolean isDisplay() {
        return this != AUTO;
    }""",
    """    public boolean isDisplay() {
        return ExecutionMode.isRootless() ? this == SOFT : this != AUTO;
    }"""
)
replace_once(
    "java/cn/classfun/droidvm/lib/store/vm/VMHypervisor.java",
    """    public static VMHypervisor defaultForNewVm(@NonNull VMBackend backend) {
        var resolved = findPreferredHypervisor(backend);""",
    """    public static VMHypervisor defaultForNewVm(@NonNull VMBackend backend) {
        if (ExecutionMode.isRootless())
            return SOFT;
        var resolved = findPreferredHypervisor(backend);"""
)

# Default a new unprivileged VM to QEMU, hide the unavailable crosvm backend.
replace_once(
    "java/cn/classfun/droidvm/ui/vm/edit/basic/VMEditBasicTab.java",
    """import cn.classfun.droidvm.lib.utils.CpuUtils;""",
    """import cn.classfun.droidvm.lib.utils.CpuUtils;
import cn.classfun.droidvm.lib.utils.ExecutionMode;"""
)
replace_once(
    "java/cn/classfun/droidvm/ui/vm/edit/basic/VMEditBasicTab.java",
    """        chooseBackend.configure(VMBackend.class, VMBackend.DEFAULT);""",
    """        var defaultBackend = ExecutionMode.isRootless() ? VMBackend.QEMU : VMBackend.DEFAULT;
        chooseBackend.configure(VMBackend.class, defaultBackend);
        if (ExecutionMode.isRootless())
            chooseBackend.setVisibility(GONE);"""
)
replace_once(
    "java/cn/classfun/droidvm/ui/vm/edit/basic/VMEditBasicTab.java",
    """VMHypervisor.class, VMHypervisor.defaultForNewVm(VMBackend.DEFAULT));""",
    """VMHypervisor.class, VMHypervisor.defaultForNewVm(defaultBackend));"""
)
replace_once(
    "java/cn/classfun/droidvm/ui/vm/edit/basic/VMEditBasicTab.java",
    """        parent.put("backend", VMBackend.DEFAULT);""",
    """        parent.put("backend", defaultBackend);"""
)

# Do not offer hardware hypervisors or hidden root-dependent paths to rootless VMs.
replace_once(
    "java/cn/classfun/droidvm/ui/setup/step/VirtualizationStepFragment.java",
    """            if (hyp.getDevicePath() == null) continue;""",
    """            if (hyp == VMHypervisor.AUTO
                || (hyp.getDevicePath() == null && hyp != VMHypervisor.SOFT)) continue;"""
)
replace_once(
    "java/cn/classfun/droidvm/ui/setup/step/VirtualizationStepFragment.java",
    """    public boolean isHiddenStep() {
        return !optBoolean("isRoot", false);
    }""",
    """    public boolean isHiddenStep() {
        return false;
    }"""
)

# Force QEMU's TCG in the daemon and use SLIRP (user networking) rather than privileged TAP.
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/backend/QemuBackendInstance.java",
    """import cn.classfun.droidvm.lib.store.vm.VMHypervisor;""",
    """import cn.classfun.droidvm.lib.store.vm.VMHypervisor;
import cn.classfun.droidvm.lib.utils.ExecutionMode;"""
)
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/backend/QemuBackendInstance.java",
    """        var hypervisor = VMHypervisor.valueOf(hyp.toUpperCase());
        hypervisor = VMHypervisor.resolveConfigured(VMBackend.QEMU, hypervisor);""",
    """        var hypervisor = VMHypervisor.valueOf(hyp.toUpperCase());
        hypervisor = ExecutionMode.isRootless()
            ? VMHypervisor.SOFT
            : VMHypervisor.resolveConfigured(VMBackend.QEMU, hypervisor);"""
)
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/backend/QemuBackendInstance.java",
    """        if (item.optBoolean("hugepages", true))
            args.add("-mem-prealloc");""",
    """        if (!ExecutionMode.isRootless() && item.optBoolean("hugepages", true))
            args.add("-mem-prealloc");"""
)
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/backend/QemuBackendInstance.java",
    """    private void buildNetCommand(@NonNull List<String> args) {
        var nets = config.item.opt("networks", null);""",
    """    private void buildNetCommand(@NonNull List<String> args) {
        if (ExecutionMode.isRootless()) {
            args.add("-netdev");
            args.add("user,id=net0");
            args.add("-device");
            args.add("virtio-net-pci,netdev=net0,disable-legacy=on,disable-modern=off");
            return;
        }
        var nets = config.item.opt("networks", null);"""
)

# Skip root-only memory tuning and limits in the app-UID daemon.
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/VMBackendInstance.java",
    """import cn.classfun.droidvm.lib.store.vm.VMConfig;""",
    """import cn.classfun.droidvm.lib.store.vm.VMConfig;
import cn.classfun.droidvm.lib.utils.ExecutionMode;"""
)
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/VMBackendInstance.java",
    """        builder.maxOpenFiles(65536);
        builder.maxLockedMemory(RLIM_INFINITY);
        cleanUpMemory();""",
    """        if (!ExecutionMode.isRootless()) {
            builder.maxOpenFiles(65536);
            builder.maxLockedMemory(RLIM_INFINITY);
            cleanUpMemory();
        }"""
)

# Rootless VM lifecycle: QEMU only, no TAP setup/cleanup.
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/VMInstance.java",
    """import cn.classfun.droidvm.lib.utils.JsonUtils;""",
    """import cn.classfun.droidvm.lib.utils.JsonUtils;
import cn.classfun.droidvm.lib.utils.ExecutionMode;"""
)
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/VMInstance.java",
    """            joinThreads(1000);
            if (!setupTaps()) return false;""",
    """            joinThreads(1000);
            if (ExecutionMode.isRootless()
                && optEnum(item, "backend", VMBackend.DEFAULT) != VMBackend.QEMU) {
                Log.e(TAG, "Rootless mode supports QEMU only");
                return false;
            }
            if (!ExecutionMode.isRootless() && !setupTaps()) return false;"""
)
replace_once(
    "java/cn/classfun/droidvm/daemon/vm/VMInstance.java",
    """    private void cleanupTap() {
        var nets = requireNonNull(item.opt("networks", DataItem.newArray()));""",
    """    private void cleanupTap() {
        if (ExecutionMode.isRootless()) return;
        var nets = requireNonNull(item.opt("networks", DataItem.newArray()));"""
)

print("Applied experimental rootless QEMU/TCG mode to the pinned DroidVM engine.")
