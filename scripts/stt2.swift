import Foundation
import Speech
import AVFoundation
// stt2 <in.wav> <out.jsonl> [maxSeconds]
// On-device word-level transcription (Apple SpeechAnalyzer, macOS 26+). One JSON line per word: {"s","e","w"}.
// REELS_LANG picks the language (a locale such as en-US, en-GB, es-ES, de-DE, fr-FR, pt-BR; default en-US).
@main struct Main {
  static func main() async throws {
    setvbuf(stdout, nil, _IONBF, 0)
    let inURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outPath = CommandLine.arguments[2]
    let maxSec = CommandLine.arguments.count > 3 ? Double(CommandLine.arguments[3])! : 1e9
    let lang = ProcessInfo.processInfo.environment["REELS_LANG"] ?? "en-US"
    guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: lang)) else {
      let all = await SpeechTranscriber.supportedLocales.map { $0.identifier(.bcp47) }.sorted().joined(separator: ", ")
      print("no on-device transcriber for \(lang). Supported: \(all)"); exit(2)
    }
    let transcriber = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [], attributeOptions: [.audioTimeRange])
    // the on-device model can be missing (first run, or macOS evicted it): install it, then go on
    if let install = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
      print("installing the on-device speech model…"); try await install.downloadAndInstall(); print("model installed")
    }
    let analyzer = SpeechAnalyzer(modules: [transcriber])
    let target = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber])!
    print("target format:", target)
    try await analyzer.prepareToAnalyze(in: target)
    print("prepared")
    var lines: [String] = []
    let collector = Task {
      for try await r in transcriber.results {
        print(String(format: "at %.0fs", r.range.start.seconds))
        for run in r.text.runs {
          guard let tr = run.audioTimeRange else { continue }
          let w = String(r.text[run.range].characters)
          let esc = w.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
          lines.append(String(format: "{\"s\":%.3f,\"e\":%.3f,\"w\":\"%@\"}", tr.start.seconds, tr.end.seconds, esc))
        }
      }
    }
    let (stream, cont) = AsyncStream<AnalyzerInput>.makeStream()
    try await analyzer.start(inputSequence: stream)
    // feed the analyzer in its own format (the model wants 16 kHz; audio.swift writes 48 kHz), converting as we go
    let file = try AVAudioFile(forReading: inURL)
    let src = file.processingFormat
    print("file fmt:", src)
    let conv = AVAudioConverter(from: src, to: target)!
    let chunk: AVAudioFrameCount = AVAudioFrameCount(src.sampleRate)
    let maxFrames = AVAudioFramePosition(maxSec * src.sampleRate)
    var total = 0
    while file.framePosition < min(file.length, maxFrames) {
      let inBuf = AVAudioPCMBuffer(pcmFormat: src, frameCapacity: chunk)!
      try file.read(into: inBuf, frameCount: chunk)
      if inBuf.frameLength == 0 { break }
      let cap = AVAudioFrameCount(Double(inBuf.frameLength) * target.sampleRate / src.sampleRate) + 1024
      let outBuf = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: cap)!
      var fed = false
      var err: NSError?
      _ = conv.convert(to: outBuf, error: &err) { _, status in
        if fed { status.pointee = .noDataNow; return nil }
        fed = true; status.pointee = .haveData; return inBuf
      }
      if let err { throw err }
      total += Int(outBuf.frameLength)
      if outBuf.frameLength > 0 { cont.yield(AnalyzerInput(buffer: outBuf)) }
    }
    cont.finish()
    print("fed audio frames:", total, "auth:", SFSpeechRecognizer.authorizationStatus().rawValue)
    try await analyzer.finalizeAndFinishThroughEndOfInput()
    try await collector.value
    try lines.joined(separator: "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
    print("words:", lines.count)
  }
}
