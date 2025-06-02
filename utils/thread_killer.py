import threading
import gc
import logging
import sys
import os
import signal
import ctypes
from concurrent.futures import ThreadPoolExecutor
import inspect
import queue
import time
logger = logging.getLogger(__name__)
class ThreadKiller:
    """Static utility class to help terminate problematic threads"""
    @staticmethod
    def terminate_thread(thread):
        """Forcefully terminate a thread using system-specific methods."""
        if not thread or not isinstance(thread, threading.Thread):
            return
        if not thread.is_alive():
            return
        thread_id = thread.ident
        if thread_id is None:
            return
        try:
            # Use ctypes to forcefully terminate thread - platform specific
            if hasattr(ctypes, 'pythonapi') and hasattr(ctypes.pythonapi, 'PyThreadState_SetAsyncExc'):
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(thread_id),
                    ctypes.py_object(SystemExit)
                )
                if res > 1:
                    # If more than one thread affected, reset the effect
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), None)
                    logger.warning(f"Failed to terminate thread {thread_id} cleanly")
                elif res == 1:
                    logger.debug(f"Successfully terminated thread {thread_id}")
                else:
                    logger.warning(f"Thread {thread_id} not found")
            else:
                logger.warning("Thread termination not supported on this platform")
        except Exception as e:
            logger.error(f"Error terminating thread {thread_id}: {e}")
    @staticmethod
    def terminate_all_threads():
        """Attempt to terminate all non-main, non-critical threads."""
        try:
            current_thread = threading.current_thread()
            main_thread = threading.main_thread()
            # Identify all active threads
            active_threads = threading.enumerate()
            qt_threads = [t for t in active_threads
                         if "Qt" in t.name or "PyQt" in t.name]
            # Only terminate threads that aren't main, current, or Qt threads
            for thread in active_threads:
                if (thread != current_thread and
                    thread != main_thread and
                    thread not in qt_threads and
                    thread.is_alive()):
                    logger.debug(f"Terminating thread: {thread.name} ({thread.ident})")
                    ThreadKiller.terminate_thread(thread)
            # Force garbage collection
            gc.collect()
        except Exception as e:
            logger.error(f"Error terminating threads: {e}")
    @staticmethod
    def terminate_thread_pool(executor):
        """Terminate a thread pool executor forcefully."""
        if not executor or not isinstance(executor, ThreadPoolExecutor):
            return
        try:
            # First try gentle shutdown
            executor.shutdown(wait=False, cancel_futures=True)
            # Then forcefully terminate remaining worker threads
            if hasattr(executor, "_threads"):
                for thread in list(executor._threads):
                    if thread.is_alive():
                        ThreadKiller.terminate_thread(thread)
        except Exception as e:
            logger.error(f"Error terminating thread pool: {e}")
    @staticmethod
    def get_current_thread_stack():
        """Get stack trace information for the current thread."""
        try:
            stack = inspect.stack()
            stack_info = "\n".join([f"{frame.filename}:{frame.lineno} - {frame.function}"
                                   for frame in stack])
            return stack_info
        except Exception as e:
            return f"Error getting stack: {e}"
    @staticmethod
    def safe_kill_processes(pids, timeout=3):
        """Safely kill processes by PID with timeout"""
        if not isinstance(pids, (list, set)):
            pids = [pids]
        killed = []
        for pid in pids:
            try:
                # First try SIGTERM for graceful shutdown
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except (ProcessLookupError, PermissionError):
                # Process doesn't exist or permission denied
                pass
            except Exception as e:
                logger.warning(f"Error sending SIGTERM to {pid}: {e}")
        # Give processes time to terminate
        if killed and timeout > 0:
            time.sleep(timeout)
        # Force kill any remaining processes
        for pid in killed:
            try:
                # Check if process still exists
                os.kill(pid, 0)
                # If we get here, process still exists, force kill
                os.kill(pid, signal.SIGKILL)
                logger.debug(f"Force killed process {pid}")
            except (ProcessLookupError, PermissionError):
                # Process doesn't exist or permission denied - already gone
                pass
            except Exception as e:
                logger.warning(f"Error force-killing {pid}: {e}")
