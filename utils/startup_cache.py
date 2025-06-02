# utils/startup_cache.py
"""
Enhanced Startup Cache System for VisionLane OCR
Provides caching for DocTR setup, model downloads, and system checks
"""
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
logger = logging.getLogger(__name__)
class StartupCache:
    """Enhanced caching system for startup operations"""
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "visionlane_ocr"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Cache files
        self.doctr_cache_file = self.cache_dir / "doctr_setup.json"
        self.models_cache_file = self.cache_dir / "models_status.json"
        self.system_cache_file = self.cache_dir / "system_info.json"
        self.config_cache_file = self.cache_dir / "config_hash.json"
        # Cache expiration times (in seconds)
        self.DOCTR_CACHE_EXPIRY = 24 * 60 * 60  # 24 hours
        self.MODELS_CACHE_EXPIRY = 7 * 24 * 60 * 60  # 7 days
        self.SYSTEM_CACHE_EXPIRY = 60 * 60  # 1 hour
    def _is_cache_valid(self, cache_file: Path, expiry_seconds: int) -> bool:
        """Check if cache file exists and is not expired"""
        if not cache_file.exists():
            return False
        try:
            stat = cache_file.stat()
            age = time.time() - stat.st_mtime
            return age < expiry_seconds
        except Exception:
            return False
    def _load_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """Load cache data from file"""
        try:
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache from {cache_file}: {e}")
        return None
    def _save_cache(self, cache_file: Path, data: Dict[str, Any]) -> bool:
        """Save cache data to file"""
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save cache to {cache_file}: {e}")
            return False
    def get_config_hash(self, config_path: Path) -> str:
        """Generate hash of config file for cache invalidation"""
        try:
            if config_path.exists():
                content = config_path.read_text(encoding='utf-8')
                return hashlib.md5(content.encode()).hexdigest()
        except Exception:
            pass
        return "no_config"
    def is_config_changed(self, config_path: Path) -> bool:
        """Check if config file has changed since last cache"""
        current_hash = self.get_config_hash(config_path)
        cached_data = self._load_cache(self.config_cache_file)
        if not cached_data:
            return True
        return cached_data.get('config_hash') != current_hash
    def update_config_hash(self, config_path: Path):
        """Update stored config hash"""
        config_hash = self.get_config_hash(config_path)
        self._save_cache(self.config_cache_file, {
            'config_hash': config_hash,
            'timestamp': time.time()
        })
    # DocTR Cache Methods
    def get_cached_doctr_setup(self) -> Optional[Dict[str, Any]]:
        """Get cached DocTR setup results"""
        if not self._is_cache_valid(self.doctr_cache_file, self.DOCTR_CACHE_EXPIRY):
            return None
        return self._load_cache(self.doctr_cache_file)
    def cache_doctr_setup(self, success: bool, pytorch_version: str = None,
                         gpu_info: str = None, **kwargs):
        """Cache DocTR setup results with enhanced logging"""
        import logging
        logger = logging.getLogger(__name__)
        data = {
            'success': success,
            'timestamp': time.time(),
            'pytorch_version': pytorch_version,
            'gpu_info': gpu_info,
            **kwargs
        }
        if self._save_cache(self.doctr_cache_file, data):
            logger.info(f"DocTR setup results cached: success={success}, pytorch={pytorch_version}")
            if gpu_info:
                logger.info(f"GPU info cached: {gpu_info}")
        else:
            logger.warning("Failed to cache DocTR setup results")
    # Models Cache Methods
    def get_cached_models_status(self) -> Optional[Dict[str, Any]]:
        """Get cached models status"""
        if not self._is_cache_valid(self.models_cache_file, self.MODELS_CACHE_EXPIRY):
            return None
        return self._load_cache(self.models_cache_file)
    def cache_models_status(self, models_info: Dict[str, Any]):
        """Cache models status with logging"""
        import logging
        logger = logging.getLogger(__name__)
        data = {
            'timestamp': time.time(),
            **models_info
        }
        if self._save_cache(self.models_cache_file, data):
            model_count = sum(1 for v in models_info.values() if v)
            total_models = len(models_info)
            logger.info(f"Models status cached: {model_count}/{total_models} models available")
        else:
            logger.warning("Failed to cache models status")
    # System Info Cache Methods
    def get_cached_system_info(self) -> Optional[Dict[str, Any]]:
        """Get cached system information"""
        if not self._is_cache_valid(self.system_cache_file, self.SYSTEM_CACHE_EXPIRY):
            return None
        return self._load_cache(self.system_cache_file)
    def cache_system_info(self, system_info: Dict[str, Any]):
        """Cache system information"""
        data = {
            'timestamp': time.time(),
            **system_info
        }
        self._save_cache(self.system_cache_file, data)
    def clear_cache(self, cache_type: str = None):
        """Clear cache files with enhanced logging"""
        import logging
        logger = logging.getLogger(__name__)
        cache_files = {
            'doctr': self.doctr_cache_file,
            'models': self.models_cache_file,
            'system': self.system_cache_file,
            'config': self.config_cache_file
        }
        if cache_type:
            if cache_type in cache_files:
                try:
                    cache_files[cache_type].unlink(missing_ok=True)
                    logger.info(f"Cleared {cache_type} cache successfully")
                except Exception as e:
                    logger.warning(f"Failed to clear {cache_type} cache: {e}")
        else:
            # Clear all caches
            cleared_count = 0
            for name, file_path in cache_files.items():
                try:
                    file_path.unlink(missing_ok=True)
                    cleared_count += 1
                    logger.info(f"Cleared {name} cache")
                except Exception as e:
                    logger.warning(f"Failed to clear {name} cache: {e}")
            logger.info(f"Cache cleanup complete: {cleared_count}/{len(cache_files)} caches cleared")
# Global cache instance
startup_cache = StartupCache()
# Backward compatibility functions
def get_cached_doctr_setup():
    return startup_cache.get_cached_doctr_setup()
def cache_doctr_setup(success: bool, pytorch_version: str = None, gpu_info: str = None):
    startup_cache.cache_doctr_setup(success, pytorch_version, gpu_info)
def get_cached_models_status():
    return startup_cache.get_cached_models_status()
def cache_models_status(models_info: Dict[str, Any]):
    startup_cache.cache_models_status(models_info)
