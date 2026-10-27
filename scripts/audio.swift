import AVFoundation
// audio <video> <out.wav> <out env.txt>
// Extracts the voice to a 48 kHz mono 16-bit WAV plus an RMS envelope (10 ms windows, dBFS, one value per line).
// REELS_MIC=left|right|mix picks the channel the mic is on (default mix: the average of both).
let mic = (ProcessInfo.processInfo.environment["REELS_MIC"] ?? "mix").lowercased()
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let outWav = URL(fileURLWithPath: CommandLine.arguments[2])
let outEnv = CommandLine.arguments[3]
let asset = AVURLAsset(url: url)
let sem = DispatchSemaphore(value: 0)
var track: AVAssetTrack!
Task { track = try! await asset.loadTracks(withMediaType: .audio).first!; sem.signal() }
sem.wait()
let reader = try! AVAssetReader(asset: asset)
let settings: [String: Any] = [AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 32, AVLinearPCMIsFloatKey: true, AVLinearPCMIsNonInterleaved: false, AVLinearPCMIsBigEndianKey: false, AVNumberOfChannelsKey: 2, AVSampleRateKey: 48000]
let out = AVAssetReaderTrackOutput(track: track, outputSettings: settings)
reader.add(out)
reader.startReading()
let fmt = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 48000, channels: 1, interleaved: false)!
let file = try! AVAudioFile(forWriting: outWav, settings: [AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 48000, AVNumberOfChannelsKey: 1, AVLinearPCMBitDepthKey: 16, AVLinearPCMIsFloatKey: false], commonFormat: .pcmFormatFloat32, interleaved: false)
var env = ""
var acc: Double = 0; var n = 0; var peak: Float = 0
let win = 480
while let sb = out.copyNextSampleBuffer() {
  guard let bb = CMSampleBufferGetDataBuffer(sb) else { continue }
  let len = CMBlockBufferGetDataLength(bb)
  var raw = [Float](repeating: 0, count: len / 4)
  raw.withUnsafeMutableBytes { _ = CMBlockBufferCopyDataBytes(bb, atOffset: 0, dataLength: len, destination: $0.baseAddress!) }
  let count = raw.count / 2
  let buf = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: AVAudioFrameCount(count))!
  buf.frameLength = AVAudioFrameCount(count)
  for i in 0..<count {
    let l = raw[2 * i], r = raw[2 * i + 1], v = mic == "left" ? l : mic == "right" ? r : 0.5 * (l + r)
    buf.floatChannelData![0][i] = v
    acc += Double(v*v); n += 1; if abs(v) > peak { peak = abs(v) }
    if n == win { env += String(format: "%.1f\n", 10*log10(acc/Double(n) + 1e-12)); acc = 0; n = 0 }
  }
  try! file.write(from: buf)
}
file.close()
try! env.write(toFile: outEnv, atomically: true, encoding: .utf8)
print("status", reader.status.rawValue, "peak dBFS", 20*log10(Double(peak)))
