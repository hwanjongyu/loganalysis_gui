import shutil
import subprocess
from typing import Optional

from PyQt5.QtWidgets import QMessageBox, QStyle
from .workers import AdbWorker, AdbDeviceScanWorker


class AdbController:
    """Manages ADB device discovery and logcat streaming worker lifecycle."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.scan_thread: Optional[AdbDeviceScanWorker] = None
        self.scan_request_id: int = 0

    @property
    def runtime(self):
        return self.main_window.runtime

    @property
    def device_selector(self):
        return self.main_window.device_selector

    @property
    def status_bar(self):
        return self.main_window.status_bar

    @property
    def adb_thread(self):
        return self.main_window.adb_thread

    @adb_thread.setter
    def adb_thread(self, val):
        self.main_window.adb_thread = val

    def stop_scan(self):
        thread = self.scan_thread
        self.scan_thread = None
        if thread is not None:
            try:
                if hasattr(thread, "stop"):
                    thread.stop()
                if hasattr(thread, "isRunning") and thread.isRunning():
                    thread.wait(500)
            except RuntimeError:
                pass

    def stop_adb_worker(self):
        self.stop_scan()
        thread = self.adb_thread
        self.adb_thread = None
        if thread:
            thread.stop()
            try:
                thread.chunk_ready.disconnect()
            except (TypeError, AttributeError):
                pass
            try:
                thread.error_occurred.disconnect()
            except (TypeError, AttributeError):
                pass
            if hasattr(thread, "isRunning") and thread.isRunning():
                thread.wait(1000)
            thread.finished.connect(thread.deleteLater)

    def refresh_adb_devices(self, sync: bool = False):
        if sync:
            self._refresh_adb_devices_sync()
        else:
            self._refresh_adb_devices_async()

    def _refresh_adb_devices_sync(self):
        self.device_selector.clear()
        try:
            adb_bin = shutil.which("adb") or "adb"
            output = subprocess.check_output(
                [adb_bin, "devices"],
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                timeout=3.0,
            )
            lines = output.strip().split("\n")
            devices = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])

            if devices:
                self.device_selector.addItems(devices)
                self.device_selector.setEnabled(True)
                self.status_bar.showMessage(f"Found {len(devices)} ADB devices.", 3000)
            else:
                self.device_selector.addItem("No Devices Found")
                self.device_selector.setEnabled(False)
                self.status_bar.showMessage("No ADB devices connected.", 3000)
        except subprocess.TimeoutExpired:
            self.device_selector.addItem("ADB Timeout")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage("ADB device scan timed out.", 3000)
        except FileNotFoundError:
            self.device_selector.addItem("ADB Not Found")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage("ADB not found in system PATH.", 3000)
        except Exception as e:
            self.device_selector.addItem("Scan Error")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage(f"ADB device scan error: {e}", 3000)

    def _refresh_adb_devices_async(self):
        self.stop_scan()
        self.scan_request_id += 1
        req_id = self.scan_request_id

        self.device_selector.clear()
        self.device_selector.addItem("Scanning...")
        self.device_selector.setEnabled(False)
        if hasattr(self.main_window, "btn_refresh_devices") and self.main_window.btn_refresh_devices:
            self.main_window.btn_refresh_devices.setEnabled(False)

        worker = AdbDeviceScanWorker(request_id=req_id)
        self.scan_thread = worker
        if hasattr(self.main_window, "_track_worker"):
            self.main_window._track_worker(worker)

        worker.devices_found.connect(self.on_devices_found)
        worker.scan_failed.connect(self.on_scan_failed)
        worker.finished.connect(self.on_scan_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def on_devices_found(self, req_id: int, devices: list):
        if req_id != self.scan_request_id:
            return
        self.device_selector.clear()
        if devices:
            self.device_selector.addItems(devices)
            self.device_selector.setEnabled(True)
            self.status_bar.showMessage(f"Found {len(devices)} ADB devices.", 3000)
        else:
            self.device_selector.addItem("No Devices Found")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage("No ADB devices connected.", 3000)

    def on_scan_failed(self, req_id: int, reason: str):
        if req_id != self.scan_request_id:
            return
        self.device_selector.clear()
        if reason == "timeout":
            self.device_selector.addItem("ADB Timeout")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage("ADB device scan timed out.", 3000)
        elif reason == "not_found":
            self.device_selector.addItem("ADB Not Found")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage("ADB not found in system PATH.", 3000)
        else:
            self.device_selector.addItem("Scan Error")
            self.device_selector.setEnabled(False)
            self.status_bar.showMessage(f"ADB device scan error: {reason}", 3000)

    def on_scan_finished(self):
        self.scan_thread = None
        if hasattr(self.main_window, "btn_refresh_devices") and self.main_window.btn_refresh_devices:
            self.main_window.btn_refresh_devices.setEnabled(True)

    def toggle_adb_monitoring(self):
        style = self.main_window.style()
        if not self.runtime.is_monitoring:
            self.main_window._cancel_file_load()
            self.main_window._stop_filter_worker()
            self.main_window._invalidate_filter_results()
            self.runtime.loaded_file_path = None
            self.main_window._update_loaded_file_label()
            self.main_window.log_model.clear()
            self.runtime.pending_chunks = []
            self.main_window.log_model.filters = self.main_window._effective_model_filters()

            serial = None
            if self.device_selector.isEnabled() and self.device_selector.currentText() not in [
                "No Devices Found",
                "ADB Not Found",
                "Scan Error",
                "ADB Timeout",
                "Scanning...",
            ]:
                serial = self.device_selector.currentText()

            thread = AdbWorker(device_serial=serial)
            self.adb_thread = thread
            self.main_window._track_worker(thread)
            thread.chunk_ready.connect(self.on_adb_chunk)
            thread.error_occurred.connect(self.on_adb_error)
            thread.start()

            self.runtime.is_monitoring = True
            self.runtime.is_paused = False
            self.main_window.adb_monitor_action.setText("Stop ADB Logcat")
            self.main_window.adb_monitor_action.setIcon(style.standardIcon(QStyle.SP_MediaStop))
            self.main_window.pause_action.setEnabled(True)
            self.main_window.pause_action.setChecked(False)
            if serial:
                self.status_bar.showMessage(f"Monitoring ADB Device: {serial}...")
            else:
                self.status_bar.showMessage("Monitoring ADB Logcat...")
        else:
            self.stop_adb_worker()
            self.runtime.is_monitoring = False
            self.runtime.is_paused = False
            self.runtime.is_refiltering = False
            self.main_window.adb_monitor_action.setText("Start ADB Logcat")
            self.main_window.adb_monitor_action.setIcon(style.standardIcon(QStyle.SP_ComputerIcon))
            self.main_window.pause_action.setEnabled(False)
            self.status_bar.showMessage("Monitoring stopped.")
            self.main_window.update_stats()
            self.main_window._flush_pending_chunks()

    def on_adb_chunk(self, lines):
        if self.runtime.is_paused or self.runtime.is_refiltering:
            self.runtime.pending_chunks.append(lines)
            return

        self.main_window._apply_chunk_to_model(lines)

    def on_adb_error(self, message):
        self.toggle_adb_monitoring()
        QMessageBox.critical(self.main_window, "ADB Error", message)
