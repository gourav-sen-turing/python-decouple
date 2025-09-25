#!/usr/bin/env python3
"""
Real-world ConfigWatcher performance demonstration.
Shows the performance improvements in realistic scenarios.
"""

import os
import sys
import time
import json
import yaml
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import logging

# Import both versions
from config_watcher import ConfigWatcher as OriginalConfigWatcher
from config_watcher_optimized import ConfigWatcherOptimized

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_realistic_configs():
    """Create realistic configuration files for testing."""
    
    # Large application configuration
    app_config = {
        "application": {
            "name": "MyApp",
            "version": "1.0.0",
            "environment": "production",
            "debug": False
        },
        "database": {
            "primary": {
                "host": "db1.example.com",
                "port": 5432,
                "database": "myapp_prod",
                "username": "appuser",
                "password": "secure_password",
                "pool_size": 20,
                "timeout": 30.0,
                "ssl_mode": "require"
            },
            "replica": {
                "host": "db2.example.com",
                "port": 5432,
                "database": "myapp_prod",
                "username": "readonly",
                "password": "readonly_password",
                "pool_size": 10
            }
        },
        "cache": {
            "redis": {
                "host": "cache.example.com",
                "port": 6379,
                "db": 0,
                "password": "cache_password",
                "timeout": 5.0
            },
            "memcached": {
                "servers": ["mc1.example.com:11211", "mc2.example.com:11211"],
                "timeout": 2.0
            }
        },
        "api": {
            "rate_limits": {
                "anonymous": 100,
                "authenticated": 1000,
                "premium": 10000
            },
            "timeouts": {
                "connect": 5.0,
                "read": 30.0,
                "write": 10.0
            }
        },
        "features": {
            f"feature_{i}": {
                "enabled": i % 3 == 0,
                "rollout_percentage": min(i * 5, 100),
                "config": {
                    "param1": f"value_{i}",
                    "param2": i * 10,
                    "param3": i % 2 == 0
                }
            } for i in range(50)  # 50 feature flags
        },
        "monitoring": {
            "metrics": {
                "enabled": True,
                "interval": 60,
                "endpoint": "metrics.example.com"
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "outputs": ["stdout", "file", "syslog"]
            }
        }
    }
    
    # Create JSON file
    json_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(app_config, json_file, indent=2)
    json_file.close()
    
    # Create YAML file with different structure
    yaml_config = {
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
            "workers": 4,
            "max_connections": 1000
        },
        "security": {
            "jwt_secret": "jwt_secret_key",
            "session_timeout": 3600,
            "csrf_protection": True
        },
        "external_apis": {
            f"api_{i}": {
                "url": f"https://api{i}.example.com",
                "key": f"api_key_{i}",
                "timeout": 30.0,
                "retry_count": 3
            } for i in range(10)
        }
    }
    
    yaml_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(yaml_config, yaml_file)
    yaml_file.close()
    
    # Create ENV file
    env_content = '\n'.join([
        "# Production environment variables",
        "NODE_ENV=production",
        "LOG_LEVEL=INFO",
        "DATABASE_URL=postgresql://user:pass@localhost/db",
        "REDIS_URL=redis://localhost:6379",
        "API_BASE_URL=https://api.example.com",
        "JWT_SECRET=your_jwt_secret_here",
        "SESSION_SECRET=your_session_secret",
        "SMTP_HOST=smtp.example.com",
        "SMTP_PORT=587",
        "EMAIL_FROM=noreply@example.com"
    ] + [f"FEATURE_{i}_ENABLED={'true' if i % 2 == 0 else 'false'}" for i in range(20)])
    
    env_file = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
    env_file.write(env_content)
    env_file.close()
    
    return [json_file.name, yaml_file.name, env_file.name]


def simulate_realistic_usage(watcher, duration=10, operations_per_second=10):
    """Simulate realistic configuration access patterns."""
    
    config = watcher.get_config()
    operations_count = 0
    errors = []
    
    start_time = time.time()
    end_time = start_time + duration
    
    # Common configuration keys that applications frequently access
    common_keys = [
        'database.primary.host', 'database.primary.port', 'database.primary.pool_size',
        'cache.redis.host', 'cache.redis.port',
        'api.rate_limits.authenticated', 'api.timeouts.read',
        'NODE_ENV', 'LOG_LEVEL', 'DATABASE_URL',
        'server.port', 'server.workers',
        'security.jwt_secret', 'security.session_timeout'
    ]
    
    # Feature flags that are checked frequently
    feature_keys = [f'features.feature_{i}.enabled' for i in range(0, 50, 5)]
    
    all_keys = common_keys + feature_keys
    
    while time.time() < end_time:
        try:
            # Simulate burst access patterns
            for _ in range(operations_per_second):
                # Access different types of configuration
                key = all_keys[operations_count % len(all_keys)]
                value = config(key, f'default_value_{operations_count}')
                operations_count += 1
                
                # Small delay to simulate processing
                time.sleep(0.001)
            
            # Sleep to maintain target operations per second
            time.sleep(max(0, 1.0 - (operations_per_second * 0.001)))
            
        except Exception as e:
            errors.append(str(e))
    
    return operations_count, errors


def concurrent_access_test(watcher_class, config_files, env_vars, num_threads=5, duration=10):
    """Test concurrent access performance."""
    
    watcher = watcher_class(
        config_files=config_files,
        env_variables=env_vars,
        poll_interval=1.0,
        enable_filesystem_watching=False
    )
    
    results = []
    errors = []
    
    def worker_thread(thread_id):
        try:
            operations, thread_errors = simulate_realistic_usage(
                watcher, duration=duration, operations_per_second=50
            )
            results.append(operations)
            errors.extend(thread_errors)
        except Exception as e:
            errors.append(f"Thread {thread_id}: {str(e)}")
    
    start_time = time.time()
    
    try:
        with watcher:
            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=worker_thread, args=(i,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
        
        execution_time = time.time() - start_time
        total_operations = sum(results)
        
        return {
            'execution_time': execution_time,
            'total_operations': total_operations,
            'operations_per_second': total_operations / execution_time if execution_time > 0 else 0,
            'error_count': len(errors),
            'thread_count': num_threads
        }
        
    except Exception as e:
        return {
            'execution_time': time.time() - start_time,
            'total_operations': 0,
            'operations_per_second': 0,
            'error_count': len(errors) + 1,
            'thread_count': num_threads,
            'fatal_error': str(e)
        }


def hot_reload_stress_test(watcher_class, config_files, env_vars, num_changes=20):
    """Test hot-reload performance under stress."""
    
    if hasattr(watcher_class, 'ConfigWatcherOptimized'):
        watcher = watcher_class(
            config_files=config_files,
            env_variables=env_vars,
            poll_interval=0.5,
            enable_filesystem_watching=False,
            enable_performance_monitoring=True
        )
    else:
        watcher = watcher_class(
            config_files=config_files,
            env_variables=env_vars,
            poll_interval=0.5,
            enable_filesystem_watching=False
        )
    
    reload_count = [0]
    reload_times = []
    
    def reload_callback(changes):
        reload_count[0] += 1
        reload_times.append(time.time())
    
    watcher.add_callback(reload_callback)
    
    start_time = time.time()
    
    try:
        with watcher:
            config = watcher.get_config()
            
            # Generate rapid configuration changes
            for i in range(num_changes):
                # Alternate between file changes and env var changes
                if i % 2 == 0:
                    # Modify JSON file
                    new_config = {"modified_at": time.time(), "change_number": i}
                    with open(config_files[0], 'w') as f:
                        json.dump(new_config, f)
                else:
                    # Modify environment variable
                    var_name = env_vars[i % len(env_vars)]
                    os.environ[var_name] = f"modified_value_{i}_{time.time()}"
                
                # Small delay between changes
                time.sleep(0.1)
            
            # Wait for all changes to be processed
            time.sleep(2.0)
            
        execution_time = time.time() - start_time
        
        # Calculate reload latency
        if len(reload_times) > 1:
            latencies = [reload_times[i] - reload_times[i-1] for i in range(1, len(reload_times))]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            max_latency = max(latencies) if latencies else 0
        else:
            avg_latency = 0
            max_latency = 0
        
        result = {
            'execution_time': execution_time,
            'changes_generated': num_changes,
            'reloads_detected': reload_count[0],
            'detection_rate': reload_count[0] / num_changes if num_changes > 0 else 0,
            'avg_reload_latency': avg_latency,
            'max_reload_latency': max_latency
        }
        
        # Add optimization stats if available
        if hasattr(watcher, 'get_performance_stats'):
            stats = watcher.get_performance_stats()
            result['cache_stats'] = stats.get('configwatcher_stats', {})
        
        return result
        
    except Exception as e:
        return {
            'execution_time': time.time() - start_time,
            'changes_generated': num_changes,
            'reloads_detected': reload_count[0],
            'detection_rate': 0,
            'error': str(e)
        }


def run_performance_demo():
    """Run comprehensive performance demonstration."""
    
    print("🔬 ConfigWatcher Performance Demo")
    print("=" * 50)
    print()
    
    # Create realistic test configurations
    print("📁 Creating realistic test configurations...")
    config_files = create_realistic_configs()
    
    # Set up environment variables
    env_vars = ['NODE_ENV', 'LOG_LEVEL', 'DATABASE_URL', 'REDIS_URL', 'JWT_SECRET']
    for i in range(20):
        env_var = f'FEATURE_{i}_ENABLED'
        os.environ[env_var] = 'true' if i % 2 == 0 else 'false'
        env_vars.append(env_var)
    
    try:
        print(f"📊 Configuration files: {len(config_files)}")
        print(f"🔧 Environment variables: {len(env_vars)}")
        print()
        
        # Test 1: Concurrent Access Performance
        print("🧪 Test 1: Concurrent Access Performance")
        print("-" * 40)
        
        print("Testing Original ConfigWatcher...")
        original_result = concurrent_access_test(
            OriginalConfigWatcher, config_files, env_vars, 
            num_threads=5, duration=5
        )
        
        print("Testing Optimized ConfigWatcher...")
        optimized_result = concurrent_access_test(
            ConfigWatcherOptimized, config_files, env_vars,
            num_threads=5, duration=5
        )
        
        print()
        print("📈 Concurrent Access Results:")
        print(f"Original    - Operations/sec: {original_result['operations_per_second']:.1f}, Errors: {original_result['error_count']}")
        print(f"Optimized   - Operations/sec: {optimized_result['operations_per_second']:.1f}, Errors: {optimized_result['error_count']}")
        
        if original_result['operations_per_second'] > 0:
            improvement = ((optimized_result['operations_per_second'] - original_result['operations_per_second']) 
                          / original_result['operations_per_second'] * 100)
            print(f"Improvement - {improvement:+.1f}% operations per second")
        
        print()
        
        # Test 2: Hot-Reload Stress Test
        print("🧪 Test 2: Hot-Reload Stress Test")
        print("-" * 35)
        
        print("Testing Original ConfigWatcher...")
        original_reload = hot_reload_stress_test(
            OriginalConfigWatcher, config_files, env_vars, num_changes=10
        )
        
        print("Testing Optimized ConfigWatcher...")
        optimized_reload = hot_reload_stress_test(
            ConfigWatcherOptimized, config_files, env_vars, num_changes=10
        )
        
        print()
        print("📈 Hot-Reload Results:")
        print(f"Original    - Detection rate: {original_reload['detection_rate']:.1%}, Avg latency: {original_reload.get('avg_reload_latency', 0):.3f}s")
        print(f"Optimized   - Detection rate: {optimized_reload['detection_rate']:.1%}, Avg latency: {optimized_reload.get('avg_reload_latency', 0):.3f}s")
        
        if 'cache_stats' in optimized_reload:
            cache_stats = optimized_reload['cache_stats']
            cache_hits = cache_stats.get('cache_hits', 0)
            cache_misses = cache_stats.get('cache_misses', 0)
            if cache_hits + cache_misses > 0:
                hit_rate = cache_hits / (cache_hits + cache_misses) * 100
                print(f"Cache Performance - Hit rate: {hit_rate:.1f}% ({cache_hits}/{cache_hits + cache_misses})")
        
        print()
        
        # Summary
        print("🎯 Performance Summary")
        print("-" * 22)
        
        ops_improvement = ((optimized_result['operations_per_second'] - original_result['operations_per_second']) 
                          / original_result['operations_per_second'] * 100) if original_result['operations_per_second'] > 0 else 0
        
        detection_improvement = ((optimized_reload['detection_rate'] - original_reload['detection_rate']) 
                               / original_reload['detection_rate'] * 100) if original_reload['detection_rate'] > 0 else 0
        
        print(f"✅ Concurrent operations improvement: {ops_improvement:+.1f}%")
        print(f"✅ Hot-reload detection improvement: {detection_improvement:+.1f}%")
        print(f"✅ Error reduction: {original_result['error_count'] + original_reload.get('error_count', 0)} → {optimized_result['error_count'] + optimized_reload.get('error_count', 0)}")
        print()
        print("💡 Recommendations:")
        print("   • Use ConfigWatcherOptimized for production workloads")
        print("   • Enable performance monitoring for production insights")
        print("   • Adjust poll_interval based on your change frequency")
        print("   • Monitor cache hit rates and adjust cache_size as needed")
        
    except Exception as e:
        print(f"❌ Performance demo failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        for config_file in config_files:
            try:
                os.unlink(config_file)
            except FileNotFoundError:
                pass
        
        # Clean up environment variables
        for i in range(20):
            env_var = f'FEATURE_{i}_ENABLED'
            if env_var in os.environ:
                del os.environ[env_var]
    
    print("✅ Performance demo complete!")


if __name__ == '__main__':
    run_performance_demo()
