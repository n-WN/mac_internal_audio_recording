import Foundation
import ScreenCaptureKit
import AVFoundation

/// Records system audio using ScreenCaptureKit
/// - Parameters:
///   - outputPath: Path for the output audio file
///   - duration: Recording duration in seconds
func recordAudio() async {
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
        
        // Set up audio writer
        let url = URL(fileURLWithPath: outputPath)
        let writer = try AVAssetWriter(outputURL: url, fileType: .wav)
        
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
        
        // Wait for specified duration
        try await Task.sleep(nanoseconds: UInt64(duration * 1_000_000_000))
        
        // Stop recording and finalize
        try await stream.stopCapture()
        audioInput.markAsFinished()
        await writer.finishWriting()
        
        print("Recording complete. Audio saved to \(outputPath)")
        
    } catch {
        print("Error occurred: \(error)")
    }
}

await recordAudio()