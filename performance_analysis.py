#!/usr/bin/env python3
"""
ConfigWatcher Performance Analysis and Optimization Guide
Comprehensive analysis of performance bottlenecks and solutions.
"""

import os
import sys
import time
import json
import tempfile
from typing import Dict, List, Any
import logging

from config_watcher import ConfigWatcher as OriginalConfigWatcher  
from config_watcher_optimized import ConfigWatcherOptimized

logging.basicConfig(level=logging.WARNING)  # Reduce log noise
logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes and demonstrates ConfigWatcher performance optimizations."""
    
    def __init__(self):
        self.results = {}
        self.temp_files = []
    
    def cleanup(self):
        """Clean up temporary files."""
        for file_path in self.temp_files:
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass
    
    def create_test_scenario(self, scenario_type: str) -> Dict[str, Any]:
        """Create test scenarios that highlight different performance aspects."""
        
        scenarios = {
            'small_config': {
                'files': 1,
                'keys_per_file': 10,
                'env_vars': 5,
                'description': 'Small configuration (typical microservice)'
            },
            'medium_config': {
                'files': 3,
                'keys_per_file': 100,
                'env_vars': 15,
                'description': 'Medium configuration (typical web application)'
            },
            'large_config': {
                'files': 5,
                'keys_per_file': 500,
                'env_vars': 50,
                'description': 'Large configuration (complex enterprise app)'
            },
            'multi_format': {
                'files': 10,
                'keys_per_file': 50,
                'env_vars': 25,
                'description': 'Multiple formats (JSON, YAML, ENV, INI)'
            }
        }
        
        if scenario_type not in scenarios:
            scenario_type = 'medium_config'
        
        scenario = scenarios[scenario_type]
        config_files = []
        
        for i in range(scenario['files']):
            # Create configuration data
            config_data = {
                f'section_{j}': {
                    f'key_{k}': f'value_{i}_{j}_{k}'
                    for k in range(scenario['keys_per_file'] // 10)
                } for j in range(10)
            }
            
            # Choose format based on file index
            formats = ['.json', '.yaml', '.env', '.ini']
            ext = formats[i % len(formats)]
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', suffix=ext, delete=False
            )
            
            if ext == '.json':
                json.dump(config_data, temp_file, indent=2)
            elif ext == '.yaml':
                import yaml
                yaml.dump(config_data, temp_file)
            elif ext == '.env':
                # Flatten for ENV format
                for section, keys in config_data.items():
                    for key, value in keys.items():
                        temp_file.write(f'{section.upper()}_{key.upper()}={value}\n')
            elif ext == '.ini':
                # INI format
                for section, keys in config_data.items():
                    temp_file.write(f'[{section}]\n')
                    for key, value in keys.items():
                        temp_file.write(f'{key} = {value}\n')
                    temp_file.write('\n')
            
            temp_file.close()
            config_files.append(temp_file.name)
            self.temp_files.append(temp_file.name)
        
        # Set up environment variables
        env_vars = []
        for i in range(scenario['env_vars']):
            var_name = f'TEST_VAR_{i}'
            os.environ[var_name] = f'env_value_{i}'
            env_vars.append(var_name)
        
        return {
            'config_files': config_files,
            'env_vars': env_vars,
            'description': scenario['description'],
            'expected_keys': scenario['files'] * scenario['keys_per_file'] + scenario['env_vars']
        }
    
    def measure_initialization_performance(self, scenario: Dict[str, Any]) -> Dict[str, float]:
        """Measure initialization performance for both versions."""
        
        results = {}
        
        # Test original version
        start_time = time.time()
        original_watcher = OriginalConfigWatcher(
            config_files=scenario['config_files'],
            env_variables=scenario['env_vars'],
            enable_filesystem_watching=False
        )
        config = original_watcher.get_config()
        original_time = time.time() - start_time
        results['original_init'] = original_time
        
        # Test optimized version  
        start_time = time.time()
        optimized_watcher = ConfigWatcherOptimized(
            config_files=scenario['config_files'],
            env_variables=scenario['env_vars'],
            enable_filesystem_watching=False,
            enable_performance_monitoring=True
        )
        config = optimized_watcher.get_config()
        optimized_time = time.time() - start_time
        results['optimized_init'] = optimized_time
        
        return results
    
    def measure_access_performance(self, scenario: Dict[str, Any], num_accesses: int = 1000) -> Dict[str, Any]:
        """Measure configuration access performance."""
        
        results = {}
        
        # Test original version
        original_watcher = OriginalConfigWatcher(
            config_files=scenario['config_files'],
            env_variables=scenario['env_vars'],
            enable_filesystem_watching=False
        )
        
        config = original_watcher.get_config()
        raw_config = original_watcher.get_raw_config()
        keys = list(raw_config.keys())[:min(10, len(raw_config))]  # Sample of keys
        
        start_time = time.time()
        for i in range(num_accesses):
            key = keys[i % len(keys)] if keys else f'non_existent_key_{i}'
            value = config(key, f'default_value_{i}')
        original_time = time.time() - start_time
        
        results['original_access_time'] = original_time
        results['original_ops_per_sec'] = num_accesses / original_time if original_time > 0 else 0
        
        # Test optimized version
        optimized_watcher = ConfigWatcherOptimized(
            config_files=scenario['config_files'],
            env_variables=scenario['env_vars'],
            enable_filesystem_watching=False,
            enable_performance_monitoring=True
        )
        
        config = optimized_watcher.get_config()
        raw_config = optimized_watcher.get_raw_config()
        keys = list(raw_config.keys())[:min(10, len(raw_config))]
        
        start_time = time.time()
        for i in range(num_accesses):
            key = keys[i % len(keys)] if keys else f'non_existent_key_{i}'
            value = config(key, f'default_value_{i}')
        optimized_time = time.time() - start_time
        
        results['optimized_access_time'] = optimized_time
        results['optimized_ops_per_sec'] = num_accesses / optimized_time if optimized_time > 0 else 0
        
        # Get optimization stats
        stats = optimized_watcher.get_performance_stats()
        results['cache_stats'] = stats.get('configwatcher_stats', {})
        
        return results
    
    def measure_reload_performance(self, scenario: Dict[str, Any], num_changes: int = 5) -> Dict[str, Any]:
        """Measure hot-reload performance."""
        
        results = {}
        
        # Test original version
        original_watcher = OriginalConfigWatcher(
            config_files=scenario['config_files'],
            env_variables=scenario['env_vars'],
            poll_interval=0.1,  # Fast polling for testing
            enable_filesystem_watching=False
        )
        
        reload_count = [0]
        def count_reloads(changes):
            reload_count[0] += 1
        
        original_watcher.add_callback(count_reloads)
        
        start_time = time.time()
        with original_watcher:
            for i in range(num_changes):
                # Modify first config file
                if scenario['config_files']:
                    test_data = {'reload_test': f'value_{i}', 'timestamp': time.time()}
                    with open(scenario['config_files'][0], 'w') as f:
                        json.dump(test_data, f)
                    time.sleep(0.2)  # Wait for detection
        
        original_time = time.time() - start_time
        results['original_reload_time'] = original_time
        results['original_reloads_detected'] = reload_count[0]
        
        # Test optimized version
        optimized_watcher = ConfigWatcherOptimized(
            config_files=scenario['config_files'],
            env_variables=scenario['env_vars'],
            poll_interval=0.1,
            enable_filesystem_watching=False,
            enable_performance_monitoring=True
        )
        
        reload_count = [0]
        optimized_watcher.add_callback(count_reloads)
        
        start_time = time.time()
        with optimized_watcher:
            for i in range(num_changes):
                if scenario['config_files']:
                    test_data = {'reload_test': f'optimized_value_{i}', 'timestamp': time.time()}
                    with open(scenario['config_files'][0], 'w') as f:
                        json.dump(test_data, f)
                    time.sleep(0.2)
        
        optimized_time = time.time() - start_time
        results['optimized_reload_time'] = optimized_time
        results['optimized_reloads_detected'] = reload_count[0]
        
        # Get optimization stats
        stats = optimized_watcher.get_performance_stats()
        results['optimization_stats'] = stats
        
        return results
    
    def analyze_performance_bottlenecks(self) -> Dict[str, Dict[str, Any]]:
        """Analyze performance across different scenarios."""
        
        print("🔍 Analyzing ConfigWatcher Performance Bottlenecks")
        print("=" * 55)
        print()
        
        scenarios = ['small_config', 'medium_config', 'large_config']
        all_results = {}
        
        for scenario_name in scenarios:
            print(f"📊 Testing {scenario_name.replace('_', ' ').title()}...")
            
            scenario = self.create_test_scenario(scenario_name)
            
            # Run performance tests
            init_results = self.measure_initialization_performance(scenario)
            access_results = self.measure_access_performance(scenario, 500)
            reload_results = self.measure_reload_performance(scenario, 3)
            
            all_results[scenario_name] = {
                'scenario': scenario,
                'initialization': init_results,
                'access': access_results,
                'reload': reload_results
            }
            
            # Show immediate results
            init_improvement = ((init_results['original_init'] - init_results['optimized_init']) 
                              / init_results['original_init'] * 100) if init_results['original_init'] > 0 else 0
            
            access_improvement = ((access_results['optimized_ops_per_sec'] - access_results['original_ops_per_sec']) 
                                / access_results['original_ops_per_sec'] * 100) if access_results['original_ops_per_sec'] > 0 else 0
            
            print(f"   Initialization: {init_improvement:+.1f}% improvement")
            print(f"   Access speed: {access_improvement:+.1f}% improvement")
            print(f"   Cache hit rate: {self._get_cache_hit_rate(access_results):.1f}%")
            print()
        
        return all_results
    
    def _get_cache_hit_rate(self, access_results: Dict[str, Any]) -> float:
        """Calculate cache hit rate from access results."""
        cache_stats = access_results.get('cache_stats', {})
        hits = cache_stats.get('cache_hits', 0)
        misses = cache_stats.get('cache_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0
    
    def generate_optimization_report(self, results: Dict[str, Dict[str, Any]]) -> str:
        """Generate comprehensive optimization report."""
        
        report = []
        report.append("ConfigWatcher Performance Analysis Report")
        report.append("=" * 45)
        report.append("")
        
        # Executive Summary
        report.append("📊 EXECUTIVE SUMMARY")
        report.append("-" * 20)
        report.append("")
        
        avg_init_improvement = 0
        avg_access_improvement = 0
        total_scenarios = len(results)
        
        for scenario_name, scenario_results in results.items():
            init_results = scenario_results['initialization']
            access_results = scenario_results['access']
            
            if init_results['original_init'] > 0:
                init_improvement = ((init_results['original_init'] - init_results['optimized_init']) 
                                  / init_results['original_init'] * 100)
                avg_init_improvement += init_improvement
            
            if access_results['original_ops_per_sec'] > 0:
                access_improvement = ((access_results['optimized_ops_per_sec'] - access_results['original_ops_per_sec']) 
                                    / access_results['original_ops_per_sec'] * 100)
                avg_access_improvement += access_improvement
        
        avg_init_improvement /= total_scenarios
        avg_access_improvement /= total_scenarios
        
        report.append(f"✅ Average initialization improvement: {avg_init_improvement:+.1f}%")
        report.append(f"✅ Average access performance improvement: {avg_access_improvement:+.1f}%")
        report.append("")
        
        # Detailed Results
        for scenario_name, scenario_results in results.items():
            scenario_desc = scenario_results['scenario']['description']
            report.append(f"📈 {scenario_name.upper()} - {scenario_desc}")
            report.append("-" * (len(scenario_name) + len(scenario_desc) + 5))
            report.append("")
            
            # Initialization Performance
            init_results = scenario_results['initialization']
            report.append("🚀 Initialization Performance:")
            report.append(f"   Original:  {init_results['original_init']:.4f}s")
            report.append(f"   Optimized: {init_results['optimized_init']:.4f}s")
            
            if init_results['original_init'] > 0:
                improvement = ((init_results['original_init'] - init_results['optimized_init']) 
                              / init_results['original_init'] * 100)
                report.append(f"   Improvement: {improvement:+.1f}%")
            report.append("")
            
            # Access Performance
            access_results = scenario_results['access']
            report.append("⚡ Access Performance:")
            report.append(f"   Original:  {access_results['original_ops_per_sec']:.1f} ops/sec")
            report.append(f"   Optimized: {access_results['optimized_ops_per_sec']:.1f} ops/sec")
            
            if access_results['original_ops_per_sec'] > 0:
                improvement = ((access_results['optimized_ops_per_sec'] - access_results['original_ops_per_sec']) 
                              / access_results['original_ops_per_sec'] * 100)
                report.append(f"   Improvement: {improvement:+.1f}%")
            
            # Cache Performance
            cache_hit_rate = self._get_cache_hit_rate(access_results)
            report.append(f"   Cache hit rate: {cache_hit_rate:.1f}%")
            report.append("")
            
            # Reload Performance
            reload_results = scenario_results['reload']
            report.append("🔄 Hot-Reload Performance:")
            report.append(f"   Original reloads:  {reload_results['original_reloads_detected']}")
            report.append(f"   Optimized reloads: {reload_results['optimized_reloads_detected']}")
            report.append("")
        
        # Key Optimizations
        report.append("🔧 KEY OPTIMIZATIONS IMPLEMENTED")
        report.append("-" * 35)
        report.append("")
        report.append("1. 📦 Intelligent Caching System")
        report.append("   • Configuration data caching with LRU eviction")
        report.append("   • Validation result caching to avoid re-computation")
        report.append("   • File hash caching for efficient change detection")
        report.append("")
        report.append("2. 🚀 Optimized File I/O")
        report.append("   • Memory-mapped file reading for large files")
        report.append("   • Streaming parser for large ENV/INI files")
        report.append("   • Efficient file stat checking with metadata caching")
        report.append("")
        report.append("3. ⚙️  Adaptive Performance")
        report.append("   • Adaptive polling intervals based on activity")
        report.append("   • Batched environment variable monitoring")
        report.append("   • Debounced file system events")
        report.append("")
        report.append("4. 🧵 Thread Optimization")
        report.append("   • Limited thread pool for controlled concurrency")
        report.append("   • Asynchronous callback processing")
        report.append("   • Optimized locking strategy")
        report.append("")
        
        # Recommendations
        report.append("💡 PERFORMANCE RECOMMENDATIONS")
        report.append("-" * 32)
        report.append("")
        report.append("For optimal performance:")
        report.append("")
        report.append("1. 🎯 Use ConfigWatcherOptimized for production")
        report.append("   watcher = ConfigWatcherOptimized(...)")
        report.append("")
        report.append("2. 📊 Enable performance monitoring")
        report.append("   enable_performance_monitoring=True")
        report.append("")
        report.append("3. ⏱️  Tune polling intervals based on workload")
        report.append("   • High frequency: poll_interval=0.5")
        report.append("   • Normal: poll_interval=2.0")
        report.append("   • Low frequency: poll_interval=5.0+")
        report.append("")
        report.append("4. 💾 Optimize cache sizes for your data")
        report.append("   • Small configs: max_cache_size=100")
        report.append("   • Large configs: max_cache_size=1000+")
        report.append("")
        report.append("5. 🔄 Use workload-specific optimizations")
        report.append("   watcher.optimize_for_workload('your_workload_type')")
        report.append("")
        
        return "\\n".join(report)
    
    def run_analysis(self) -> str:
        """Run complete performance analysis."""
        try:
            results = self.analyze_performance_bottlenecks()
            report = self.generate_optimization_report(results)
            return report
        finally:
            self.cleanup()


def main():
    """Main performance analysis entry point."""
    print("🔬 Starting ConfigWatcher Performance Analysis...")
    print("This will test performance across different configuration scenarios.")
    print()
    
    analyzer = PerformanceAnalyzer()
    
    try:
        report = analyzer.run_analysis()
        
        print()
        print("=" * 60)
        print("📋 PERFORMANCE ANALYSIS COMPLETE")
        print("=" * 60)
        print()
        print(report)
        
        # Save report
        with open('/tmp/inputs/performance_analysis_report.txt', 'w') as f:
            f.write(report)
        
        print()
        print("📄 Full analysis saved to: performance_analysis_report.txt")
        
    except Exception as e:
        print(f"❌ Performance analysis failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        analyzer.cleanup()


if __name__ == '__main__':
    main()
