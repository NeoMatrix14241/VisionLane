import threading
import ctypes
import inspect
import logging
import queue
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ThreadKiller:
    @staticmethod
    def terminate_thread(thread):
        """Forcefully terminate a Python thread"""
        if not thread.is_alive():
            return
            
        try:
            # Skip threads with 'watch', 'monitor' or 'event' in their names
            thread_name = thread.name.lower()
            if any(x in thread_name for x in ['watch', 'monitor', 'event']):
                return
                
            # Try graceful shutdown first
            thread.join(timeout=0.5)
            if not thread.is_alive():
                return
                
            # Force termination if still alive and not a monitor thread
            exc = ctypes.py_object(SystemExit)
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread.ident), exc)
            if res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
                
        except Exception as e:
            logger.error(f"Error terminating thread {thread.name}: {e}")

    @staticmethod
    def terminate_thread_pool(pool):
        """Safely terminate a ThreadPoolExecutor"""
        try:
            # Cancel queued tasks first
            if hasattr(pool, '_work_queue'):
                while True:
                    try:
                        pool._work_queue.get_nowait()
                    except queue.Empty:
                        break

            # Shutdown without waiting for tasks
            pool.shutdown(wait=False, cancel_futures=True)

            # Force terminate worker threads
            if hasattr(pool, '_threads'):
                for t in list(pool._threads):
                    ThreadKiller.terminate_thread(t)
                pool._threads.clear()

        except Exception as e:
            logger.error(f"Error terminating thread pool: {e}")

    @staticmethod
    def terminate_all_threads(exclude_qt=True):
        """Kill all threads except main thread, Qt threads and monitor threads"""
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()

        for thread in list(threading.enumerate()):
            # Skip protected threads
            if thread in (main_thread, current_thread):
                continue
            if exclude_qt and ("Qt" in thread.name or "MainThread" in thread.name):
                continue
                
            # Skip monitor/watch threads
            thread_name = thread.name.lower()
            if any(x in thread_name for x in ['watch', 'monitor', 'event']):
                continue
                
            try:
                ThreadKiller.terminate_thread(thread)
            except:
                pass
