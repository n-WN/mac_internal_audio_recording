#!/usr/bin/env python3
import subprocess
import os
from datetime import datetime
import time
import sys
import locale

# --- Internationalization (i18n) ---
# Define messages for different languages
MESSAGES = {
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
        'choose_option': "\n1. Try ScreenCaptureKit\n\nChoice: ",
        'enter_duration_prompt': "Recording duration in seconds (default 10): ",
        'compiling_in_progress': "Compiling in progress...",
        'compilation_failed': "Compilation failed:\n{error}",
        'running_in_progress': "Running in progress...",
        'error_message': "Error: {error}",
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
        'choose_option': "\n1. 尝试ScreenCaptureKit\n\n选择: ",
        'enter_duration_prompt': "录制秒数 (默认10) : ",
        'compiling_in_progress': "编译中...",
        'compilation_failed': "编译失败:\n{error}",
        'running_in_progress': "运行中...",
        'error_message': "错误: {error}"
    }
}

def get_message(key, **kwargs):
    """Get a translated message based on the current locale."""
    # Get the user's preferred locale
    try:
        lang, _ = locale.getlocale()
        if lang is None:
            locale.setlocale(locale.LC_ALL, '')
            lang, _ = locale.getlocale()
        # print(lang)
    except Exception:
        lang = 'en'

    # Use the language part (e.g., 'en', 'zh')
    lang_code = lang.split('_')[0] if lang else 'en'



    # Prioritize specific locale (e.g., 'zh_CN') then general language (e.g., 'zh')
    # messages = MESSAGES.get(lang, MESSAGES.get(lang_code, MESSAGES['en']))
    messages = MESSAGES.get(lang_code, MESSAGES['en'])
    
    message = messages.get(key, MESSAGES['en'].get(key, f"MISSING_TRANSLATION_{key}"))
    return message.format(**kwargs)

# --- Configuration ---

def create_swift_recorder():
    """创建最简单的Swift录制脚本"""
    swift_code = open('core.swift', 'r').read()
    
    with open('recorder.swift', 'w') as f:
        f.write(swift_code)
    
    return 'recorder.swift'


def main():
    print(get_message('macos_audio_recording'))
    print("="*40)
    
    choice = input(get_message('choose_option'))
    
    if choice == "1":
        duration = input(get_message('enter_duration_prompt')).strip() or "10"
        output = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        
        # 创建并编译Swift代码
        swift_file = create_swift_recorder()
        
        print(get_message('compiling_in_progress'))
        result = subprocess.run(['swiftc', swift_file, '-o', 'recorder'], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print(get_message('compilation_failed', error=result.stderr))
            os.remove(swift_file)
            return
        
        print(get_message('running_in_progress'))
        result = subprocess.run(['./recorder', output, duration], 
                              capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print(get_message('error_message', error=result.stderr))
            
        # 清理
        os.remove(swift_file)
        os.remove('recorder')
        

if __name__ == "__main__":
    main()