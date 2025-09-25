# coding: utf-8
"""
ConfigWatcher Performance-Optimized Version
High-performance configuration hot-reload system with intelligent caching,
efficient change detection, and minimal resource consumption.
"""

__version__ = '1.1.0'
__author__ = 'ConfigWatcher Team'
__license__ = 'MIT'

import os
import sys
import json
import yaml
import time
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional, Union, Tuple, Set
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
import weakref
import mmap

# Add the decouple module to our path
sys.path.insert(0, '/tmp/inputs/pythondecouple')
from decouple import Config, RepositoryEmpty, DEFAULT_ENCODING

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Performance monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class PerformanceMonitor:
    """Lightweight performance monitoring for ConfigWatcher."""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled and PSUTIL_AVAILABLE
        self.process = None
        self.stats = {
            'cpu_percent': 0.0,
            'memory_mb': 0.0,
            'io_reads': 0,
            'io_writes': 0,
            'thread_count': 0
        }
        
        if self.enabled:
            try:
                self.process = psutil.Process()
            except:
                self.enabled = False
    
    def update_stats(self):
        """Update performance statistics."""
        if not self.enabled:
            return
        
        try:
            self.stats['cpu_percent'] = self.process.cpu_percent()
            self.stats['memory_mb'] = self.process.memory_info().rss / 1024 / 1024
            self.stats['thread_count'] = self.process.num_threads()
            
            # IO stats if available
            try:
                io_counters = self.process.io_counters()
                self.stats['io_reads'] = io_counters.read_count
                self.stats['io_writes'] = io_counters.write_count
            except:
                pass
        except:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        if self.enabled:
            self.update_stats()
        return self.stats.copy()


class FastFileHasher:
    """Efficient file hashing with caching and memory mapping."""
    
    def __init__(self, cache_size: int = 1000):
        self._hash_cache = OrderedDict()
        self._cache_size = cache_size
        self._mtime_cache = {}
        self._lock = threading.RLock()
    
    def get_file_hash(self, file_path: str, use_mmap: bool = True) -> Optional[str]:
        """Get file hash efficiently with caching."""
        try:
            stat = os.stat(file_path)
            mtime = stat.st_mtime
            size = stat.st_size
            
            # Check cache first
            cache_key = (file_path, mtime, size)
            
            with self._lock:
                if cache_key in self._hash_cache:
                    # Move to end (LRU)
                    self._hash_cache.move_to_end(cache_key)
                    return self._hash_cache[cache_key]
            
            # Compute hash efficiently
            if use_mmap and size > 1024:  # Use mmap for larger files
                file_hash = self._hash_with_mmap(file_path)
            else:
                file_hash = self._hash_simple(file_path)
            
            # Cache the result
            with self._lock:
                self._hash_cache[cache_key] = file_hash
                
                # Maintain cache size
                while len(self._hash_cache) > self._cache_size:
                    self._hash_cache.popitem(last=False)
            
            return file_hash
            
        except (OSError, IOError):
            return None
    
    def _hash_with_mmap(self, file_path: str) -> str:
        """Hash file using memory mapping for better performance."""
        hasher = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    # Read in chunks to avoid loading entire file
                    chunk_size = 8192
                    for i in range(0, len(mm), chunk_size):
                        chunk = mm[i:i + chunk_size]
                        hasher.update(chunk)
                        
            return hasher.hexdigest()
            
        except (OSError, ValueError):
            # Fall back to simple hashing
            return self._hash_simple(file_path)
    
    def _hash_simple(self, file_path: str) -> str:
        """Simple file hashing for small files."""
        hasher = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return ''
    
    def clear_cache(self):
        """Clear the hash cache."""
        with self._lock:
            self._hash_cache.clear()


class OptimizedConfigRepository:
    """Performance-optimized configuration repository with intelligent caching."""
    
    def __init__(self, source: str, encoding: str = DEFAULT_ENCODING):
        self.source = source
        self.encoding = encoding
        self.data = {}
        self.last_modified = 0
        self.last_hash = None
        self.format_type = self._detect_format()
        
        # Performance optimizations
        self._parse_cache = {}
        self._access_count = defaultdict(int)
        self._hot_keys = set()  # Frequently accessed keys
        
        # Efficient file monitoring
        self._file_size = 0
        self._inode = 0
        
        self._load_data()
    
    def _detect_format(self) -> str:
        """Detect configuration file format from extension."""
        suffix = Path(self.source).suffix.lower()
        format_map = {
            '.json': 'json',
            '.yaml': 'yaml', '.yml': 'yaml',
            '.ini': 'ini',
            '.env': 'env'
        }
        return format_map.get(suffix, 'env')
    
    def _get_file_stats(self) -> Tuple[float, int, int]:
        """Get file statistics efficiently."""
        try:
            stat = os.stat(self.source)
            return stat.st_mtime, stat.st_size, stat.st_ino
        except OSError:
            return 0, 0, 0
    
    def _load_data(self):
        """Load configuration data with performance optimizations."""
        if not os.path.exists(self.source):
            return
        
        mtime, size, inode = self._get_file_stats()
        self.last_modified = mtime
        self._file_size = size
        self._inode = inode
        
        # Cache key for parsed content
        cache_key = (self.source, mtime, size)
        
        if cache_key in self._parse_cache:
            self.data = self._parse_cache[cache_key]
            return
        
        try:
            # Choose optimal loading strategy based on file size
            if size > 1024 * 1024:  # > 1MB
                self.data = self._load_large_file()
            else:
                self.data = self._load_small_file()
            
            # Cache parsed content (limit cache size)
            if len(self._parse_cache) < 50:  # Reasonable cache size
                self._parse_cache[cache_key] = self.data.copy()
            
        except Exception as e:
            logging.error(f"Failed to load config from {self.source}: {e}")
            self.data = {}
    
    def _load_small_file(self) -> Dict[str, Any]:
        """Optimized loading for small files."""
        with open(self.source, 'r', encoding=self.encoding) as file:
            if self.format_type == 'json':
                return json.load(file)
            elif self.format_type == 'yaml':
                return yaml.safe_load(file) or {}
            elif self.format_type == 'ini':
                return self._parse_ini(file)
            else:  # env
                return self._parse_env(file)
    
    def _load_large_file(self) -> Dict[str, Any]:
        """Optimized loading for large files with streaming."""
        if self.format_type == 'json':
            # For large JSON, use streaming if possible
            with open(self.source, 'r', encoding=self.encoding) as file:
                return json.load(file)
        elif self.format_type == 'yaml':
            # YAML doesn't have good streaming support, load normally
            with open(self.source, 'r', encoding=self.encoding) as file:
                return yaml.safe_load(file) or {}
        else:
            # ENV and INI can be streamed line by line
            return self._stream_parse()
    
    def _stream_parse(self) -> Dict[str, Any]:
        """Stream-parse ENV/INI files line by line."""
        data = {}
        current_section = None
        
        with open(self.source, 'r', encoding=self.encoding) as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if self.format_type == 'ini':
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1]
                        continue
                    elif '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if current_section:
                            key = f"{current_section}.{key}"
                        data[key] = value
                
                elif self.format_type == 'env' and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    data[key] = value
        
        return data
    
    def _parse_ini(self, file) -> Dict[str, Any]:
        """Parse INI file efficiently."""
        from configparser import ConfigParser
        parser = ConfigParser()
        parser.read_file(file)
        
        data = {}
        for section in parser.sections():
            for key, value in parser.items(section):
                data[f"{section}.{key}"] = value
        return data
    
    def _parse_env(self, file) -> Dict[str, Any]:
        """Parse ENV file efficiently."""
        data = {}
        for line in file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            data[key] = value
        return data
    
    def has_changed(self) -> bool:
        """Efficiently check if file has changed."""
        if not os.path.exists(self.source):
            return bool(self.data)  # File was deleted
        
        mtime, size, inode = self._get_file_stats()
        
        # Quick checks for changes
        return (
            mtime > self.last_modified or 
            size != self._file_size or 
            inode != self._inode
        )
    
    def reload(self) -> bool:
        """Reload configuration if changed."""
        if not self.has_changed():
            return False
        
        old_data = self.data.copy()
        self._load_data()
        return old_data != self.data
    
    def get_hash(self) -> str:
        """Get hash of current configuration data."""
        if not self.last_hash:
            self.last_hash = hashlib.sha256(
                json.dumps(self.data, sort_keys=True).encode()
            ).hexdigest()
        return self.last_hash
    
    def __contains__(self, key):
        # Track access patterns for optimization
        self._access_count[key] += 1
        if self._access_count[key] > 10:
            self._hot_keys.add(key)
        return key in self.data
    
    def __getitem__(self, key):
        self._access_count[key] += 1
        if self._access_count[key] > 10:
            self._hot_keys.add(key)
        return self.data.get(key)


class EfficientEnvironmentWatcher:
    """Optimized environment variable watcher with batching and caching."""
    
    def __init__(self, variables: List[str], callback: Callable[[str, str, str], None]):
        self.variables = set(variables)  # Use set for O(1) lookups
        self.callback = callback
        self.last_values = {}
        self.running = False
        self.thread = None
        
        # Performance optimizations
        self.poll_interval = 2.0  # Increased default interval
        self.batch_size = 10  # Process changes in batches
        self.change_queue = []
        self.last_check = 0
        
        # Initialize values efficiently
        self._update_all_values()
    
    def _update_all_values(self):
        """Efficiently update all monitored environment variables."""
        for var in self.variables:
            self.last_values[var] = os.environ.get(var)
    
    def set_poll_interval(self, interval: float):
        """Set polling interval for performance tuning."""
        self.poll_interval = max(0.1, interval)  # Minimum 100ms
    
    def add_variables(self, variables: List[str]):
        """Add variables to monitor."""
        new_vars = set(variables) - self.variables
        self.variables.update(new_vars)
        
        # Initialize new variables
        for var in new_vars:
            self.last_values[var] = os.environ.get(var)
    
    def remove_variables(self, variables: List[str]):
        """Remove variables from monitoring."""
        for var in variables:
            self.variables.discard(var)
            self.last_values.pop(var, None)
    
    def start(self):
        """Start monitoring with optimized polling."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._optimized_monitor_loop, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _optimized_monitor_loop(self):
        """Optimized monitoring loop with batching and adaptive intervals."""
        consecutive_no_changes = 0
        adaptive_interval = self.poll_interval
        
        while self.running:
            current_time = time.time()
            changes_detected = 0
            
            # Batch check all variables
            for var in self.variables:
                current_value = os.environ.get(var)
                last_value = self.last_values.get(var)
                
                if current_value != last_value:
                    self.change_queue.append((var, last_value, current_value))
                    self.last_values[var] = current_value
                    changes_detected += 1
            
            # Process changes in batches
            if self.change_queue:
                self._process_change_batch()
                consecutive_no_changes = 0
                adaptive_interval = self.poll_interval  # Reset to normal interval
            else:
                consecutive_no_changes += 1
                # Adaptive polling: slow down if no changes detected
                if consecutive_no_changes > 5:
                    adaptive_interval = min(self.poll_interval * 2, 10.0)
            
            self.last_check = current_time
            time.sleep(adaptive_interval)
    
    def _process_change_batch(self):
        """Process a batch of environment variable changes."""
        batch = self.change_queue[:self.batch_size]
        self.change_queue = self.change_queue[self.batch_size:]
        
        for var, old_value, new_value in batch:
            try:
                self.callback(var, old_value, new_value)
            except Exception as e:
                logging.error(f"Error in environment change callback for {var}: {e}")


class OptimizedFileSystemWatcher(FileSystemEventHandler):
    """Optimized filesystem event handler with debouncing and batching."""
    
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self.event_queue = defaultdict(list)
        self.debounce_interval = 0.5
        self.batch_timer = None
        self.lock = threading.RLock()
    
    def on_modified(self, event):
        """Handle file modification with intelligent batching."""
        if event.is_directory:
            return
        
        current_time = time.time()
        
        with self.lock:
            self.event_queue[event.src_path].append(current_time)
            
            # Clean old events (beyond debounce window)
            cutoff = current_time - self.debounce_interval
            self.event_queue[event.src_path] = [
                t for t in self.event_queue[event.src_path] if t > cutoff
            ]
            
            # Cancel existing timer and start new one
            if self.batch_timer:
                self.batch_timer.cancel()
            
            self.batch_timer = threading.Timer(
                self.debounce_interval, 
                self._process_events
            )
            self.batch_timer.start()
    
    def _process_events(self):
        """Process batched file system events."""
        with self.lock:
            current_time = time.time()
            cutoff = current_time - self.debounce_interval
            
            # Process files that have stabilized (no recent events)
            for file_path, event_times in list(self.event_queue.items()):
                if event_times and max(event_times) < cutoff:
                    try:
                        self.callback(file_path)
                    except Exception as e:
                        logging.error(f"Error processing file change {file_path}: {e}")
                    finally:
                        del self.event_queue[file_path]


class ConfigWatcherOptimized:
    """
    High-performance ConfigWatcher with optimized resource usage.
    
    Key optimizations:
    - Intelligent caching and memoization
    - Efficient file change detection
    - Batched environment variable monitoring
    - Adaptive polling intervals
    - Memory-mapped file reading
    - Thread pool management
    - Performance monitoring
    """
    
    def __init__(self, 
                 config_files: Optional[List[str]] = None,
                 env_variables: Optional[List[str]] = None,
                 validators: Optional[List] = None,
                 poll_interval: float = 2.0,  # Increased default
                 enable_filesystem_watching: bool = True,
                 fallback_on_error: bool = True,
                 enable_performance_monitoring: bool = False,
                 max_cache_size: int = 1000,
                 thread_pool_size: int = 2):
        
        self.config_files = config_files or []
        self.env_variables = env_variables or []
        self.validators = validators or []
        self.poll_interval = poll_interval
        self.enable_filesystem_watching = enable_filesystem_watching
        self.fallback_on_error = fallback_on_error
        
        # Performance optimizations
        self.max_cache_size = max_cache_size
        self.thread_pool_size = thread_pool_size
        
        # Internal state with optimizations
        self._lock = threading.RLock()
        self._config = Config(RepositoryEmpty())
        self._repositories = {}
        self._config_data = {}
        self._backup_config = {}
        self._callbacks = []
        self._running = False
        
        # Performance components
        self.performance_monitor = PerformanceMonitor(enable_performance_monitoring)
        self.file_hasher = FastFileHasher(max_cache_size)
        self.thread_pool = ThreadPoolExecutor(max_workers=thread_pool_size)
        
        # Monitoring components
        self._observer = None
        self._env_watcher = None
        self._poll_thread = None
        
        # Optimization caches
        self._validation_cache = OrderedDict()
        self._callback_cache = weakref.WeakSet()  # Weak references to avoid memory leaks
        
        # Statistics
        self.stats = {
            'config_reloads': 0,
            'validation_runs': 0,
            'callback_executions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'last_reload_time': 0
        }
        
        # Logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize
        self._initialize_repositories()
        self._load_initial_config()
    
    def _initialize_repositories(self):
        """Initialize optimized configuration repositories."""
        for config_file in self.config_files:
            if os.path.exists(config_file):
                self._repositories[config_file] = OptimizedConfigRepository(config_file)
            else:
                self.logger.warning(f"Configuration file not found: {config_file}")
    
    def _load_initial_config(self):
        """Load initial configuration with caching."""
        with self._lock:
            self._config_data = {}
            
            # Load from repositories efficiently
            for repo in self._repositories.values():
                self._config_data.update(repo.data)
            
            # Environment variables override file config
            if self.env_variables:
                env_data = {var: os.environ.get(var) for var in self.env_variables}
                env_data = {k: v for k, v in env_data.items() if v is not None}
                self._config_data.update(env_data)
            
            # Create backup
            self._backup_config = self._config_data.copy()
            
            # Update main config
            self._config = Config(DictRepository(self._config_data))
            
            self.logger.info(f"Loaded initial configuration with {len(self._config_data)} keys")
    
    def start_watching(self):
        """Start optimized configuration monitoring."""
        if self._running:
            return
        
        self._running = True
        
        try:
            # Start filesystem watching with optimization
            if self.enable_filesystem_watching and WATCHDOG_AVAILABLE and self.config_files:
                self._start_optimized_filesystem_watching()
            
            # Start environment variable watching with optimization
            if self.env_variables:
                self._env_watcher = EfficientEnvironmentWatcher(
                    self.env_variables, 
                    self._on_env_change
                )
                self._env_watcher.set_poll_interval(self.poll_interval)
                self._env_watcher.start()
            
            # Start polling thread as fallback
            if not WATCHDOG_AVAILABLE or not self.enable_filesystem_watching:
                self._start_optimized_polling()
            
            self.logger.info("Optimized configuration watching started")
            
        except Exception as e:
            self.logger.error(f"Failed to start configuration watching: {e}")
            self._running = False
            raise
    
    def stop_watching(self):
        """Stop configuration monitoring and cleanup resources."""
        self._running = False
        
        # Stop filesystem observer
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        
        # Stop environment watcher
        if self._env_watcher:
            self._env_watcher.stop()
            self._env_watcher = None
        
        # Stop polling thread
        if self._poll_thread:
            self._poll_thread.join()
            self._poll_thread = None
        
        # Cleanup thread pool
        self.thread_pool.shutdown(wait=True)
        
        # Clear caches
        self.file_hasher.clear_cache()
        self._validation_cache.clear()
        
        self.logger.info("Optimized configuration watching stopped")
    
    def _start_optimized_filesystem_watching(self):
        """Start filesystem watching with optimizations."""
        self._observer = Observer()
        handler = OptimizedFileSystemWatcher(self._on_file_change)
        
        # Watch only unique directories to reduce overhead
        watched_dirs = set()
        for config_file in self.config_files:
            if os.path.exists(config_file):
                dir_path = os.path.dirname(os.path.abspath(config_file))
                if dir_path not in watched_dirs:
                    self._observer.schedule(handler, dir_path, recursive=False)
                    watched_dirs.add(dir_path)
        
        self._observer.start()
        self.logger.info(f"Started optimized filesystem watching for {len(watched_dirs)} directories")
    
    def _start_optimized_polling(self):
        """Start optimized polling with adaptive intervals."""
        def adaptive_poll_loop():
            consecutive_no_changes = 0
            current_interval = self.poll_interval
            
            while self._running:
                try:
                    changes_detected = self._check_file_changes_batch()
                    
                    if changes_detected:
                        consecutive_no_changes = 0
                        current_interval = self.poll_interval
                    else:
                        consecutive_no_changes += 1
                        # Adaptive interval: slow down if no changes
                        if consecutive_no_changes > 3:
                            current_interval = min(self.poll_interval * 1.5, 10.0)
                    
                    time.sleep(current_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in polling loop: {e}")
                    time.sleep(self.poll_interval)
        
        self._poll_thread = threading.Thread(target=adaptive_poll_loop, daemon=True)
        self._poll_thread.start()
        self.logger.info("Started optimized polling-based monitoring")
    
    def _check_file_changes_batch(self) -> bool:
        """Check for file changes in batch with parallel processing."""
        if not self._repositories:
            return False
        
        changes_detected = False
        
        # Use thread pool for parallel file checking
        future_to_file = {
            self.thread_pool.submit(self._check_single_file, config_file, repo): config_file
            for config_file, repo in self._repositories.items()
        }
        
        for future in future_to_file:
            try:
                if future.result():  # File changed
                    config_file = future_to_file[future]
                    self._on_file_change(config_file)
                    changes_detected = True
            except Exception as e:
                config_file = future_to_file[future]
                self.logger.error(f"Error checking file {config_file}: {e}")
        
        return changes_detected
    
    def _check_single_file(self, config_file: str, repo: OptimizedConfigRepository) -> bool:
        """Check if a single file has changed."""
        return repo.has_changed()
    
    def _on_file_change(self, file_path: str):
        """Handle file change events with optimization."""
        if file_path not in self._repositories:
            return
        
        self.logger.debug(f"Configuration file changed: {file_path}")
        
        try:
            repo = self._repositories[file_path]
            if repo.reload():
                # File actually changed, trigger reload
                self.thread_pool.submit(self._reload_configuration_async)
                
        except Exception as e:
            self.logger.error(f"Failed to process file change {file_path}: {e}")
    
    def _on_env_change(self, variable: str, old_value: str, new_value: str):
        """Handle environment variable changes."""
        self.logger.debug(f"Environment variable changed: {variable} = {new_value}")
        
        # Use thread pool for async processing
        self.thread_pool.submit(self._reload_configuration_async)
    
    def _reload_configuration_async(self):
        """Asynchronously reload configuration."""
        try:
            self._reload_configuration_optimized()
        except Exception as e:
            self.logger.error(f"Async configuration reload failed: {e}")
    
    def _reload_configuration_optimized(self, changes=None):
        """Optimized configuration reload with caching and batching."""
        start_time = time.time()
        
        with self._lock:
            try:
                # Build new configuration efficiently
                new_config_data = {}
                
                # Load from repositories
                for repo in self._repositories.values():
                    new_config_data.update(repo.data)
                
                # Environment variables override file config
                if self.env_variables:
                    for var in self.env_variables:
                        value = os.environ.get(var)
                        if value is not None:
                            new_config_data[var] = value
                
                # Check if anything actually changed
                if new_config_data == self._config_data:
                    self.stats['cache_hits'] += 1
                    return  # No changes, skip expensive operations
                
                self.stats['cache_misses'] += 1
                
                # Validate new configuration with caching
                validation_result = self._validate_config_cached(new_config_data)
                
                if validation_result.is_valid:
                    # Detect changes efficiently
                    if changes is None:
                        changes = self._detect_changes_optimized(
                            self._config_data, new_config_data
                        )
                    
                    # Update configuration
                    self._config_data = new_config_data
                    self._config = Config(DictRepository(self._config_data))
                    
                    # Update backup on successful reload
                    self._backup_config = self._config_data.copy()
                    
                    # Notify callbacks asynchronously
                    if changes:
                        self.thread_pool.submit(self._notify_callbacks_async, changes)
                    
                    # Update statistics
                    self.stats['config_reloads'] += 1
                    self.stats['last_reload_time'] = time.time()
                    
                    reload_time = time.time() - start_time
                    self.logger.info(
                        f"Configuration reloaded in {reload_time:.3f}s with {len(changes)} changes"
                    )
                    
                    # Log warnings
                    for warning in validation_result.warnings:
                        self.logger.warning(f"Configuration warning: {warning}")
                        
                else:
                    # Validation failed
                    self.logger.error(f"Configuration validation failed: {validation_result.errors}")
                    
                    if self.fallback_on_error:
                        self.logger.info("Using fallback configuration")
                    else:
                        raise ValueError(f"Configuration validation failed: {validation_result.errors}")
                        
            except Exception as e:
                self.logger.error(f"Failed to reload configuration: {e}")
                
                if self.fallback_on_error:
                    self.logger.info("Reverting to backup configuration")
                    self._config_data = self._backup_config.copy()
                    self._config = Config(DictRepository(self._config_data))
                else:
                    raise
    
    def _validate_config_cached(self, config_data: Dict[str, Any]):
        """Validate configuration with result caching."""
        # Create cache key from config hash
        config_hash = hashlib.sha256(
            json.dumps(config_data, sort_keys=True).encode()
        ).hexdigest()[:16]  # Short hash for cache key
        
        if config_hash in self._validation_cache:
            self.stats['cache_hits'] += 1
            return self._validation_cache[config_hash]
        
        # Run validation
        from config_watcher import ValidationResult
        combined_result = ValidationResult(is_valid=True)
        
        for validator in self.validators:
            try:
                result = validator.validate(config_data)
                combined_result.errors.extend(result.errors)
                combined_result.warnings.extend(result.warnings)
                
                if not result.is_valid:
                    combined_result.is_valid = False
                    
            except Exception as e:
                self.logger.error(f"Validator error: {e}")
                combined_result.errors.append(f"Validator exception: {e}")
                combined_result.is_valid = False
        
        # Cache result (with size limit)
        if len(self._validation_cache) >= self.max_cache_size:
            self._validation_cache.popitem(last=False)  # Remove oldest
        
        self._validation_cache[config_hash] = combined_result
        self.stats['validation_runs'] += 1
        self.stats['cache_misses'] += 1
        
        return combined_result
    
    def _detect_changes_optimized(self, old_config: Dict[str, Any], 
                                new_config: Dict[str, Any]) -> List:
        """Optimized change detection using set operations."""
        from config_watcher import ConfigChange, ConfigChangeType
        
        changes = []
        old_keys = set(old_config.keys())
        new_keys = set(new_config.keys())
        
        # Added keys
        added_keys = new_keys - old_keys
        for key in added_keys:
            changes.append(ConfigChange(
                change_type=ConfigChangeType.ADDED,
                source="file",
                key=key,
                new_value=new_config[key]
            ))
        
        # Deleted keys
        deleted_keys = old_keys - new_keys
        for key in deleted_keys:
            changes.append(ConfigChange(
                change_type=ConfigChangeType.DELETED,
                source="file",
                key=key,
                old_value=old_config[key]
            ))
        
        # Modified keys (only check common keys)
        common_keys = old_keys & new_keys
        for key in common_keys:
            if old_config[key] != new_config[key]:
                changes.append(ConfigChange(
                    change_type=ConfigChangeType.MODIFIED,
                    source="file",
                    key=key,
                    old_value=old_config[key],
                    new_value=new_config[key]
                ))
        
        return changes
    
    def _notify_callbacks_async(self, changes):
        """Asynchronously notify callbacks."""
        self.stats['callback_executions'] += 1
        
        for callback in self._callbacks:
            try:
                callback(changes)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")
    
    def add_callback(self, callback: Callable):
        """Add a callback with weak reference tracking."""
        with self._lock:
            self._callbacks.append(callback)
            self._callback_cache.add(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove a callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
            self._callback_cache.discard(callback)
    
    def get_config(self):
        """Get current configuration object."""
        with self._lock:
            return self._config
    
    def get_raw_config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        with self._lock:
            return self._config_data.copy()
    
    def force_reload(self):
        """Force configuration reload."""
        self.logger.info("Forcing configuration reload")
        self._reload_configuration_optimized()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        perf_stats = self.performance_monitor.get_stats()
        
        return {
            'system_performance': perf_stats,
            'configwatcher_stats': self.stats.copy(),
            'cache_stats': {
                'validation_cache_size': len(self._validation_cache),
                'hash_cache_size': len(self.file_hasher._hash_cache),
                'max_cache_size': self.max_cache_size
            },
            'monitoring_info': {
                'config_files': len(self.config_files),
                'env_variables': len(self.env_variables),
                'callbacks': len(self._callbacks),
                'thread_pool_size': self.thread_pool_size
            }
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status with performance info."""
        with self._lock:
            base_status = {
                'running': self._running,
                'config_files': self.config_files,
                'env_variables': self.env_variables,
                'num_validators': len(self.validators),
                'num_callbacks': len(self._callbacks),
                'config_keys': len(self._config_data),
                'filesystem_watching': self._observer is not None,
                'env_watching': self._env_watcher is not None,
                'polling': self._poll_thread is not None
            }
            
            # Add performance stats if available
            base_status['performance'] = self.get_performance_stats()
            
            return base_status
    
    def optimize_for_workload(self, workload_type: str = "balanced"):
        """Optimize settings for specific workload types."""
        if workload_type == "high_frequency":
            # High frequency changes
            self.poll_interval = 0.5
            if self._env_watcher:
                self._env_watcher.set_poll_interval(0.5)
            
        elif workload_type == "low_frequency":
            # Infrequent changes, optimize for resources
            self.poll_interval = 5.0
            if self._env_watcher:
                self._env_watcher.set_poll_interval(5.0)
                
        elif workload_type == "memory_constrained":
            # Reduce memory usage
            self.max_cache_size = 100
            self.file_hasher._cache_size = 100
            
        elif workload_type == "cpu_constrained":
            # Reduce CPU usage
            self.poll_interval = 10.0
            if self._env_watcher:
                self._env_watcher.set_poll_interval(10.0)
        
        self.logger.info(f"Optimized for {workload_type} workload")
    
    def __enter__(self):
        self.start_watching()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_watching()


class DictRepository:
    """Optimized dictionary repository."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
    
    def __contains__(self, key):
        return key in self.data
    
    def __getitem__(self, key):
        return self.data.get(key)


# Convenience function for easy migration
def create_optimized_watcher(*args, **kwargs) -> ConfigWatcherOptimized:
    """Create an optimized ConfigWatcher instance."""
    return ConfigWatcherOptimized(*args, **kwargs)
