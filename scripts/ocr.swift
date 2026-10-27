import Foundation
import Vision
import AppKit
import AVFoundation
// ocr <image|video> <out.json> [--at SECONDS] [--find "phrase"]...
// On-device text recognition (Apple Vision) for screenshots and screen recordings the creator supplies: the ones capture.mjs
// can't take (apps behind a login, their own computer). For a video it reads the frame at --at. Writes the same sidecar shape
// as capture.mjs: {size, lines: [{text, rect, conf}], finds: {phrase: [[x, y, w, h] per line] per match}}, pixels,
// top-left origin, so screenkit's find= works on either.
let a = CommandLine.arguments
guard a.count >= 3 else { print("usage: ocr <image|video> <out.json> [--at seconds] [--find \"phrase\"]..."); exit(1) }
let src = URL(fileURLWithPath: a[1]), out = URL(fileURLWithPath: a[2])
var at = 0.0, finds: [String] = []
var i = 3
while i < a.count {
  if a[i] == "--at", i + 1 < a.count { at = Double(a[i + 1]) ?? 0; i += 2 }
  else if a[i] == "--find", i + 1 < a.count { finds.append(a[i + 1]); i += 2 }
  else { i += 1 }
}

var cg: CGImage
if ["mp4", "mov", "m4v"].contains(src.pathExtension.lowercased()) {
  let gen = AVAssetImageGenerator(asset: AVURLAsset(url: src))
  gen.appliesPreferredTrackTransform = true
  gen.requestedTimeToleranceBefore = .zero; gen.requestedTimeToleranceAfter = .zero
  cg = try gen.copyCGImage(at: CMTime(seconds: at, preferredTimescale: 600), actualTime: nil)
} else {
  guard let im = NSImage(contentsOf: src), let c = im.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("can't read \(src.path)"); exit(1)
  }
  cg = c
}
let W = Double(cg.width), H = Double(cg.height)
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = true
try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
func px(_ r: CGRect) -> [Double] { [(r.minX * W).rounded(), ((1 - r.maxY) * H).rounded(), (r.width * W).rounded(), (r.height * H).rounded()] }

// reading order: top to bottom, then left to right
let lines = (req.results ?? []).compactMap { o -> (VNRecognizedText, CGRect)? in
  guard let c = o.topCandidates(1).first else { return nil }; return (c, o.boundingBox)
}.sorted { p, q in
  let yp = 1 - p.1.maxY, yq = 1 - q.1.maxY
  return abs(yp - yq) > 0.008 ? yp < yq : p.1.minX < q.1.minX
}

// find: phrases are matched along paragraphs, not the page's global order (two columns would interleave). Each line
// continues into the nearest line just below it that overlaps it horizontally; a chain of those is one paragraph.
let R = lines.map { px($0.1) }                       // [x, y, w, h] in pixels
var nextOf = [Int](repeating: -1, count: lines.count), hasPrev = [Bool](repeating: false, count: lines.count)
for (k, r) in R.enumerated() {
  var best = -1
  for (j, q) in R.enumerated() where j != k {
    let overlap = min(r[0] + r[2], q[0] + q[2]) - max(r[0], q[0])
    let gap = q[1] - (r[1] + r[3])
    guard q[1] > r[1] + r[3] * 0.5, overlap > 0.3 * min(r[2], q[2]), gap < 1.6 * max(r[3], q[3]) else { continue }
    if best < 0 || q[1] < R[best][1] { best = j }
  }
  if best >= 0 && !hasPrev[best] { nextOf[k] = best; hasPrev[best] = true }
}
var chains: [[Int]] = []
for k in lines.indices where !hasPrev[k] { var c = [k]; while let n = c.last.map({ nextOf[$0] }), n >= 0 { c.append(n) }; chains.append(c) }
var found: [String: [[[Double]]]] = [:]
for ph in finds {
  let pat = ph.split(whereSeparator: { $0 == " " }).map { NSRegularExpression.escapedPattern(for: String($0)).replacingOccurrences(of: "-", with: "-\\s*") }.joined(separator: "\\s+")   // a hyphen may wrap: "multi-" / "day"
  guard let re = try? NSRegularExpression(pattern: pat, options: [.caseInsensitive]) else { continue }
  var hits: [[[Double]]] = []
  for c in chains {
    var flat = "", starts: [Int] = []
    for k in c { starts.append((flat as NSString).length); flat += lines[k].0.string + " " }
    for m in re.matches(in: flat, range: NSRange(location: 0, length: (flat as NSString).length)) where hits.count < 6 {
      var boxes: [[Double]] = []
      for (n, k) in c.enumerated() {
        let str = lines[k].0.string, s = starts[n], e = s + (str as NSString).length
        let a0 = max(m.range.location, s), b0 = min(m.range.location + m.range.length, e)
        guard a0 < b0 else { continue }
        let r = String.Index(utf16Offset: a0 - s, in: str)..<String.Index(utf16Offset: b0 - s, in: str)
        if let bb = try? lines[k].0.boundingBox(for: r)?.boundingBox { boxes.append(px(bb)) } else { boxes.append(R[k]) }
      }
      if !boxes.isEmpty { hits.append(boxes) }
    }
  }
  found[ph] = hits
}
let json: [String: Any] = ["source": src.path, "at": at, "size": [Int(W), Int(H)],
                           "lines": lines.map { ["text": $0.0.string, "rect": px($0.1), "conf": Double($0.0.confidence)] },
                           "finds": found]
try JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys]).write(to: out)
print("\(lines.count) lines read from \(src.lastPathComponent) (\(Int(W))x\(Int(H)))")
for (k, v) in found.sorted(by: { $0.key < $1.key }) { print("  find \"\(k)\": \(v.isEmpty ? "NOT FOUND" : v.map { "\($0.count) line(s)" }.joined(separator: ", "))") }
