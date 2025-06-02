import os
import signal
import psutil
import threading
import logging
from typing import Set
logger = logging.getLogger(__name__)
class ProcessManager:
    def __init__(self):
        self.processes: Set[int] = set()
        self.threads: Set[threading.Thread] = set()
        self.main_pid = os.getpid()
        self._lock = threading.Lock()
    def track_thread(self, thread: threading.Thread):
        """Track thread for cleanup and ensure it's set as daemon"""
        # Ensure thread is daemon to prevent hanging on exit
        if not thread.daemon:
            thread.daemon = True
        with self._lock:
            self.threads.add(thread)
    def track_process(self, pid: int):
        """Track process for cleanup"""
        with self._lock:
            self.processes.add(pid)
    def force_exit(self):
        """Force kill all tracked processes and threads"""
        # Stop threads first
        with self._lock:
            for thread in list(self.threads):
                try:
                    if thread.is_alive():
                        thread_name = thread.name.lower()
                        if not any(x in thread_name for x in ['watch', 'monitor', 'event', 'qt']):
                            thread._stop()
                except:
                    pass
            self.threads.clear()
        # Force kill processes and their children
        with self._lock:
            for pid in list(self.processes):
                try:
                    if pid != self.main_pid and psutil.pid_exists(pid):
                        proc = psutil.Process(pid)
                        for child in proc.children(recursive=True):
                            try:
                                child.kill()  # Use kill() instead of terminate()
                            except:
                                pass
                        proc.kill()  # Use kill() instead of terminate()
                except:
                    continue
            # Double check and force kill any remaining processes
            for pid in list(self.processes):
                try:
                    if pid != self.main_pid and psutil.pid_exists(pid):
                        os.kill(pid, signal.SIGKILL)
                except:
                    pass
            self.processes.clear()
        logger.debug("Force exit completed")
    def is_running(self) -> bool:
        """Check if any processes or threads are still running"""
        with self._lock:
            return bool(self.processes or any(t.is_alive() for t in self.threads))
