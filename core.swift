//
//  core.swift
//  macOS Internal Audio Recording
//
//  A Swift implementation for recording system audio and microphone input
//  using ScreenCaptureKit, AVFoundation, and CoreAudio.
//

import AVFoundation
import CoreAudio
import Foundation
import ScreenCaptureKit

nonisolated(unsafe) var shouldStop = false

enum RecorderError: LocalizedError {
    case badArguments(String)
    case unsupportedRecordingType(String)
    case microphonePermissionDenied
    case microphoneRecordStartFailed
    case noDisplayFound
    case micDeviceNotFound(String)
    case audioHardwareError(String)

    var errorDescription: String? {
        switch self {
        case .badArguments(let msg):
            return "Bad arguments: \(msg)"
        case .unsupportedRecordingType(let v):
            return "Unsupported recording type: \(v)"
        case .microphonePermissionDenied:
            return "Microphone permission denied."
        case .microphoneRecordStartFailed:
            return "Failed to start microphone recorder."
        case .noDisplayFound:
            return "No display found for system audio capture."
        case .micDeviceNotFound(let selector):
            return "Microphone device not found for selector: \(selector)"
        case .audioHardwareError(let msg):
            return "Audio hardware error: \(msg)"
        }
    }
}

struct RecorderOptions {
    var outputPath: String = "audio.wav"
    var duration: Double = 10.0
    var recordingType: String = "internal"
    var micDeviceSelector: String = ""
    var listMicsJSON: Bool = false
    var testMicsJSON: Bool = false
    var testDuration: Double = 1.5
    var testSettle: Double = 0.25
}

struct MicDeviceInfo: Codable {
    var index: Int
    var uid: String
    var name: String
    var input_channels: Int
    var is_default: Bool
    var device_id: UInt32
}

struct MicTestResult: Codable {
    var index: Int
    var uid: String
    var name: String
    var input_channels: Int
    var ok: Bool
    var bytes: Int
    var rms: Double
    var error: String
}

func setupSignalHandler() {
    signal(SIGINT) { _ in
        shouldStop = true
    }
}

func parseOptions() throws -> RecorderOptions {
    var options = RecorderOptions()
    let args = Array(CommandLine.arguments.dropFirst())
    var positional: [String] = []

    var i = 0
    while i < args.count {
        let arg = args[i]
        switch arg {
        case "--list-mics-json":
            options.listMicsJSON = true
        case "--test-mics-json":
            options.testMicsJSON = true
        case "--mic-device":
            guard i + 1 < args.count else {
                throw RecorderError.badArguments("--mic-device requires a value")
            }
            i += 1
            options.micDeviceSelector = args[i]
        case "--test-duration":
            guard i + 1 < args.count else {
                throw RecorderError.badArguments("--test-duration requires a value")
            }
            i += 1
            options.testDuration = Double(args[i]) ?? options.testDuration
        case "--test-settle":
            guard i + 1 < args.count else {
                throw RecorderError.badArguments("--test-settle requires a value")
            }
            i += 1
            options.testSettle = Double(args[i]) ?? options.testSettle
        default:
            positional.append(arg)
        }
        i += 1
    }

    if options.listMicsJSON || options.testMicsJSON {
        return options
    }

    if positional.count > 0 {
        options.outputPath = positional[0]
    }
    if positional.count > 1 {
        options.duration = Double(positional[1]) ?? options.duration
    }
    if positional.count > 2 {
        options.recordingType = positional[2]
    }

    let normalized = options.recordingType.lowercased()
    if !["internal", "microphone", "both"].contains(normalized) {
        throw RecorderError.unsupportedRecordingType(options.recordingType)
    }
    options.recordingType = normalized
    return options
}

func encodeJSON<T: Encodable>(_ value: T) throws -> String {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try encoder.encode(value)
    return String(data: data, encoding: .utf8) ?? "{}"
}

func ensureMicrophonePermission() async throws {
    let status = AVCaptureDevice.authorizationStatus(for: .audio)
    switch status {
    case .authorized:
        return
    case .notDetermined:
        let granted = await AVCaptureDevice.requestAccess(for: .audio)
        if !granted {
            throw RecorderError.microphonePermissionDenied
        }
    default:
        throw RecorderError.microphonePermissionDenied
    }
}

func allAudioDeviceIDs() throws -> [AudioDeviceID] {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var size: UInt32 = 0
    var status = AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size)
    if status != noErr {
        throw RecorderError.audioHardwareError("query devices size failed: \(status)")
    }
    let count = Int(size) / MemoryLayout<AudioDeviceID>.stride
    if count <= 0 {
        return []
    }
    var ids = Array(repeating: AudioDeviceID(0), count: count)
    status = ids.withUnsafeMutableBufferPointer { buf in
        AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject),
            &address,
            0,
            nil,
            &size,
            buf.baseAddress!
        )
    }
    if status != noErr {
        throw RecorderError.audioHardwareError("query devices failed: \(status)")
    }
    return ids
}

func deviceInputChannels(deviceID: AudioDeviceID) -> Int {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyStreamConfiguration,
        mScope: kAudioDevicePropertyScopeInput,
        mElement: kAudioObjectPropertyElementMain
    )
    var size: UInt32 = 0
    let statusSize = AudioObjectGetPropertyDataSize(deviceID, &address, 0, nil, &size)
    if statusSize != noErr || size == 0 {
        return 0
    }
    let raw = UnsafeMutableRawPointer.allocate(byteCount: Int(size), alignment: MemoryLayout<AudioBufferList>.alignment)
    defer { raw.deallocate() }
    let status = AudioObjectGetPropertyData(deviceID, &address, 0, nil, &size, raw)
    if status != noErr {
        return 0
    }
    let bufferList = raw.assumingMemoryBound(to: AudioBufferList.self)
    let buffers = UnsafeMutableAudioBufferListPointer(bufferList)
    var total = 0
    for b in buffers {
        total += Int(b.mNumberChannels)
    }
    return total
}

func deviceStringProperty(deviceID: AudioDeviceID, selector: AudioObjectPropertySelector) -> String {
    var address = AudioObjectPropertyAddress(
        mSelector: selector,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var value: Unmanaged<CFString>? = nil
    var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
    let status = AudioObjectGetPropertyData(deviceID, &address, 0, nil, &size, &value)
    if status != noErr {
        return ""
    }
    return (value?.takeUnretainedValue() as String?) ?? ""
}

func defaultInputDeviceID() -> AudioDeviceID? {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDefaultInputDevice,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var devID: AudioDeviceID = 0
    var size = UInt32(MemoryLayout<AudioDeviceID>.size)
    let status = AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &devID)
    if status != noErr || devID == 0 {
        return nil
    }
    return devID
}

func setDefaultInputDeviceID(_ deviceID: AudioDeviceID) throws {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDefaultInputDevice,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var dev = deviceID
    let size = UInt32(MemoryLayout<AudioDeviceID>.size)
    let status = AudioObjectSetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, size, &dev)
    if status != noErr {
        throw RecorderError.audioHardwareError("set default input failed: \(status)")
    }
}

func listMicDevices() throws -> [MicDeviceInfo] {
    let ids = try allAudioDeviceIDs()
    let defaultID = defaultInputDeviceID()
    var out: [MicDeviceInfo] = []
    var idx = 0
    for dev in ids {
        let ch = deviceInputChannels(deviceID: dev)
        if ch <= 0 {
            continue
        }
        let uid = deviceStringProperty(deviceID: dev, selector: kAudioDevicePropertyDeviceUID)
        let name = deviceStringProperty(deviceID: dev, selector: kAudioObjectPropertyName)
        out.append(
            MicDeviceInfo(
                index: idx,
                uid: uid,
                name: name.isEmpty ? "AudioDevice-\(dev)" : name,
                input_channels: ch,
                is_default: defaultID == dev,
                device_id: dev
            )
        )
        idx += 1
    }
    return out
}

func chooseMicDevice(selector: String, devices: [MicDeviceInfo]) -> MicDeviceInfo? {
    let sel = selector.trimmingCharacters(in: .whitespacesAndNewlines)
    if sel.isEmpty {
        return nil
    }
    if let intVal = Int(sel), let hit = devices.first(where: { $0.index == intVal }) {
        return hit
    }
    if let hit = devices.first(where: { $0.uid == sel }) {
        return hit
    }
    let lower = sel.lowercased()
    if let hit = devices.first(where: { $0.name.lowercased() == lower }) {
        return hit
    }
    if let hit = devices.first(where: { $0.name.lowercased().contains(lower) }) {
        return hit
    }
    return nil
}

func estimateWavRMS(url: URL) -> Double {
    guard let data = try? Data(contentsOf: url), data.count > 44 else {
        return 0.0
    }
    let payload = data.subdata(in: 44 ..< data.count)
    if payload.count < 2 {
        return 0.0
    }
    let sampleCount = payload.count / 2
    let sumSq: Double = payload.withUnsafeBytes { raw in
        let samples = raw.bindMemory(to: Int16.self)
        if samples.isEmpty {
            return 0.0
        }
        var acc = 0.0
        for s in samples {
            let v = Double(s)
            acc += v * v
        }
        return acc
    }
    if sampleCount <= 0 {
        return 0.0
    }
    return sqrt(sumSq / Double(sampleCount))
}

func micSettings() -> [String: Any] {
    return [
        AVFormatIDKey: Int(kAudioFormatLinearPCM),
        AVSampleRateKey: 48000,
        AVNumberOfChannelsKey: 2,
        AVLinearPCMBitDepthKey: 16,
        AVLinearPCMIsNonInterleaved: false,
        AVLinearPCMIsFloatKey: false,
        AVLinearPCMIsBigEndianKey: false
    ]
}

func runMicDeviceTests(options: RecorderOptions) async throws {
    try await ensureMicrophonePermission()
    let devices = try listMicDevices()
    let originalDefault = defaultInputDeviceID()
    defer {
        if let originalDefault {
            try? setDefaultInputDeviceID(originalDefault)
        }
    }

    let tmpBase = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("mic_probe_\(UUID().uuidString)")
    try? FileManager.default.createDirectory(at: tmpBase, withIntermediateDirectories: true)

    var results: [MicTestResult] = []
    for dev in devices {
        var item = MicTestResult(
            index: dev.index,
            uid: dev.uid,
            name: dev.name,
            input_channels: dev.input_channels,
            ok: false,
            bytes: 0,
            rms: 0.0,
            error: ""
        )

        do {
            try setDefaultInputDeviceID(dev.device_id)
            if options.testSettle > 0 {
                let nanos = UInt64(max(0.0, options.testSettle) * 1_000_000_000.0)
                try await Task.sleep(nanoseconds: nanos)
            }
            let outURL = tmpBase.appendingPathComponent("mic_\(dev.index).wav")
            let recorder = try AVAudioRecorder(url: outURL, settings: micSettings())
            recorder.prepareToRecord()
            let started = recorder.record()
            if !started {
                throw RecorderError.microphoneRecordStartFailed
            }
            let nanos = UInt64(max(0.2, options.testDuration) * 1_000_000_000.0)
            try await Task.sleep(nanoseconds: nanos)
            recorder.stop()

            if let attrs = try? FileManager.default.attributesOfItem(atPath: outURL.path),
               let sizeNum = attrs[.size] as? NSNumber
            {
                item.bytes = sizeNum.intValue
            }
            item.rms = estimateWavRMS(url: outURL)
            item.ok = item.bytes > 44 && item.rms > 0.0
        } catch {
            item.ok = false
            item.error = String(describing: error)
        }
        results.append(item)
    }

    let payload: [String: Any] = [
        "ok": true,
        "count": results.count,
        "duration_s": options.testDuration,
        "settle_s": options.testSettle,
        "results": results.map { r in
            [
                "index": r.index,
                "uid": r.uid,
                "name": r.name,
                "input_channels": r.input_channels,
                "ok": r.ok,
                "bytes": r.bytes,
                "rms": r.rms,
                "error": r.error
            ] as [String: Any]
        }
    ]
    let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8) ?? "{\"ok\":false}")
}

func emitMicListJSON() throws {
    let list = try listMicDevices()
    let payload: [String: Any] = [
        "ok": true,
        "count": list.count,
        "devices": list.map { d in
            [
                "index": d.index,
                "uid": d.uid,
                "name": d.name,
                "input_channels": d.input_channels,
                "is_default": d.is_default
            ] as [String: Any]
        }
    ]
    let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8) ?? "{\"ok\":false}")
}

final class AudioHandler: NSObject, SCStreamOutput {
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

func recordAudio(options: RecorderOptions) async throws {
    setupSignalHandler()

    let captureSystem = options.recordingType == "internal" || options.recordingType == "both"
    let captureMic = options.recordingType == "microphone" || options.recordingType == "both"
    let outputURL = URL(fileURLWithPath: options.outputPath)

    var stream: SCStream?
    var writer: AVAssetWriter?
    var audioInput: AVAssetWriterInput?
    var micRecorder: AVAudioRecorder?
    var selectedMic: MicDeviceInfo?
    var restoreDefaultInput: AudioDeviceID?

    if captureMic {
        try await ensureMicrophonePermission()
        if !options.micDeviceSelector.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            let devices = try listMicDevices()
            guard let hit = chooseMicDevice(selector: options.micDeviceSelector, devices: devices) else {
                throw RecorderError.micDeviceNotFound(options.micDeviceSelector)
            }
            let current = defaultInputDeviceID()
            if current != hit.device_id {
                restoreDefaultInput = current
                try setDefaultInputDeviceID(hit.device_id)
            }
            selectedMic = hit
            print("Mic selected: index=\(hit.index) uid=\(hit.uid) name=\(hit.name) channels=\(hit.input_channels)")
        }
    }

    defer {
        if let restoreDefaultInput {
            try? setDefaultInputDeviceID(restoreDefaultInput)
        }
    }

    if captureSystem {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else {
            throw RecorderError.noDisplayFound
        }

        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.sampleRate = 48000
        config.channelCount = 2
        config.width = Int(display.width)
        config.height = Int(display.height)

        let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
        let s = SCStream(filter: filter, configuration: config, delegate: nil)

        let w = try AVAssetWriter(outputURL: outputURL, fileType: .wav)
        let input = AVAssetWriterInput(mediaType: .audio, outputSettings: micSettings())
        input.expectsMediaDataInRealTime = true
        w.add(input)
        w.startWriting()
        w.startSession(atSourceTime: .zero)
        let handler = AudioHandler(input: input)
        try s.addStreamOutput(handler, type: .audio, sampleHandlerQueue: .main)

        stream = s
        writer = w
        audioInput = input
    }

    if captureMic {
        if options.recordingType == "microphone" {
            micRecorder = try AVAudioRecorder(url: outputURL, settings: micSettings())
        } else {
            let micURL = URL(fileURLWithPath: options.outputPath.replacingOccurrences(of: ".wav", with: "_mic.wav"))
            micRecorder = try AVAudioRecorder(url: micURL, settings: micSettings())
        }
        micRecorder?.prepareToRecord()
        micRecorder?.isMeteringEnabled = true
        let ok = micRecorder?.record() ?? false
        if !ok {
            throw RecorderError.microphoneRecordStartFailed
        }
    }

    if captureSystem {
        try await stream?.startCapture()
    }

    if options.duration <= 0 {
        while !shouldStop {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
    } else {
        let startTime = Date()
        while !shouldStop && Date().timeIntervalSince(startTime) < options.duration {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
    }

    if captureSystem {
        if let stream {
            do {
                try await stream.stopCapture()
            } catch {
                let nsErr = error as NSError
                // Ignore stop-time errors when stream is already stopped/invalid.
                if !(nsErr.domain.contains("SCStreamErrorDomain") && nsErr.code == -3808) {
                    throw error
                }
            }
        }
        audioInput?.markAsFinished()
        await writer?.finishWriting()
    }
    if captureMic {
        micRecorder?.stop()
    }

    if options.recordingType == "both" {
        print("Recording complete. System audio saved to \(options.outputPath)")
        print("Microphone audio saved to \(options.outputPath.replacingOccurrences(of: ".wav", with: "_mic.wav"))")
    } else if options.recordingType == "microphone", let selectedMic {
        print("Recording complete. Mic(\(selectedMic.name)) saved to \(options.outputPath)")
    } else {
        print("Recording complete. Audio saved to \(options.outputPath)")
    }
}

func run() async -> Int32 {
    do {
        let options = try parseOptions()
        if options.listMicsJSON {
            try emitMicListJSON()
            return 0
        }
        if options.testMicsJSON {
            try await runMicDeviceTests(options: options)
            return 0
        }
        try await recordAudio(options: options)
        return 0
    } catch {
        fputs("Error occurred: \(error)\n", stderr)
        return 1
    }
}

let rc = await run()
if rc != 0 {
    Foundation.exit(rc)
}
