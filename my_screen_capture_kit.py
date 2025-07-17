#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS Internal Audio Recording

A simple command-line tool for recording internal audio, microphone input, 
or both simultaneously on macOS using ScreenCaptureKit.

Copyright (c) 2025 n-WN
Repository: https://github.com/n-WN/mac_internal_audio_recording

This program is free software: you can redistribute it and/or modify
it under the terms of the MIT License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
"""

import subprocess
import os
from datetime import datetime
import locale
from typing import Dict, Any

# --- Configuration ---
DEFAULT_DURATION = 10
SWIFT_COMPILER = 'swiftc'
RECORDER_EXECUTABLE = 'recorder'
SWIFT_SOURCE_FILE = 'core.swift'
OUTPUT_FOLDER = 'output'

# --- Internationalization (i18n) ---
MESSAGES: Dict[str, Dict[str, str]] = {
    'en': {
        'swift_source_written': "Swift source written to {output_path}",
        'compiling_swift_code': "Compiling Swift code: {command}",
        'swift_compilation_successful': "Swift compilation successful.",
        'compiler_output_stdout': "Compiler Output (stdout):\\n",

        'compiler_output_stderr': "Compiler Output (stderr):\n",
        'swift_compilation_failed': "Swift compilation failed: {error}",
        'compiler_error_stdout': "Compiler Error (stdout):\n",
        'compiler_error_stderr': "Compiler Error (stderr):\n",
        'error_during_swift_compilation': "An error occurred during Swift compilation: {error}",
        'cleaned_up': "Cleaned up {file}",
        'enter_duration': "Enter recording duration in seconds (e.g., 60 for 1 minute): ",
        'duration_positive': "Duration must be a positive number.",
        'invalid_duration': "Invalid duration. Please enter a number.",
        'failed_to_compile_swift': "Failed to compile Swift code. Exiting.",
        'starting_recording': "Starting recording for {duration} seconds. Output will be saved to: {output_filepath}",
        'recording_complete': "Recording complete. Audio saved to {output_filepath}",
        'recording_failed': "Recording failed: {error}",
        'swift_executable_error_stdout': "Swift Executable Error (stdout):\n",
        'swift_executable_error_stderr': "Swift Executable Error (stderr):\n",
        'unexpected_recording_error': "An unexpected error occurred during recording: {error}",
        'macos_audio_recording': "macOS audio recording",
        'choose_option': "\n1. Record internal audio only\n2. Record microphone only\n3. Record both (internal + microphone)\n\nChoice: ",
        'enter_duration_prompt': "Recording duration in seconds (default: continuous until Ctrl+C): ",
        'continuous_recording': "Press Enter for continuous recording, or enter duration in seconds: ",
        'recording_started': "Recording started. Press Ctrl+C to stop and save.",
        'recording_stopped': "Recording stopped by user.",
        'compiling_in_progress': "Compiling in progress...",
        'compilation_failed': "Compilation failed:\n{error}",
        'running_in_progress': "Running in progress...",
        'error_message': "Error: {error}",
        'user_interrupted': "User interrupted",
        'goodbye': "Goodbye!",
        'recording_started_internal': "Recording internal audio. Press Ctrl+C to stop and save.",
        'recording_started_microphone': "Recording microphone. Press Ctrl+C to stop and save.",
        'recording_started_both': "Recording both internal audio and microphone. Press Ctrl+C to stop and save.",
        'output_folder_created': "Created output folder: {folder}",
        # Swift template messages
        'swift_no_display': "No display found to capture.",
        'swift_cannot_add_writer_input': "Cannot add asset writer input.",
        'swift_recording_started': "Recording started. Press Ctrl+C to stop early or wait for duration.",
        'swift_error_stopping': "Error stopping recording: {error.localizedDescription}",
        'swift_recording_finished': "Recording finished after {Int(self?.recordingDuration ?? 0)} seconds.",
        'swift_stream_stopped_error': "Stream stopped with error: {error.localizedDescription}",
        'swift_usage': "Usage: {CommandLine.arguments[0]} <output_path> <duration_seconds>",
        'swift_invalid_duration': "Invalid duration: {durationString}",
        'swift_failed_to_start': "Failed to start recording: {error.localizedDescription}"
    },
    'zh_CN': {
        'swift_source_written': "Swift 源代码已写入 {output_path}",
        'compiling_swift_code': "正在编译 Swift 代码: {command}",
        'swift_compilation_successful': "Swift 编译成功。",
        'compiler_output_stdout': "编译器输出 (stdout):\n",
        'compiler_output_stderr': "编译器输出 (stderr):\n",
        'swift_compilation_failed': "Swift 编译失败: {error}",
        'compiler_error_stdout': "编译器错误 (stdout):\n",
        'compiler_error_stderr': "编译器错误 (stderr):\n",
        'error_during_swift_compilation': "Swift 编译过程中发生错误: {error}",
        'cleaned_up': "已清理 {file}",
        'enter_duration': "请输入录音时长 (秒, 例如 60 代表 1 分钟): ",
        'duration_positive': "时长必须是正数。",
        'invalid_duration': "时长无效。请输入一个数字。",
        'failed_to_compile_swift': "Swift 代码编译失败。正在退出。",
        'starting_recording': "开始录音，时长 {duration} 秒。输出将保存到: {output_filepath}",
        'recording_complete': "录音完成。音频已保存到 {output_filepath}",
        'recording_failed': "录音失败: {error}",
        'swift_executable_error_stdout': "Swift 可执行文件错误 (stdout):\n",
        'swift_executable_error_stderr': "Swift 可执行文件错误 (stderr):\n",
        'unexpected_recording_error': "录音过程中发生意外错误: {error}",
        # Swift template messages
        'swift_no_display': "未找到可捕获的显示器。",
        'swift_cannot_add_writer_input': "无法添加资产写入器输入。",
        'swift_recording_started': "录音已开始。按 Ctrl+C 提前停止或等待指定时长。",
        'swift_error_stopping': r"停止录音时出错: {error.localizedDescription}",
        'swift_recording_finished': r"录音在 {Int(self?.recordingDuration ?? 0)} 秒后完成。",
        'swift_stream_stopped_error': r"流因错误停止: {error.localizedDescription}",
        'swift_usage': r"用法: {CommandLine.arguments[0]} <输出路径> <时长秒>",
        'swift_invalid_duration': r"无效时长: {durationString}",
        'swift_failed_to_start': r"启动录音失败: {error.localizedDescription}",
        'swift_recording_complete_with_path': r"完成: {outputPath}",
        'swift_error_occurred': r"错误: {error}",
        'macos_audio_recording': "macOS 音频录制",
        'choose_option': "\n1. 仅录制内部音频\n2. 仅录制麦克风\n3. 同时录制两者 (内部+麦克风)\n\n选择: ",
        'enter_duration_prompt': "录制秒数 (默认: 持续录制直到 Ctrl+C): ",
        'continuous_recording': "按回车键持续录制，或输入录制秒数: ",
        'recording_started': "录制已开始。按 Ctrl+C 停止并保存。",
        'recording_stopped': "用户停止录制。",
        'compiling_in_progress': "编译中...",
        'compilation_failed': "编译失败:\n{error}",
        'running_in_progress': "运行中...",
        'error_message': "错误: {error}",
        'user_interrupted': "用户中断操作",
        'goodbye': "再见！",
        'recording_started_internal': "正在录制内部音频。按 Ctrl+C 停止并保存。",
        'recording_started_microphone': "正在录制麦克风。按 Ctrl+C 停止并保存。",
        'recording_started_both': "正在同时录制内部音频和麦克风。按 Ctrl+C 停止并保存。",
        'output_folder_created': "已创建输出文件夹: {folder}"
    }
}

def get_message(key: str, **kwargs: Any) -> str:
    """Get a translated message based on the current locale.
    
    Args:
        key: The message key to look up
        **kwargs: Format parameters for the message
        
    Returns:
        Formatted message string in the appropriate language
    """
    try:
        lang, _ = locale.getlocale()
        if lang is None:
            locale.setlocale(locale.LC_ALL, '')
            lang, _ = locale.getlocale()
    except Exception:
        lang = 'en'

    lang_code = lang.split('_')[0] if lang else 'en'
    messages = MESSAGES.get(lang_code, MESSAGES['en'])
    
    message = messages.get(key, MESSAGES['en'].get(key, f"MISSING_TRANSLATION_{key}"))
    return message.format(**kwargs)

def verify_swift_source() -> str:
    """Verify Swift source file exists.
    
    Returns:
        Path to the Swift source file
        
    Raises:
        FileNotFoundError: If core.swift is not found
    """
    if not os.path.exists(SWIFT_SOURCE_FILE):
        raise FileNotFoundError(f"{SWIFT_SOURCE_FILE} not found")
    
    return SWIFT_SOURCE_FILE


def get_duration_input() -> str:
    """Get recording duration from user input with validation.
    
    Returns:
        Valid duration string, or 'continuous' for continuous recording
        
    Raises:
        KeyboardInterrupt: When user interrupts input
    """
    try:
        duration_input = input(get_message('continuous_recording')).strip()
        if not duration_input:
            return 'continuous'
        # Validate that it's a positive number
        try:
            duration = float(duration_input)
            if duration <= 0:
                print(get_message('duration_positive'))
                return 'continuous'
            return duration_input
        except ValueError:
            print(get_message('invalid_duration'))
            return 'continuous'
    except KeyboardInterrupt:
        raise


def ensure_output_folder() -> None:
    """Ensure output folder exists."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(get_message('output_folder_created', folder=OUTPUT_FOLDER))


def generate_output_filename() -> str:
    """Generate timestamped output filename with full path.
    
    Returns:
        Full path to output file in output folder
    """
    ensure_output_folder()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"recording_{timestamp}.wav"
    return os.path.join(OUTPUT_FOLDER, filename)


def ensure_executable() -> bool:
    """Ensure Swift executable exists, compile if necessary.
        
    Returns:
        True if executable is available, False otherwise
    """
    # Check if executable already exists and is newer than source
    if os.path.exists(RECORDER_EXECUTABLE):
        try:
            exe_time = os.path.getmtime(RECORDER_EXECUTABLE)
            src_time = os.path.getmtime(SWIFT_SOURCE_FILE)
            
            # If executable is newer than source, no need to recompile
            if exe_time > src_time:
                return True
        except OSError:
            pass  # If we can't check times, just recompile
    
    # Compile Swift code
    print(get_message('compiling_in_progress'))
    result = subprocess.run(
        [SWIFT_COMPILER, SWIFT_SOURCE_FILE, '-o', RECORDER_EXECUTABLE],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(get_message('compilation_failed', error=result.stderr))
        return False
    
    return True


def run_recording(output_file: str, duration: str, recording_type: str) -> None:
    """Run the audio recording process.
    
    Args:
        output_file: Path for output audio file
        duration: Recording duration in seconds or 'continuous'
        recording_type: Type of recording ('internal', 'microphone', 'both')
    """
    # Show appropriate message based on recording type
    if recording_type == 'internal':
        message_key = 'recording_started_internal'
    elif recording_type == 'microphone':
        message_key = 'recording_started_microphone'
    elif recording_type == 'both':
        message_key = 'recording_started_both'
    else:
        message_key = 'recording_started'
    
    if duration == 'continuous':
        print(get_message(message_key))
        try:
            # Run with a very long duration, user will interrupt with Ctrl+C
            subprocess.run(
                [f'./{RECORDER_EXECUTABLE}', output_file, '86400', recording_type],  # 24 hours max
                capture_output=False,  # Allow real-time output
                text=True
            )
        except KeyboardInterrupt:
            print(f"\n{get_message('recording_stopped')}")
            # The Swift program should handle SIGINT gracefully
            return
    else:
        print(get_message('running_in_progress'))
        try:
            subprocess.run(
                [f'./{RECORDER_EXECUTABLE}', output_file, duration, recording_type],
                capture_output=False,
                text=True
            )
        except KeyboardInterrupt:
            print(f"\n{get_message('recording_stopped')}")
            return


def cleanup_files() -> None:
    """Clean up generated executable if needed.
    
    Note: By default, we keep the executable to avoid recompilation.
    Only remove it if you specifically want to force recompilation.
    """
    # Uncomment the following lines if you want to clean up the executable
    # try:
    #     if os.path.exists(RECORDER_EXECUTABLE):
    #         os.remove(RECORDER_EXECUTABLE)
    # except OSError:
    #     pass  # Ignore cleanup errors
    pass


def handle_user_input() -> str:
    """Handle user input with graceful interrupt handling.
    
    Returns:
        User's choice
        
    Raises:
        KeyboardInterrupt: When user interrupts input
    """
    try:
        return input(get_message('choose_option'))
    except KeyboardInterrupt:
        raise


def main() -> None:
    """Main application entry point."""
    try:
        print(get_message('macos_audio_recording'))
        print("=" * 40)
        
        choice = handle_user_input()
        
        if choice in ["1", "2", "3"]:
            try:
                duration = get_duration_input()
                output_file = generate_output_filename()
                
                verify_swift_source()
                
                if not ensure_executable():
                    return
                
                # Map choice to recording type
                recording_types = {
                    "1": "internal",
                    "2": "microphone", 
                    "3": "both"
                }
                recording_type = recording_types[choice]
                
                run_recording(output_file, duration, recording_type)
                
            except FileNotFoundError as e:
                print(get_message('error_message', error=str(e)))
            finally:
                cleanup_files()
                
    except KeyboardInterrupt:
        print(f"\n{get_message('user_interrupted')}")
        print(get_message('goodbye'))
        

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Handle any remaining KeyboardInterrupt at the top level
        pass