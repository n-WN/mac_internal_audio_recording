#!/usr/bin/env python3
"""
Performance testing script for macOS Internal Audio Recording

This script measures the performance of various components of the application.
"""

import time
import sys
import os
import subprocess
import psutil
from typing import Dict, Any, Callable

# Add the current directory to path so we can import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import my_screen_capture_kit as audio_kit

def measure_time(func: Callable, *args, **kwargs) -> tuple:
    """Measure execution time of a function."""
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    return result, end_time - start_time

def measure_memory_usage(func: Callable, *args, **kwargs) -> tuple:
    """Measure memory usage of a function."""
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    
    return result, end_time - start_time, mem_after - mem_before

def test_language_detection():
    """Test language detection performance."""
    print("🧪 Testing language detection...")
    
    # Test multiple calls to see if caching would help
    times = []
    for i in range(10):
        _, exec_time = measure_time(audio_kit.detect_system_language)
        times.append(exec_time)
    
    avg_time = sum(times) / len(times)
    print(f"   Average language detection time: {avg_time:.4f}s")
    print(f"   Min time: {min(times):.4f}s, Max time: {max(times):.4f}s")
    
    return avg_time

def test_message_translation():
    """Test message translation performance."""
    print("🧪 Testing message translation...")
    
    test_keys = [
        'macos_audio_recording',
        'choose_option',
        'recording_started_internal',
        'recording_started_microphone',
        'recording_started_both',
        'continuous_recording',
        'compiling_in_progress',
        'error_message'
    ]
    
    times = []
    for key in test_keys:
        _, exec_time = measure_time(audio_kit.get_message, key)
        times.append(exec_time)
    
    avg_time = sum(times) / len(times)
    print(f"   Average message translation time: {avg_time:.4f}s")
    print(f"   Tested {len(test_keys)} keys")
    
    return avg_time

def test_file_operations():
    """Test file operations performance."""
    print("🧪 Testing file operations...")
    
    # Test Swift source verification
    _, swift_verify_time = measure_time(audio_kit.verify_swift_source)
    print(f"   Swift source verification: {swift_verify_time:.4f}s")
    
    # Test output folder creation
    _, folder_time = measure_time(audio_kit.ensure_output_folder)
    print(f"   Output folder creation: {folder_time:.4f}s")
    
    # Test filename generation
    _, filename_time = measure_time(audio_kit.generate_output_filename)
    print(f"   Filename generation: {filename_time:.4f}s")
    
    return swift_verify_time + folder_time + filename_time

def test_compilation_performance():
    """Test Swift compilation performance."""
    print("🧪 Testing Swift compilation...")
    
    # Check if executable exists
    if os.path.exists('recorder'):
        print("   Executable exists, testing smart compilation...")
        _, compile_time = measure_time(audio_kit.ensure_executable)
        print(f"   Smart compilation check: {compile_time:.4f}s")
    else:
        print("   No executable found, testing full compilation...")
        _, compile_time = measure_time(audio_kit.ensure_executable)
        print(f"   Full compilation time: {compile_time:.4f}s")
    
    return compile_time

def test_startup_performance():
    """Test overall startup performance."""
    print("🧪 Testing startup performance...")
    
    start_time = time.perf_counter()
    
    # Simulate startup sequence
    lang = audio_kit.detect_system_language()
    title = audio_kit.get_message('macos_audio_recording')
    options = audio_kit.get_message('choose_option')
    audio_kit.verify_swift_source()
    filename = audio_kit.generate_output_filename()
    
    end_time = time.perf_counter()
    total_time = end_time - start_time
    
    print(f"   Total startup time: {total_time:.4f}s")
    return total_time

def test_memory_usage():
    """Test memory usage."""
    print("🧪 Testing memory usage...")
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Load module and run basic operations
    _, _, mem_change = measure_memory_usage(test_startup_performance)
    
    current_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    print(f"   Initial memory: {initial_memory:.2f} MB")
    print(f"   Current memory: {current_memory:.2f} MB")
    print(f"   Memory change: {mem_change:.2f} MB")
    
    return current_memory - initial_memory

def test_cpu_usage():
    """Test CPU usage during various operations."""
    print("🧪 Testing CPU usage...")
    
    process = psutil.Process()
    
    # Test CPU during language detection
    time.sleep(0.1)  # Let CPU settle
    
    start_time = time.time()
    for _ in range(50):  # Run multiple times to get measurable CPU usage
        audio_kit.detect_system_language()
    end_time = time.time()
    
    cpu_lang = process.cpu_percent()
    print(f"   Language detection CPU usage: {cpu_lang:.1f}%")
    print(f"   50 language detections took: {(end_time - start_time):.4f}s")
    
    # Test CPU during message translation
    time.sleep(0.1)
    
    start_time = time.time()
    for _ in range(100):  # Run multiple times
        audio_kit.get_message('macos_audio_recording')
        audio_kit.get_message('choose_option')
    end_time = time.time()
    
    cpu_msg = process.cpu_percent()
    print(f"   Message translation CPU usage: {cpu_msg:.1f}%")
    print(f"   200 message translations took: {(end_time - start_time):.4f}s")
    
    # Test CPU during compilation
    cpu_compile = 0
    if not os.path.exists('recorder'):
        print("   Testing CPU during compilation...")
        time.sleep(0.1)
        
        start_time = time.time()
        audio_kit.ensure_executable()
        end_time = time.time()
        
        cpu_compile = process.cpu_percent()
        print(f"   Compilation CPU usage: {cpu_compile:.1f}%")
        print(f"   Compilation took: {(end_time - start_time):.4f}s")
    else:
        print("   Executable exists, skipping compilation CPU test")
    
    # Get overall CPU usage
    cpu_percent = process.cpu_percent(interval=1)
    print(f"   Overall process CPU usage: {cpu_percent:.1f}%")
    
    return cpu_percent

def run_performance_tests():
    """Run all performance tests."""
    print("🚀 macOS Internal Audio Recording - Performance Tests")
    print("=" * 60)
    
    results = {}
    
    # Individual tests
    results['language_detection'] = test_language_detection()
    print()
    
    results['message_translation'] = test_message_translation()
    print()
    
    results['file_operations'] = test_file_operations()
    print()
    
    results['compilation'] = test_compilation_performance()
    print()
    
    results['startup'] = test_startup_performance()
    print()
    
    results['memory_usage'] = test_memory_usage()
    print()
    
    results['cpu_usage'] = test_cpu_usage()
    print()
    
    # Summary
    print("📊 Performance Summary")
    print("=" * 30)
    for test_name, result in results.items():
        if test_name == 'memory_usage':
            print(f"{test_name:20}: {result:.2f} MB")
        elif test_name == 'cpu_usage':
            print(f"{test_name:20}: {result:.1f}%")
        else:
            print(f"{test_name:20}: {result:.4f}s")
    
    # Performance assessment
    print("\n🎯 Performance Assessment")
    print("=" * 30)
    
    if results['startup'] < 0.1:
        print("✅ Startup performance: Excellent (< 0.1s)")
    elif results['startup'] < 0.5:
        print("✅ Startup performance: Good (< 0.5s)")
    else:
        print("⚠️  Startup performance: Could be improved (> 0.5s)")
    
    if results['memory_usage'] < 10:
        print("✅ Memory usage: Excellent (< 10 MB)")
    elif results['memory_usage'] < 50:
        print("✅ Memory usage: Good (< 50 MB)")
    else:
        print("⚠️  Memory usage: High (> 50 MB)")
    
    if results['compilation'] < 2.0:
        print("✅ Compilation: Fast (< 2s)")
    elif results['compilation'] < 5.0:
        print("✅ Compilation: Acceptable (< 5s)")
    else:
        print("⚠️  Compilation: Slow (> 5s)")
    
    # Recommendations
    print("\n💡 Recommendations")
    print("=" * 20)
    
    if results['language_detection'] > 0.01:
        print("• Consider caching language detection result")
    
    if results['compilation'] > 3.0:
        print("• Swift compilation is the main bottleneck")
        print("• Consider pre-compiling for distribution")
    
    if results['memory_usage'] > 20:
        print("• Consider optimizing memory usage")
    
    if results['cpu_usage'] > 50:
        print("• High CPU usage detected")
        print("• Consider optimizing computational operations")
    elif results['cpu_usage'] < 10:
        print("• CPU usage is very low - excellent efficiency")
    
    if all(v < 0.1 for k, v in results.items() if k not in ['memory_usage', 'compilation', 'cpu_usage']):
        print("• Overall performance is excellent!")

if __name__ == "__main__":
    run_performance_tests()