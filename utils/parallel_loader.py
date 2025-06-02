# utils/parallel_loader.py
"""
Parallel Loading System for VisionLane OCR
Enables parallel loading of components for faster startup
"""
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, Dict, Any, List, Optional
import logging
logger = logging.getLogger(__name__)
class LoadingTask:
    """Represents a single loading task"""
    def __init__(self, name: str, func: Callable, priority: int = 0,
                 dependencies: List[str] = None, **kwargs):
        self.name = name
        self.func = func
        self.priority = priority  # Higher priority = runs first
        self.dependencies = dependencies or []
        self.kwargs = kwargs
        self.result = None
        self.error = None
        self.completed = False
        self.started = False
class ParallelLoader:
    """Manages parallel loading of components with dependencies"""
    def __init__(self, progress_callback: Callable[[str], None] = None,
                 max_workers: int = 4):
        self.progress_callback = progress_callback or (lambda x: print(x))
        self.max_workers = max_workers
        self.tasks: Dict[str, LoadingTask] = {}
        self.completed_tasks: set = set()
        self.failed_tasks: set = set()
        self.task_lock = threading.Lock()
    def add_task(self, name: str, func: Callable, priority: int = 0,
                 dependencies: List[str] = None, **kwargs):
        """Add a loading task"""
        task = LoadingTask(name, func, priority, dependencies, **kwargs)
        self.tasks[name] = task
    def _can_start_task(self, task: LoadingTask) -> bool:
        """Check if a task can start (dependencies met)"""
        if task.started or task.completed:
            return False
        for dep in task.dependencies:
            if dep not in self.completed_tasks:
                return False
        return True
    def _get_ready_tasks(self) -> List[LoadingTask]:
        """Get tasks that are ready to run"""
        ready = []
        for task in self.tasks.values():
            if self._can_start_task(task):
                ready.append(task)
        # Sort by priority (higher first)
        ready.sort(key=lambda t: t.priority, reverse=True)
        return ready
    def _run_task(self, task: LoadingTask) -> LoadingTask:
        """Run a single task"""
        try:
            with self.task_lock:
                if task.started:
                    return task
                task.started = True
            self.progress_callback(f"Loading {task.name}...")
            # Run the task
            if task.kwargs:
                task.result = task.func(**task.kwargs)
            else:
                task.result = task.func()
            task.completed = True
            with self.task_lock:
                self.completed_tasks.add(task.name)
            self.progress_callback(f"✓ {task.name} loaded")
        except Exception as e:
            task.error = e
            task.completed = True
            with self.task_lock:
                self.failed_tasks.add(task.name)
            self.progress_callback(f"✗ Failed to load {task.name}")
            logger.error(f"Task {task.name} failed: {e}")
        return task
    def load_parallel(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Load all tasks in parallel with dependency management"""
        start_time = time.time()
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: Dict[Future, str] = {}
            while len(self.completed_tasks) + len(self.failed_tasks) < len(self.tasks):
                # Check for timeout
                if timeout and (time.time() - start_time) > timeout:
                    self.progress_callback("⚠ Loading timeout reached")
                    break
                # Get ready tasks
                ready_tasks = self._get_ready_tasks()
                # Submit ready tasks
                for task in ready_tasks:
                    if task.name not in [name for future, name in futures.items()]:
                        future = executor.submit(self._run_task, task)
                        futures[future] = task.name
                # Check completed futures
                completed_futures = []
                for future in list(futures.keys()):
                    if future.done():
                        completed_futures.append(future)
                # Process completed futures
                for future in completed_futures:
                    task_name = futures.pop(future)
                    try:
                        task = future.result()
                        if task.completed and not task.error:
                            results[task_name] = task.result
                    except Exception as e:
                        logger.error(f"Future error for {task_name}: {e}")
                # Small delay to prevent busy waiting
                if not completed_futures and not ready_tasks:
                    time.sleep(0.1)
        # Collect results from failed tasks as well
        for task_name, task in self.tasks.items():
            if task_name not in results:
                results[task_name] = task.result if task.completed else None
        return results
    def get_loading_summary(self) -> Dict[str, Any]:
        """Get summary of loading results"""
        return {
            'total_tasks': len(self.tasks),
            'completed': len(self.completed_tasks),
            'failed': len(self.failed_tasks),
            'success_rate': len(self.completed_tasks) / len(self.tasks) if self.tasks else 0,
            'failed_tasks': list(self.failed_tasks)
        }
class StartupLoader:
    """High-level startup loader using parallel loading"""
    def __init__(self, progress_callback: Callable[[str], None] = None):
        self.progress_callback = progress_callback
        self.loader = ParallelLoader(progress_callback, max_workers=3)
    def setup_loading_tasks(self, config_path=None):
        """Setup all startup loading tasks"""
        # Task 1: System diagnostics (no dependencies, high priority)
        self.loader.add_task(
            "system_check",
            self._run_system_diagnostics,
            priority=10
        )
        # Task 2: DocTR setup (no dependencies, high priority)
        self.loader.add_task(
            "doctr_setup",
            self._run_doctr_setup,
            priority=9
        )
        # Task 3: Config loading (no dependencies, medium priority)
        self.loader.add_task(
            "config_load",
            self._load_config,
            priority=8,
            config_path=config_path
        )
        # Task 4: Model downloads (depends on DocTR and config)
        self.loader.add_task(
            "model_download",
            self._download_models,
            priority=7,
            dependencies=["doctr_setup", "config_load"]
        )
        # Task 5: Initialize logging (no dependencies, low priority)
        self.loader.add_task(
            "logging_init",
            self._init_logging,
            priority=6
        )
    def _run_system_diagnostics(self):
        """Run system diagnostics"""
        from utils.system_diagnostics import SystemDiagnostics
        diagnostics = SystemDiagnostics(self.progress_callback)
        return diagnostics.run_diagnostics()
    def _run_doctr_setup(self):
        """Run DocTR setup"""
        from core import doctr_torch_setup
        return doctr_torch_setup.setup_doctr_with_progress(self.progress_callback)
    def _load_config(self, config_path=None):
        """Load configuration"""
        import configparser
        from pathlib import Path
        config_path = config_path or Path(__file__).parent.parent / "config.ini"
        config = configparser.ConfigParser()
        if config_path and Path(config_path).exists():
            config.read(config_path, encoding="utf-8")
        return {
            'detection_model': config.get("General", "detection_model", fallback="db_resnet50"),
            'recognition_model': config.get("General", "recognition_model", fallback="parseq"),
            'thread_count': config.getint("Performance", "thread_count", fallback=4)
        }
    def _download_models(self):
        """Download required models"""
        from utils.model_downloader import EnhancedModelManager
        # Get config from previous task
        config_task = self.loader.tasks.get("config_load")
        if config_task and config_task.result:
            config = config_task.result
            det_model = config.get('detection_model', 'db_resnet50')
            rec_model = config.get('recognition_model', 'parseq')
        else:
            det_model = 'db_resnet50'
            rec_model = 'parseq'
        manager = EnhancedModelManager(self.progress_callback)
        results = {}
        results['detection'] = manager.download_model_if_needed(det_model, "detection")
        results['recognition'] = manager.download_model_if_needed(rec_model, "recognition")
        return results
    def _init_logging(self):
        """Initialize logging system"""
        import logging
        from utils.logging_config import setup_logging
        try:
            setup_logging()
            return True
        except:
            # Fallback logging setup
            logging.basicConfig(level=logging.INFO)
            return True
    def load_all(self, timeout: float = 120) -> Dict[str, Any]:
        """Load all components in parallel"""
        return self.loader.load_parallel(timeout=timeout)
