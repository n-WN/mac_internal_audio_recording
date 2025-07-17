//
//  core.swift
//  macOS Internal Audio Recording
//
//  A Swift implementation for recording system audio and microphone input
//  using ScreenCaptureKit and AVFoundation frameworks.
//
//  Copyright (c) 2025 n-WN
//  Repository: https://github.com/n-WN/mac_internal_audio_recording
//
//  This program is free software: you can redistribute it and/or modify
//  it under the terms of the MIT License.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//

import Foundation
import ScreenCaptureKit
import AVFoundation

// Global variables for signal handling
var shouldStop = false

/// Handle SIGINT (Ctrl+C) gracefully
func setupSignalHandler() {
    signal(SIGINT) { _ in
        print("\nReceived interrupt signal, stopping recording...")
        shouldStop = true
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
        let recordingType = CommandLine.arguments.count > 3 ? CommandLine.arguments[3] : "internal"
        
        
        
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
        
        // Set audio capture based on recording type
        if recordingType == "microphone" {
            config.capturesAudio = false  // Don't capture system audio for mic-only
        } else {
            config.capturesAudio = true   // Capture system audio for internal or both
        }
        
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
        
        // Set up microphone recording if needed
        var micRecorder: AVAudioRecorder?
        if recordingType == "microphone" || recordingType == "both" {
            let micSettings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatLinearPCM),
                AVSampleRateKey: 48000,
                AVNumberOfChannelsKey: 2,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsNonInterleaved: false,
                AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsBigEndianKey: false
            ]
            
            if recordingType == "microphone" {
                // For microphone-only, record directly to output file
                micRecorder = try AVAudioRecorder(url: url, settings: micSettings)
                micRecorder?.record()
            } else {
                // For both, we'll need to mix later (simplified approach)
                let micURL = URL(fileURLWithPath: outputPath.replacingOccurrences(of: ".wav", with: "_mic.wav"))
                micRecorder = try AVAudioRecorder(url: micURL, settings: micSettings)
                micRecorder?.record()
            }
        }
        
        // Start system audio recording if needed
        if recordingType == "internal" || recordingType == "both" {
            try stream.addStreamOutput(handler, type: .audio, sampleHandlerQueue: .main)
            try await stream.startCapture()
        }
        
        // Wait for specified duration
        try await Task.sleep(nanoseconds: UInt64(duration * 1_000_000_000))
        
        // Stop recording and finalize
        if recordingType == "internal" || recordingType == "both" {
            try await stream.stopCapture()
            audioInput.markAsFinished()
            await writer.finishWriting()
        }
        
        if recordingType == "microphone" || recordingType == "both" {
            micRecorder?.stop()
        }
        
        if recordingType == "both" {
            print("Recording complete. System audio saved to \(outputPath)")
            print("Microphone audio saved to \(outputPath.replacingOccurrences(of: ".wav", with: "_mic.wav"))")
        } else {
            print("Recording complete. Audio saved to \(outputPath)")
        }
        
    } catch {
        print("Error occurred: \(error)")
    }
}

await recordAudio()