# utils/startup_config.py
"""
Startup Configuration Manager for VisionLane OCR
Merges all configuration settings into config.ini with default values
Uses maximum CPU threads for optimal performance
"""

import configparser
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

class StartupConfig:
    """Manages unified configuration with startup and runtime settings"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config.ini"
        self.config = configparser.ConfigParser()

        # Get max CPU threads
        self.max_cpu_threads = os.cpu_count() or 4

        self.load_config()
        self.ensure_all_sections()

    def load_config(self):
        """Load main configuration"""
        try:
            if self.config_path.exists():
                self.config.read(self.config_path, encoding="utf-8")
                logger.info(f"Loaded config from {self.config_path}")
            else:
                logger.info("Config file not found, creating with defaults")
                self.create_default_config()
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            self.create_default_config()

    def create_default_config(self):
        """Create default configuration structure with all sections"""
        self.add_general_section()
        self.add_startup_section()
        self.add_paths_section()
        self.add_performance_section()
        self.save_config()

    def add_general_section(self):
        """Add General section with defaults (only if section doesn't exist)"""
        if not self.config.has_section('General'):
            self.config.add_section('General')

            general_defaults = {
                'dpi': 'Auto',
                'output_format': 'PDF',
                'theme_mode': 'system',
                'detection_model': 'db_resnet50',
                'recognition_model': 'parseq',
                'compress_enabled': 'False',
                'compression_type': 'jpeg',
                'compression_quality': '100',
                'archive_enabled': 'False'
            }

            for key, value in general_defaults.items():
                self.config.set('General', key, value)

    def add_startup_section(self):
        """Add Startup section with defaults using max CPU threads"""
        if not self.config.has_section('Startup'):
            self.config.add_section('Startup')

        startup_defaults = {
            'enable_parallel_loading': 'True',
            'show_detailed_progress': 'True',
            'cache_validation_results': 'True',
            'skip_doctr_setup_check': 'False',
            'skip_model_validation': 'False',
            'auto_download_models': 'True',
            'use_minimal_diagnostics': 'False',
            'startup_timeout': '120',
            'max_parallel_workers': str(self.max_cpu_threads),
            'cache_expiry_hours': '24',
            'skip_system_diagnostics': 'False'
        }

        for key, value in startup_defaults.items():
            if not self.config.has_option('Startup', key):
                self.config.set('Startup', key, value)

    def add_paths_section(self):
        """Add Paths section with defaults"""
        if not self.config.has_section('Paths'):
            self.config.add_section('Paths')

        paths_defaults = {
            'archive_single': '',
            'archive_folder': '',
            'archive_pdf': '',
            'single': '',
            'folder': '',
            'pdf': '',
            'output_single': '',
            'output_folder': '',
            'output_pdf': ''
        }

        for key, value in paths_defaults.items():
            if not self.config.has_option('Paths', key):
                self.config.set('Paths', key, value)

    def add_performance_section(self):
        """Add Performance section with max CPU threads"""
        if not self.config.has_section('Performance'):
            self.config.add_section('Performance')

        performance_defaults = {
            'thread_count': str(self.max_cpu_threads),
            'operation_timeout': '300',
            'chunk_timeout': '60'
        }

        for key, value in performance_defaults.items():
            if not self.config.has_option('Performance', key):
                self.config.set('Performance', key, value)

    def save_config(self):
        """Save configuration to config.ini with proper section ordering and warnings"""
        try:
            # Create a new config parser to control ordering
            ordered_config = configparser.ConfigParser()
            
            # Add sections in desired order
            
            # 1. General section
            if self.config.has_section('General'):
                ordered_config.add_section('General')
                for key, value in self.config.items('General'):
                    ordered_config.set('General', key, value)
            
            # 2. Paths section
            if self.config.has_section('Paths'):
                ordered_config.add_section('Paths')
                for key, value in self.config.items('Paths'):
                    ordered_config.set('Paths', key, value)
            
            # 3. Performance section
            if self.config.has_section('Performance'):
                ordered_config.add_section('Performance')
                for key, value in self.config.items('Performance'):
                    ordered_config.set('Performance', key, value)
            
            # 4. Startup section (LAST with warning)
            if self.config.has_section('Startup'):
                ordered_config.add_section('Startup')
                for key, value in self.config.items('Startup'):
                    ordered_config.set('Startup', key, value)
            
            # Write to file with custom formatting
            with open(self.config_path, 'w', encoding="utf-8") as f:
                # Write sections manually to add comments
                for section_name in ordered_config.sections():
                    if section_name == 'Startup':
                        # Add warning comment before Startup section
                        f.write('\n# ============================================================================\n')
                        f.write('# EXPERIMENTAL STARTUP CONFIGURATION - PLEASE DO NOT EDIT\n')
                        f.write('# These settings control advanced startup behavior and parallel loading.\n')
                        f.write('# Modifying these values may cause application instability or startup failures.\n')
                        f.write('# Only change these settings if you understand the technical implications.\n')
                        f.write('# ============================================================================\n')
                    
                    f.write(f'[{section_name}]\n')
                    
                    for key, value in ordered_config.items(section_name):
                        f.write(f'{key} = {value}\n')
                    
                    f.write('\n')  # Add blank line after each section
            
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def ensure_all_sections(self):
        """Ensure all sections exist with default values, but preserve existing values"""
        changed = False

        # Ensure sections exist in the correct order
        required_sections = ['General', 'Paths', 'Performance', 'Startup']
        
        for section in required_sections:
            if not self.config.has_section(section):
                self.config.add_section(section)
                changed = True

        # General section defaults
        if not self.config.has_section('General'):
            self.add_general_section()
            changed = True
        else:
            general_defaults = {
                'dpi': 'Auto',
                'output_format': 'PDF',
                'theme_mode': 'system',
                'detection_model': 'db_resnet50',
                'recognition_model': 'parseq',
                'compress_enabled': 'False',
                'compression_type': 'jpeg',
                'compression_quality': '100',
                'archive_enabled': 'False'
            }
            for key, value in general_defaults.items():
                if not self.config.has_option('General', key):
                    self.config.set('General', key, value)
                    changed = True

        # Paths section defaults
        if not self.config.has_section('Paths'):
            self.add_paths_section()
            changed = True
        else:
            paths_defaults = {
                'archive_single': '',
                'archive_folder': '',
                'archive_pdf': '',
                'single': '',
                'folder': '',
                'pdf': '',
                'output_single': '',
                'output_folder': '',
                'output_pdf': ''
            }
            for key, value in paths_defaults.items():
                if not self.config.has_option('Paths', key):
                    self.config.set('Paths', key, value)
                    changed = True

        # Performance section defaults
        if not self.config.has_section('Performance'):
            self.add_performance_section()
            changed = True
        else:
            performance_defaults = {
                'thread_count': str(self.max_cpu_threads),
                'operation_timeout': '300',
                'chunk_timeout': '60'
            }
            for key, value in performance_defaults.items():
                if not self.config.has_option('Performance', key):
                    self.config.set('Performance', key, value)
                    changed = True

        # Startup section defaults (LAST)
        if not self.config.has_section('Startup'):
            self.add_startup_section()
            changed = True
        else:
            startup_defaults = {
                'enable_parallel_loading': 'True',
                'show_detailed_progress': 'True',
                'cache_validation_results': 'True',
                'skip_doctr_setup_check': 'False',
                'skip_model_validation': 'False',
                'auto_download_models': 'True',
                'use_minimal_diagnostics': 'False',
                'startup_timeout': '120',
                'max_parallel_workers': str(self.max_cpu_threads),
                'cache_expiry_hours': '24',
                'skip_system_diagnostics': 'False'
            }
            for key, value in startup_defaults.items():
                if not self.config.has_option('Startup', key):
                    self.config.set('Startup', key, value)
                    changed = True

        if changed:
            self.save_config()

    def get_startup_option(self, key: str, default: Any = None) -> Any:
        """Get a startup option value"""
        try:
            if self.config.has_option('Startup', key):
                value = self.config.get('Startup', key)
                if value.lower() in ('true', 'false'):
                    return value.lower() == 'true'
                try:
                    return int(value)
                except ValueError:
                    try:
                        return float(value)
                    except ValueError:
                        return value
            return default
        except Exception as e:
            logger.warning(f"Failed to get startup option {key}: {e}")
            return default

    def set_startup_option(self, key: str, value: Any):
        """Set a startup option value"""
        try:
            if not self.config.has_section('Startup'):
                self.config.add_section('Startup')
            self.config.set('Startup', key, str(value))
            self.save_config()
        except Exception as e:
            logger.error(f"Failed to set startup option {key}: {e}")

    def should_use_parallel_loading(self) -> bool:
        return self.get_startup_option('enable_parallel_loading', True)

    def should_show_detailed_progress(self) -> bool:
        return self.get_startup_option('show_detailed_progress', True)

    def should_cache_results(self) -> bool:
        return self.get_startup_option('cache_validation_results', True)

    def should_skip_doctr_check(self) -> bool:
        return self.get_startup_option('skip_doctr_setup_check', False)

    def should_skip_model_validation(self) -> bool:
        return self.get_startup_option('skip_model_validation', False)

    def should_auto_download_models(self) -> bool:
        return self.get_startup_option('auto_download_models', True)

    def use_minimal_diagnostics(self) -> bool:
        return self.get_startup_option('use_minimal_diagnostics', False)

    def get_startup_timeout(self) -> int:
        return self.get_startup_option('startup_timeout', 120)

    def get_max_parallel_workers(self) -> int:
        return self.get_startup_option('max_parallel_workers', self.max_cpu_threads)

    def get_cache_expiry_hours(self) -> int:
        return self.get_startup_option('cache_expiry_hours', 24)

    def should_skip_system_diagnostics(self) -> bool:
        return self.get_startup_option("skip_system_diagnostics", False)

    def get_all_options(self) -> Dict[str, Any]:
        options = {}
        if self.config.has_section('Startup'):
            for key in self.config.options('Startup'):
                options[key] = self.get_startup_option(key)
        return options

    def reset_to_defaults(self):
        for section in self.config.sections():
            self.config.remove_section(section)
        self.create_default_config()
        logger.info("Reset all configuration to defaults")

    def get_summary(self) -> str:
        parallel = "enabled" if self.should_use_parallel_loading() else "disabled"
        detailed = "enabled" if self.should_show_detailed_progress() else "disabled"
        caching = "enabled" if self.should_cache_results() else "disabled"

        return f"""
Startup Configuration Summary:
- Parallel loading: {parallel}
- Detailed progress: {detailed}
- Result caching: {caching}
- Startup timeout: {self.get_startup_timeout()}s
- Max workers: {self.get_max_parallel_workers()}
- CPU threads available: {self.max_cpu_threads}
        """.strip()

    def is_fast_startup_mode(self) -> bool:
        return self.get_startup_option("fast_startup_mode", False)

    def get_models_config(self) -> Dict[str, str]:
        return {
            'detection_model': self.config.get('General', 'detection_model', fallback='db_resnet50'),
            'recognition_model': self.config.get('General', 'recognition_model', fallback='parseq')
        }
