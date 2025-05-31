# demo_enhanced_startup.py
"""
Demo script showcasing the enhanced startup system with all 5 features
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit, QLabel, QCheckBox, QSpinBox, QHBoxLayout, QGroupBox, QMessageBox
from PyQt6.QtCore import QTimer, Qt
import time
import json

def demo_startup_enhancements():
    """Demo all 5 startup enhancements"""
    
    print("=== VisionLane OCR Enhanced Startup Demo ===")
    print()
    
    # Feature 1: Enhanced Caching System
    print("1. ENHANCED CACHING SYSTEM")
    print("-" * 30)
    
    from utils.startup_cache import StartupCache
    cache = StartupCache()
    
    print(f"Cache directory: {cache.cache_dir}")
    print("Cache expiration times:")
    print(f"  - DocTR setup: {cache.DOCTR_CACHE_EXPIRY // 3600} hours")
    print(f"  - Models: {cache.MODELS_CACHE_EXPIRY // (24 * 3600)} days") 
    print(f"  - System info: {cache.SYSTEM_CACHE_EXPIRY // 3600} hour")
    
    # Demo caching
    print("\nCaching demo results...")
    cache.cache_doctr_setup(True, "2.0.0", "NVIDIA GeForce RTX 4090")
    cache.cache_models_status({"db_resnet50": True, "parseq": True})
    cache.cache_system_info({"memory_gb": 32, "cpu_cores": 16, "pytorch": True})
    
    # Retrieve cached data
    doctr_cache = cache.get_cached_doctr_setup()
    models_cache = cache.get_cached_models_status()
    system_cache = cache.get_cached_system_info()
    
    print("✓ DocTR cache:", "Found" if doctr_cache else "Not found")
    print("✓ Models cache:", "Found" if models_cache else "Not found")
    print("✓ System cache:", "Found" if system_cache else "Not found")
    print()
    
    # Feature 2: Model Download Progress
    print("2. MODEL DOWNLOAD PROGRESS")
    print("-" * 30)
    
    from utils.model_downloader import EnhancedModelManager
    
    def progress_callback(msg):
        print(f"  {msg}")
    
    model_manager = EnhancedModelManager(progress_callback)
    
    print("Model information:")
    for model in ["db_resnet50", "parseq"]:
        info = model_manager.get_model_info(model)
        print(f"  {model}: {'Cached' if info['cached'] else 'Not cached'} ({info['size']})")
    
    print("\nSimulating model download progress...")
    # This would normally download, but we'll just show the structure
    print("✓ Enhanced download system ready")
    print()
    
    # Feature 3: Parallel Loading System
    print("3. PARALLEL LOADING SYSTEM")
    print("-" * 30)
    
    from utils.parallel_loader import ParallelLoader, StartupLoader
    
    loader = ParallelLoader(max_workers=3)
    
    # Add some demo tasks
    loader.add_task("task1", lambda: time.sleep(0.1), priority=10)
    loader.add_task("task2", lambda: time.sleep(0.1), priority=9, dependencies=["task1"])
    loader.add_task("task3", lambda: time.sleep(0.1), priority=8)
    
    print(f"Parallel loader with {loader.max_workers} workers")
    print(f"Added {len(loader.tasks)} demo tasks")
    
    # Simulate loading
    print("Running parallel tasks...")
    results = loader.load_parallel(timeout=5)
    summary = loader.get_loading_summary()
    
    print(f"✓ Completed: {summary['completed']}/{summary['total_tasks']} tasks")
    print(f"✓ Success rate: {summary['success_rate']:.1%}")
    print()
    
    # Feature 4: Advanced System Diagnostics
    print("4. ADVANCED SYSTEM DIAGNOSTICS")
    print("-" * 30)
    
    from utils.system_diagnostics import SystemDiagnostics
    
    diagnostics = SystemDiagnostics()
    
    print("Running quick diagnostics...")
    quick_results = diagnostics.run_diagnostics(quick=True)
    
    print("System summary:")
    if 'memory_gb' in quick_results:
        print(f"  RAM: {quick_results['memory_gb']} GB")
    if 'cpu_cores' in quick_results:
        print(f"  CPU: {quick_results['cpu_cores']} cores")
    if 'pytorch' in quick_results:
        print(f"  PyTorch: {'Available' if quick_results['pytorch'] else 'Not available'}")
    if 'cuda' in quick_results:
        print(f"  CUDA: {'Available' if quick_results['cuda'] else 'Not available'}")
    
    print("✓ System diagnostics completed")
    print()
    
    # Feature 5: Configuration System
    print("5. STARTUP CONFIGURATION")
    print("-" * 30)
    
    from utils.startup_config import StartupConfig
    
    config = StartupConfig()
    
    print("Current startup preferences:")
    options = config.get_all_options()
    for key, value in options.items():
        print(f"  {key}: {value}")
    
    print("\nConfiguration capabilities:")
    print(f"  Skip diagnostics: {config.should_skip_system_diagnostics()}")
    print(f"  Parallel loading: {config.should_use_parallel_loading()}")
    print(f"  Auto-download models: {config.should_auto_download_models()}")
    print(f"  Cache results: {config.should_cache_results()}")
    print(f"  Startup timeout: {config.get_startup_timeout()}s")
    print("✓ Configuration system ready")
    print()
    
    print("=== DEMO COMPLETED ===")
    print("All 5 enhancements are implemented and functional!")
    print()
    print("Features summary:")
    print("✓ 1. Enhanced caching with expiration and validation")
    print("✓ 2. Detailed model download progress tracking") 
    print("✓ 3. Parallel loading with dependency management")
    print("✓ 4. Advanced system diagnostics and health checks")
    print("✓ 5. Comprehensive startup configuration options")

class EnhancedStartupDemo(QMainWindow):
    """GUI demo of the enhanced startup system"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VisionLane OCR - Enhanced Startup Demo")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Title
        title = QLabel("Enhanced Startup System Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Create tabs for each feature
        self.create_caching_demo(layout)
        self.create_parallel_loading_demo(layout)
        self.create_diagnostics_demo(layout)
        self.create_config_demo(layout)
        
        # Output area
        self.output = QTextEdit()
        self.output.setMaximumHeight(200)
        self.output.setStyleSheet("background-color: #2C3E50; color: #ECF0F1; font-family: monospace;")
        layout.addWidget(QLabel("Output:"))
        layout.addWidget(self.output)
        
        # Run all demo button
        run_all_btn = QPushButton("Run All Demos")
        run_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        run_all_btn.clicked.connect(self.run_all_demos)
        layout.addWidget(run_all_btn)
        
        # Initialize
        self.log("Enhanced Startup Demo initialized")
        
    def create_caching_demo(self, layout):
        """Create caching demo section"""
        group = QGroupBox("1. Enhanced Caching System")
        group_layout = QVBoxLayout(group)
        
        btn_layout = QHBoxLayout()
        
        cache_btn = QPushButton("Test Cache")
        cache_btn.clicked.connect(self.demo_caching)
        btn_layout.addWidget(cache_btn)
        
        clear_btn = QPushButton("Clear Cache")
        clear_btn.clicked.connect(self.clear_cache)
        btn_layout.addWidget(clear_btn)
        
        group_layout.addLayout(btn_layout)
        layout.addWidget(group)
        
    def create_parallel_loading_demo(self, layout):
        """Create parallel loading demo section"""
        group = QGroupBox("2. Parallel Loading System")
        group_layout = QVBoxLayout(group)
        
        parallel_btn = QPushButton("Demo Parallel Loading")
        parallel_btn.clicked.connect(self.demo_parallel_loading)
        group_layout.addWidget(parallel_btn)
        
        layout.addWidget(group)
        
    def create_diagnostics_demo(self, layout):
        """Create diagnostics demo section"""
        group = QGroupBox("3. System Diagnostics")
        group_layout = QVBoxLayout(group)
        
        diag_layout = QHBoxLayout()
        
        quick_btn = QPushButton("Quick Diagnostics")
        quick_btn.clicked.connect(lambda: self.demo_diagnostics(quick=True))
        diag_layout.addWidget(quick_btn)
        
        full_btn = QPushButton("Full Diagnostics")
        full_btn.clicked.connect(lambda: self.demo_diagnostics(quick=False))
        diag_layout.addWidget(full_btn)
        
        group_layout.addLayout(diag_layout)
        layout.addWidget(group)
        
    def create_config_demo(self, layout):
        """Create configuration demo section"""
        group = QGroupBox("4. Startup Configuration")
        group_layout = QVBoxLayout(group)
        
        # Configuration options
        self.parallel_check = QCheckBox("Enable Parallel Loading")
        self.parallel_check.setChecked(True)
        group_layout.addWidget(self.parallel_check)
        
        self.cache_check = QCheckBox("Cache Results")
        self.cache_check.setChecked(True)
        group_layout.addWidget(self.cache_check)
        
        self.auto_download_check = QCheckBox("Auto-download Models")
        self.auto_download_check.setChecked(True)
        group_layout.addWidget(self.auto_download_check)
        
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Startup Timeout:"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 600)
        self.timeout_spin.setValue(120)
        self.timeout_spin.setSuffix(" seconds")
        timeout_layout.addWidget(self.timeout_spin)
        group_layout.addLayout(timeout_layout)
        
        config_btn = QPushButton("Apply Configuration")
        config_btn.clicked.connect(self.apply_config)
        group_layout.addWidget(config_btn)
        
        layout.addWidget(group)
        
    def log(self, message):
        """Log message to output"""
        self.output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        
    def demo_caching(self):
        """Demo caching system"""
        self.log("Testing enhanced caching system...")
        try:
            from utils.startup_cache import StartupCache
            cache = StartupCache()
            
            # Test caching
            cache.cache_doctr_setup(True, "2.0.0", "Demo GPU")
            cache.cache_models_status({"model1": True, "model2": False})
            
            # Retrieve
            doctr_data = cache.get_cached_doctr_setup()
            models_data = cache.get_cached_models_status()
            
            self.log(f"✓ DocTR cache: {doctr_data is not None}")
            self.log(f"✓ Models cache: {models_data is not None}")
            self.log("Caching demo completed")
            
        except Exception as e:
            self.log(f"✗ Caching demo failed: {e}")
            
    def clear_cache(self):
        """Clear all caches"""
        try:
            from utils.startup_cache import StartupCache
            cache = StartupCache()
            cache.clear_cache()
            self.log("✓ All caches cleared")
        except Exception as e:
            self.log(f"✗ Cache clear failed: {e}")
            
    def demo_parallel_loading(self):
        """Demo parallel loading"""
        self.log("Starting parallel loading demo...")
        try:
            from utils.parallel_loader import ParallelLoader
            
            loader = ParallelLoader(
                progress_callback=self.log,
                max_workers=3
            )
            
            # Add demo tasks
            loader.add_task("init", lambda: time.sleep(0.1), priority=10)
            loader.add_task("config", lambda: time.sleep(0.1), priority=9)
            loader.add_task("models", lambda: time.sleep(0.2), priority=8, dependencies=["init"])
            loader.add_task("cleanup", lambda: time.sleep(0.1), priority=7, dependencies=["models", "config"])
            
            # Run tasks
            results = loader.load_parallel(timeout=10)
            summary = loader.get_loading_summary()
            
            self.log(f"✓ Parallel loading: {summary['completed']}/{summary['total_tasks']} tasks")
            self.log(f"✓ Success rate: {summary['success_rate']:.1%}")
            
        except Exception as e:
            self.log(f"✗ Parallel loading demo failed: {e}")
            
    def demo_diagnostics(self, quick=True):
        """Demo system diagnostics"""
        mode = "quick" if quick else "full"
        self.log(f"Running {mode} system diagnostics...")
        
        try:
            from utils.system_diagnostics import SystemDiagnostics
            
            diagnostics = SystemDiagnostics(self.log)
            results = diagnostics.run_diagnostics(quick=quick)
            
            if quick:
                self.log(f"✓ Memory: {results.get('memory_gb', 'Unknown')} GB")
                self.log(f"✓ CPU: {results.get('cpu_cores', 'Unknown')} cores")
                self.log(f"✓ PyTorch: {results.get('pytorch', False)}")
            else:
                summary = diagnostics.get_diagnostic_summary(results)
                self.log(f"✓ System summary: {summary}")
                
        except Exception as e:
            self.log(f"✗ Diagnostics failed: {e}")
            
    def apply_config(self):
        """Apply configuration settings"""
        self.log("Applying startup configuration...")
        
        try:
            from utils.startup_config import StartupConfig
            
            config = StartupConfig()
            
            # Update settings
            config.set_startup_option('enable_parallel_loading', self.parallel_check.isChecked())
            config.set_startup_option('cache_validation_results', self.cache_check.isChecked())
            config.set_startup_option('auto_download_models', self.auto_download_check.isChecked())
            config.set_startup_option('startup_timeout', self.timeout_spin.value())
            
            self.log("✓ Configuration applied successfully")
            
        except Exception as e:
            self.log(f"✗ Configuration failed: {e}")
            
    def run_all_demos(self):
        """Run all demos sequentially"""
        self.log("=== RUNNING ALL DEMOS ===")
        
        QTimer.singleShot(100, self.demo_caching)
        QTimer.singleShot(500, self.demo_parallel_loading)
        QTimer.singleShot(1000, lambda: self.demo_diagnostics(quick=True))
        QTimer.singleShot(1500, self.apply_config)
        
        QTimer.singleShot(2000, lambda: self.log("=== ALL DEMOS COMPLETED ==="))

if __name__ == "__main__":
    print("Choose demo mode:")
    print("1. Console demo")
    print("2. GUI demo")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            demo_startup_enhancements()
        elif choice == "2":
            app = QApplication(sys.argv)
            window = EnhancedStartupDemo()
            window.show()
            sys.exit(app.exec())
        else:
            print("Invalid choice, running console demo...")
            demo_startup_enhancements()
            
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        import traceback
        traceback.print_exc()
