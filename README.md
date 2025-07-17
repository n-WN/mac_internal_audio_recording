# macOS Internal Audio Recording

A simple command-line tool for recording internal audio, microphone input, or both simultaneously on macOS using ScreenCaptureKit.

## Features

- **Multiple recording modes**:
  - Internal audio only (system sounds)
  - Microphone only
  - Both internal audio and microphone simultaneously
- **Flexible duration**: Continuous recording with Ctrl+C to stop, or specify duration in seconds
- **Organized output**: All recordings saved to `output/` folder with timestamped filenames
- **Internationalization**: Support for English and Chinese interfaces
- **Smart compilation**: Automatic Swift compilation with caching for faster subsequent runs

## Requirements

- macOS 12.0 or later
- Python 3.6+
- Xcode Command Line Tools (for Swift compiler)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/n-WN/mac_internal_audio_recording.git
cd mac_internal_audio_recording
```

2. Grant microphone permissions if you plan to use microphone recording:
   - Go to System Preferences → Security & Privacy → Privacy → Microphone
   - Add Terminal (or your terminal application) to the list

## Usage

Run the main script:
```bash
python my_screen_capture_kit.py
```

### Recording Options

1. **Internal audio only** - Records system sounds, music, videos, etc.
2. **Microphone only** - Records from your microphone
3. **Both** - Records internal audio and microphone simultaneously (saves as separate files)

### Recording Duration

- **Continuous recording** (default): Press Enter to start recording, press Ctrl+C to stop and save
- **Timed recording**: Enter duration in seconds (e.g., `30` for 30 seconds)

### Output Files

All recordings are saved to the `output/` folder with the following naming convention:
- System audio: `recording_YYYYMMDD_HHMMSS.wav`
- Microphone: `recording_YYYYMMDD_HHMMSS_mic.wav`

## Examples

### Continuous Recording
```bash
$ python my_screen_capture_kit.py
macOS audio recording
========================================

1. Record internal audio only
2. Record microphone only
3. Record both (internal + microphone)

Choice: 1
Press Enter for continuous recording, or enter duration in seconds: 
Recording internal audio. Press Ctrl+C to stop and save.
# Press Ctrl+C when done
Recording stopped by user.
```

### Timed Recording
```bash
Choice: 2
Press Enter for continuous recording, or enter duration in seconds: 30
Recording microphone. Press Ctrl+C to stop and save.
# Records for 30 seconds automatically
```

## File Structure

```
mac_internal_audio_recording/
├── my_screen_capture_kit.py    # Main Python script
├── core.swift                  # Swift recording implementation
├── output/                     # Output folder for recordings
│   ├── recording_20240101_120000.wav
│   └── recording_20240101_120000_mic.wav
└── README.md
```

## Technical Details

- Uses Swift's `ScreenCaptureKit` framework for internal audio capture
- Uses `AVAudioRecorder` for microphone recording
- Automatic compilation of Swift code with timestamp-based caching
- Graceful interrupt handling with proper resource cleanup
- WAV format output at 48kHz, 16-bit, stereo

## Troubleshooting

### Permission Issues
If you encounter permission errors:
1. Check microphone permissions in System Preferences
2. Ensure Terminal has necessary permissions
3. Try running with administrator privileges if needed

### Compilation Errors
If Swift compilation fails:
1. Ensure Xcode Command Line Tools are installed: `xcode-select --install`
2. Check that `swiftc` is available in your PATH
3. Verify macOS version compatibility

### No Audio Recorded
If recordings are silent:
1. Check system audio levels
2. Verify the correct audio source is selected
3. Test with different applications playing audio

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the repository for license details.

## Limitations

- macOS only (uses platform-specific APIs)
- Requires microphone permissions for microphone recording
- Internal audio recording may not work with all applications due to system restrictions