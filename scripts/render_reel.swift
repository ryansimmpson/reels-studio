import AVFoundation
import Foundation

// render_reel <source video> <edl.json> <out.mp4> <reel dir> [audio]
// Builds the reel's edited, loudness-processed audio (<reel dir>/edit_audio.wav, with the SFX bus from
// <reel dir>/plan.json) and the base footage (the cut, at the source's own size and orientation) that the 9:16
// HyperFrames composition crops and animates. "audio" as the last argument rebuilds only the audio (seconds).
// plan.json "fade": false (the reel default) skips a fade to silence so the reel can loop; only a 60 ms de-click
// is applied to the last samples.
// The voice comes from one channel of the source: REELS_MIC=left|right|mix (default: the "mic" ingest.py wrote to
// <work>/source.json, else mix). A lav on one channel of a camera wants left or right; a phone or a mixed file, mix.
setvbuf(stdout, nil, _IONBF, 0)
let args = CommandLine.arguments
let srcURL = URL(fileURLWithPath: args[1])
let edl = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[2]))) as! [String: Any]
let outURL = URL(fileURLWithPath: args[3])
let work = args[4]
let audioOnly = args.count > 5 && args[5] == "audio"
let env = ProcessInfo.processInfo.environment
let srcInfo = (try? JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: "\(work)/../../source.json")))) as? [String: Any] ?? [:]
let micMode = (env["REELS_MIC"] ?? srcInfo["mic"] as? String ?? "mix").lowercased()

let planEarly = (try? JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: "\(work)/plan.json")))) as? [String: Any] ?? [:]
let fadeOut = (planEarly["fade"] as? Bool) ?? false
let segs = (edl["segments"] as! [[Int]]).map { ($0[0], $0[1]) }
let FR = CMTime(value: 1001, timescale: 30000)
let SR = 48000.0
let samplesPerFrame = SR * 1001.0 / 30000.0   // 1601.6

func await_<T>(_ f: @escaping () async throws -> T) -> T {
  let sem = DispatchSemaphore(value: 0); var r: T!
  Task { r = try! await f(); sem.signal() }
  sem.wait(); return r
}

let asset = AVURLAsset(url: srcURL)
let srcVideo = await_ { try await asset.loadTracks(withMediaType: .video).first! }
let srcAudio = await_ { try await asset.loadTracks(withMediaType: .audio).first! }

// ---------- 1. read the mic channel ----------
print("reading audio (mic: \(micMode))…")
var mic = [Float](); mic.reserveCapacity(Int(2130 * SR))
do {
  let reader = try! AVAssetReader(asset: asset)
  let out = AVAssetReaderTrackOutput(track: srcAudio, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 32, AVLinearPCMIsFloatKey: true, AVLinearPCMIsNonInterleaved: false, AVLinearPCMIsBigEndianKey: false, AVNumberOfChannelsKey: 2, AVSampleRateKey: 48000])
  reader.add(out); reader.startReading()
  while let sb = out.copyNextSampleBuffer() {
    guard let bb = CMSampleBufferGetDataBuffer(sb) else { continue }
    let len = CMBlockBufferGetDataLength(bb)
    var raw = [Float](repeating: 0, count: len / 4)
    raw.withUnsafeMutableBytes { _ = CMBlockBufferCopyDataBytes(bb, atOffset: 0, dataLength: len, destination: $0.baseAddress!) }
    var i = 0
    while i + 1 < raw.count {
      mic.append(micMode == "left" ? raw[i] : micMode == "right" ? raw[i + 1] : 0.5 * (raw[i] + raw[i + 1])); i += 2
    }
  }
}

// ---------- 2. assemble edited audio with short fades at every cut ----------
var edited = [Float]()
var cumFrames = 0
let cutIn = Int(0.006 * SR), cutOut = Int(0.025 * SR)
for (s, e) in segs {
  let n = e - s
  let a0 = Int((Double(cumFrames) * samplesPerFrame).rounded())
  let a1 = Int((Double(cumFrames + n) * samplesPerFrame).rounded())
  let len = a1 - a0
  let src0 = Int((Double(s) * samplesPerFrame).rounded())
  var chunk = [Float](repeating: 0, count: len)
  for k in 0..<len { let idx = src0 + k; chunk[k] = idx < mic.count ? mic[idx] : 0 }
  for k in 0..<min(cutIn, len) { chunk[k] *= Float(k) / Float(cutIn) }
  for k in 0..<min(cutOut, len) { chunk[len - 1 - k] *= Float(k) / Float(cutOut) }
  edited.append(contentsOf: chunk)
  cumFrames += n
}
mic = []
print(String(format: "edited audio: %.1fs", Double(edited.count) / SR))

// ---------- 3. DSP ----------
struct Biquad {
  var b0, b1, b2, a1, a2: Double; var z1 = 0.0, z2 = 0.0
  mutating func run(_ x: Double) -> Double { let y = b0*x + z1; z1 = b1*x - a1*y + z2; z2 = b2*x - a2*y; return y }
}
func highpass(_ f: Double) -> Biquad {
  let w = 2 * Double.pi * f / SR, q = 0.7071, al = sin(w) / (2*q), c = cos(w), a0 = 1 + al
  return Biquad(b0: (1+c)/2/a0, b1: -(1+c)/a0, b2: (1+c)/2/a0, a1: -2*c/a0, a2: (1-al)/a0)
}
// BS.1770 integrated loudness, reported for a dual-mono stereo file
func lufs(_ x: [Float]) -> Double {
  var s1 = Biquad(b0: 1.53512485958697, b1: -2.69169618940638, b2: 1.19839281085285, a1: -1.69065929318241, a2: 0.73248077421585)
  var s2 = Biquad(b0: 1, b1: -2, b2: 1, a1: -1.99004745483398, a2: 0.99007225036621)
  let step = Int(0.1 * SR)
  var sq = [Double](); sq.reserveCapacity(x.count / step + 1)
  var acc = 0.0, n = 0
  for v in x { let k = s2.run(s1.run(Double(v))); acc += k*k; n += 1; if n == step { sq.append(acc / Double(n)); acc = 0; n = 0 } }
  var blocks = [Double]()
  if sq.count >= 4 { for i in 0...(sq.count - 4) { blocks.append((sq[i] + sq[i+1] + sq[i+2] + sq[i+3]) / 4 * 2) } }
  func L(_ z: Double) -> Double { -0.691 + 10 * log10(z) }
  let abs = blocks.filter { L($0) > -70 }
  let rel = L(abs.reduce(0, +) / Double(abs.count)) - 10
  let gated = abs.filter { L($0) > rel }
  return L(gated.reduce(0, +) / Double(gated.count))
}

var hp = highpass(80)
var x = edited.map { Float(hp.run(Double($0))) }
edited = []
let L0 = lufs(x)
print(String(format: "loudness before: %.1f LUFS", L0))

// pre-gain to -20 LUFS, then compress
var g0 = Float(pow(10, (-20 - L0) / 20))
for i in x.indices { x[i] *= g0 }
do {
  let thr = -26.0, ratio = 3.0, knee = 6.0
  let det = exp(-1 / (0.010 * SR)), att = exp(-1 / (0.005 * SR)), rel = exp(-1 / (0.120 * SR))
  var ms = 0.0, gr = 0.0
  for i in x.indices {
    let v = Double(x[i]); ms = det * ms + (1 - det) * v * v
    let lvl = 10 * log10(ms + 1e-12)
    var target = 0.0
    let over = lvl - thr
    if over > knee / 2 { target = -(over - over / ratio) }
    else if over > -knee / 2 { let k = over + knee / 2; target = -((1 - 1 / ratio) * k * k / (2 * knee)) }
    gr = target < gr ? att * gr + (1 - att) * target : rel * gr + (1 - rel) * target
    x[i] = Float(v * pow(10, gr / 20))
  }
}
let L1 = lufs(x)
let makeup = Float(pow(10, (-14 - L1) / 20))
for i in x.indices { x[i] *= makeup }

// ---------- SFX bus: library samples (a built-in synth stands in for a missing kind), mixed under the voice ----------
struct XorShift { var s: UInt64; mutating func next() -> Float { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return Float(s % 2_000_001) / 1_000_000 - 1 } }
func synth(_ kind: String) -> [Float] {
  var rng = XorShift(s: 0x9E3779B97F4A7C15 &+ UInt64(kind.count))
  let sr = Float(SR)
  func bandNoise(_ dur: Float, _ fc: (Float) -> Float, _ env: (Float) -> Float, q: Float = 0.6) -> [Float] {
    let n = Int(dur * sr); var o = [Float](repeating: 0, count: n); var low: Float = 0, band: Float = 0
    for i in 0..<n { let u = Float(i) / Float(n); let f = 2 * sinf(.pi * min(fc(u), 9000) / sr)
      let xin = rng.next(); low += f * band; let high = xin - low - q * band; band += f * high; o[i] = band * env(u) }
    return o
  }
  var o: [Float]
  switch kind {
  case "whoosh": o = bandNoise(0.46, { 350 + 3400 * powf(sinf(.pi * $0), 1.4) }, { powf(sinf(.pi * min(1, $0 * 1.15)), 2.4) })
  case "swish":  o = bandNoise(0.22, { 1400 + 5200 * sinf(.pi * $0) }, { powf(sinf(.pi * $0), 2.0) }, q: 0.9)
  case "riser":  o = bandNoise(0.95, { 300 + 4200 * $0 * $0 }, { powf($0, 2.2) * (1 - max(0, ($0 - 0.93) * 14)) })
  case "pop":
    let n = Int(0.12 * sr); o = [Float](repeating: 0, count: n); var ph: Float = 0
    for i in 0..<n { let t = Float(i) / sr; let f = 280 + 900 * expf(-t / 0.018); ph += 2 * .pi * f / sr
      o[i] = sinf(ph) * expf(-t / 0.028) + (i < 90 ? rng.next() * 0.35 * (1 - Float(i) / 90) : 0) }
  case "tick":
    let n = Int(0.03 * sr); o = (0..<n).map { i in let t = Float(i) / sr; return sinf(2 * .pi * 2700 * t) * expf(-t / 0.005) }
  case "ding":
    let n = Int(0.55 * sr); o = (0..<n).map { i in let t = Float(i) / sr
      return (sinf(2 * .pi * 1320 * t) + 0.45 * sinf(2 * .pi * 1980 * t) + 0.2 * sinf(2 * .pi * 2640 * t)) * expf(-t / 0.16) * min(1, t / 0.002) }
  case "impact":
    let n = Int(0.75 * sr); o = [Float](repeating: 0, count: n); var ph: Float = 0; var lp: Float = 0
    for i in 0..<n { let t = Float(i) / sr; let f = 48 + 40 * expf(-t / 0.05); ph += 2 * .pi * f / sr
      lp += 0.08 * (rng.next() - lp)
      o[i] = sinf(ph) * expf(-t / 0.2) + lp * 2.5 * expf(-t / 0.04) }
  case "shutter":
    let n = Int(0.16 * sr); o = [Float](repeating: 0, count: n)
    for i in 0..<n { let t = Float(i) / sr
      o[i] = rng.next() * (expf(-t / 0.006) + (t > 0.07 ? expf(-(t - 0.07) / 0.008) * 0.8 : 0)) }
  case "marker":  o = bandNoise(0.38, { 2600 + 900 * sinf(.pi * $0) }, { powf(sinf(.pi * $0), 0.8) * 0.8 }, q: 1.4)
  case "scribble": o = bandNoise(0.55, { 1900 + 1500 * sinf(.pi * 9 * $0) }, { powf(sinf(.pi * $0), 0.7) * (0.6 + 0.4 * sinf(.pi * 14 * $0)) }, q: 1.2)
  default: o = []
  }
  let pk = o.map { abs($0) }.max() ?? 1
  return o.map { $0 / max(pk, 1e-6) }
}
// Sounds come from the sound library ($SFX_LIB, default $REELS_HOME/_sound/sfx, see reference/sound.md):
// <lib>/<kind>.wav, or <kind>-1.wav, <kind>-2.wav ... taken in turn so repeats vary. An event may name its own "file"
// (absolute path). <lib>/levels.json holds optional per-kind trims in dB. The synth above stands in for a kind
// the library doesn't have, and the run says which.
let home = env["REELS_HOME"] ?? (NSHomeDirectory() + "/reels-studio")
let sfxLib = env["SFX_LIB"] ?? (home + "/_sound/sfx")
let sfxTrim = ((try? JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: "\(sfxLib)/levels.json")))) as? [String: NSNumber]) ?? [:]
let libNames = ((try? FileManager.default.contentsOfDirectory(atPath: sfxLib)) ?? []).filter { $0.lowercased().hasSuffix(".wav") && !$0.hasPrefix("._") }.sorted()
func libraryFiles(_ kind: String) -> [String] { libNames.filter { $0 == "\(kind).wav" || $0.hasPrefix("\(kind)-") } }
func loadSample(_ path: String) -> [Float]? {
  guard let f = try? AVAudioFile(forReading: URL(fileURLWithPath: path)), f.length > 0,
        let mono = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: SR, channels: 1, interleaved: false),
        let conv = AVAudioConverter(from: f.processingFormat, to: mono),
        let src = AVAudioPCMBuffer(pcmFormat: f.processingFormat, frameCapacity: AVAudioFrameCount(f.length)) else { return nil }
  conv.downmix = true
  do { try f.read(into: src) } catch { return nil }
  let cap = AVAudioFrameCount(Double(f.length) * SR / f.processingFormat.sampleRate) + 4096
  guard let dst = AVAudioPCMBuffer(pcmFormat: mono, frameCapacity: cap) else { return nil }
  var fed = false
  _ = conv.convert(to: dst, error: nil) { _, status in
    if fed { status.pointee = .endOfStream; return nil }
    fed = true; status.pointee = .haveData; return src
  }
  let o = Array(UnsafeBufferPointer(start: dst.floatChannelData![0], count: Int(dst.frameLength)))
  let pk = o.map { abs($0) }.max() ?? 0
  return pk > 1e-6 ? o.map { $0 / pk } : nil   // peak-normalised like the synth, so the approved gains keep their meaning
}
let sfxEvents = ((try? JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: "\(work)/plan.json")))) as? [String: Any])?["sfx"] as? [[String: Any]] ?? []
var sfxCache: [String: [Float]] = [:], sfxTurn: [String: Int] = [:], fromLib = 0, standIns = Set<String>()
for ev in sfxEvents {
  let kind = ev["kind"] as? String ?? "", t = (ev["t"] as! NSNumber).doubleValue, db = (ev["gain"] as? NSNumber)?.doubleValue ?? -26
  var path = ev["file"] as? String
  if path == nil { let files = libraryFiles(kind); if !files.isEmpty { let k = sfxTurn[kind, default: 0]; sfxTurn[kind] = k + 1; path = "\(sfxLib)/\(files[k % files.count])" } }
  let key = path ?? "synth:\(kind)"
  if sfxCache[key] == nil { sfxCache[key] = path.flatMap(loadSample) ?? synth(kind) }
  if path == nil { standIns.insert(kind) } else { fromLib += 1 }
  let buf = sfxCache[key]!, g = Float(pow(10, (db + (sfxTrim[kind]?.doubleValue ?? 0)) / 20)), at = Int(t * SR)
  for k in 0..<buf.count where at + k >= 0 && at + k < x.count { x[at + k] += buf[k] * g }
}
print("sfx mixed: \(sfxEvents.count) events, \(fromLib) from the library" + (standIns.isEmpty ? "" : "; built-in synth for \(standIns.sorted().joined(separator: ", ")) (add files to \(sfxLib) to replace them)"))

// lookahead peak limiter, ceiling -1.5 dBFS
do {
  let ceil = Float(pow(10, -1.5 / 20)), look = Int(0.005 * SR), relC = Float(1 - exp(-1 / (0.060 * SR)))
  let n = x.count
  var g = [Float](repeating: 1, count: n)
  for i in 0..<n { let a = abs(x[i]); if a > ceil { g[i] = ceil / a } }
  // sliding min over [i, i+look]
  var h = [Float](repeating: 1, count: n)
  var dq = [Int](); var head = 0
  var j = 0
  for i in 0..<n {
    while j < n && j <= i + look { while dq.count > head && g[dq.last!] >= g[j] { dq.removeLast() }; dq.append(j); j += 1 }
    while dq[head] < i { head += 1 }
    h[i] = g[dq[head]]
    if head > 4096 { dq.removeFirst(head); head = 0 }
  }
  var r: Float = 1
  for i in 0..<n { r = min(h[i], r + (1 - r) * relC); h[i] = r }
  var sum: Float = 0
  for i in 0..<n {
    sum += h[i]; if i >= look { sum -= h[i - look] }
    let avg = sum / Float(min(i + 1, look))
    x[i] = max(-ceil, min(ceil, x[i] * avg))
  }
}
// fade the end: 0.8 s to silence for a fade-out, otherwise a 60 ms de-click so the reel loops cleanly
do { let n = Int((fadeOut ? 0.8 : 0.06) * SR); for k in 0..<n { x[x.count - 1 - k] *= Float(k) / Float(n) } }
let L2 = lufs(x)
print(String(format: "loudness after: %.1f LUFS, peak %.1f dBFS", L2, 20 * log10(Double(x.map { abs($0) }.max()!))))

// write stereo (dual-mono) 24-bit WAV
let audioURL = URL(fileURLWithPath: "\(work)/edit_audio.wav")
try? FileManager.default.removeItem(at: audioURL)
do {
  let fmt = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: SR, channels: 2, interleaved: false)!
  let f = try! AVAudioFile(forWriting: audioURL, settings: [AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: SR, AVNumberOfChannelsKey: 2, AVLinearPCMBitDepthKey: 24, AVLinearPCMIsFloatKey: false], commonFormat: .pcmFormatFloat32, interleaved: false)
  let chunk = 1 << 16
  var p = 0
  while p < x.count {
    let n = min(chunk, x.count - p)
    let b = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: AVAudioFrameCount(n))!
    b.frameLength = AVAudioFrameCount(n)
    for k in 0..<n { b.floatChannelData![0][k] = x[p + k]; b.floatChannelData![1][k] = x[p + k] }
    try! f.write(from: b); p += n
  }
  f.close()
}
x = []
if audioOnly { print("audio written"); exit(0) }


// ---------- 4. base footage: the cut at the source's own size and orientation ----------
// The 9:16 framing, zooms and layouts all happen in the HyperFrames composition, so this is a plain cut.
print("building the cut…")
let comp = AVMutableComposition()
let vt = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
let at = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
var cursor = CMTime.zero
for (s, e) in segs {
  let r = CMTimeRange(start: CMTimeMultiply(FR, multiplier: Int32(s)), duration: CMTimeMultiply(FR, multiplier: Int32(e - s)))
  try! vt.insertTimeRange(r, of: srcVideo, at: cursor)
  cursor = CMTimeAdd(cursor, r.duration)
}
vt.preferredTransform = await_ { try await srcVideo.load(.preferredTransform) }
let total = cursor
let editedAudio = AVURLAsset(url: audioURL)
let eat = await_ { try await editedAudio.loadTracks(withMediaType: .audio).first! }
let audioDur = await_ { try await editedAudio.load(.duration) }
try! at.insertTimeRange(CMTimeRange(start: .zero, duration: CMTimeMinimum(audioDur, total)), of: eat, at: .zero)
let size = await_ { try await srcVideo.load(.naturalSize) }
print(String(format: "timeline: %d cuts, %.1fs, source %.0fx%.0f", segs.count, total.seconds, size.width, size.height))

try? FileManager.default.removeItem(at: outURL)
let ex = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetHEVCHighestQuality)!
ex.outputURL = outURL
ex.outputFileType = .mp4
ex.shouldOptimizeForNetworkUse = true
let done = DispatchSemaphore(value: 0)
let t0 = Date()
ex.exportAsynchronously { done.signal() }
while done.wait(timeout: .now() + 15) == .timedOut {
  let p = Double(ex.progress)
  let el = Date().timeIntervalSince(t0)
  print(String(format: "export %.1f%%  elapsed %.0fs  eta %.0fs", p * 100, el, p > 0.01 ? el / p - el : 0))
}
print("export status:", ex.status.rawValue, ex.error.map { "\($0)" } ?? "ok", String(format: "in %.0fs", Date().timeIntervalSince(t0)))
