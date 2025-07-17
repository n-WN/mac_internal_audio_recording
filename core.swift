import Foundation
import ScreenCaptureKit
import AVFoundation

// Global variables for signal handling
var shouldStop = false
var currentStream: SCStream?
var currentWriter: AVAssetWriter?
var currentAudioInput: AVAssetWriterInput?

/// Handle SIGINT (Ctrl+C) gracefully
func setupSignalHandler() {
    signal(SIGINT) { _ in
        print("\nReceived interrupt signal, stopping recording...")
        shouldStop = true
        
        // Stop the stream and finalize the writer
        Task {
            if let stream = currentStream {
                try? await stream.stopCapture()
            }
            if let input = currentAudioInput {
                input.markAsFinished()
            }
            if let writer = currentWriter {
                await writer.finishWriting()
            }
        }
    }
}

/// Records system audio using ScreenCaptureKit
/// - Parameters:
///   - outputPath: Path for the output audio file
///   - duration: Recording duration in seconds
func recordAudio() async {
    // Setup signal handler
    setupSignalHandler()
    
    do {
        let outputPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "audio.wav"
        let duration = CommandLine.arguments.count > 2 ? Double(CommandLine.arguments[2]) ?? 10.0 : 10.0
        
        
        
        // Get screen content for audio capture
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else { 
            print("No display found to capture.")
            return 
        }
        
        // Configure stream for audio capture
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.sampleRate = 48000
        config.channelCount = 2
        config.width = Int(display.width) 
        config.height = Int(display.height)
        
        // Create content filter and stream
        let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
        let stream = SCStream(filter: filter, configuration: config, delegate: nil)
        currentStream = stream
        
        // Set up audio writer
        let url = URL(fileURLWithPath: outputPath)
        let writer = try AVAssetWriter(outputURL: url, fileType: .wav)
        currentWriter = writer
        
        let audioSettings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 48000,
            AVNumberOfChannelsKey: 2,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsNonInterleaved: false,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false
        ]
        
        let audioInput = AVAssetWriterInput(mediaType: .audio, outputSettings: audioSettings)
        audioInput.expectsMediaDataInRealTime = true
        writer.add(audioInput)
        currentAudioInput = audioInput
        
        // Start writing session
        writer.startWriting()
        writer.startSession(atSourceTime: .zero)
        
        // Audio output handler
        class AudioHandler: NSObject, SCStreamOutput {
            let input: AVAssetWriterInput
            
            init(input: AVAssetWriterInput) {
                self.input = input
            }
            
            func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
                guard type == .audio else { return }
                if input.isReadyForMoreMediaData {
                    input.append(sampleBuffer)
                }
            }
        }
        
        let handler = AudioHandler(input: audioInput)
        try stream.addStreamOutput(handler, type: .audio, sampleHandlerQueue: .main)
        
        // Start recording
        try await stream.startCapture()
        
        // Wait for specified duration or until interrupted
        let startTime = Date()
        while !shouldStop && Date().timeIntervalSince(startTime) < duration {
            try await Task.sleep(nanoseconds: 100_000_000) // Sleep for 0.1 seconds
        }
        
        // Stop recording and finalize
        if !shouldStop {
            try await stream.stopCapture()
            audioInput.markAsFinished()
            await writer.finishWriting()
        }
        
        print("Recording complete. Audio saved to \(outputPath)")
        
    } catch {
        print("Error occurred: \(error)")
        // Clean up on error
        if let input = currentAudioInput {
            input.markAsFinished()
        }
        if let writer = currentWriter {
            await writer.finishWriting()
        }
    }
}

await recordAudio()