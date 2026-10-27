import AppKit
// vgrid <out.jpg> <cols> <tileW> files...   (9:16 tiles for reel snapshots)
// Labels each tile with its file name (the snapshot time) and draws the platform safe zones in red:
// top 200 px (status bar / search), bottom 380 px (caption, handle, audio), right rail x > 950 from y 900.
let a = CommandLine.arguments, cols = Int(a[2])!, tw = Double(a[3])!, th = tw * 16 / 9, k = tw / 1080
let files = Array(a.dropFirst(4)); let rows = (files.count + cols - 1) / cols
let img = NSImage(size: NSSize(width: tw * Double(cols), height: th * Double(rows)))
img.lockFocus(); NSColor.black.setFill(); NSRect(origin: .zero, size: img.size).fill()
for (i, f) in files.enumerated() { guard let im = NSImage(contentsOfFile: f) else { continue }
  let r = i / cols, c = i % cols, x0 = Double(c) * tw, y0 = th * Double(rows - 1 - r)
  im.draw(in: NSRect(x: x0, y: y0, width: tw, height: th))
  NSColor(red: 1, green: 0.15, blue: 0.15, alpha: 0.8).setStroke()
  for rect in [NSRect(x: x0, y: y0 + th - 200 * k, width: tw, height: 200 * k), NSRect(x: x0, y: y0, width: tw, height: 380 * k),
               NSRect(x: x0 + 950 * k, y: y0 + 380 * k, width: 130 * k, height: 640 * k)] {
    let p = NSBezierPath(rect: rect.insetBy(dx: 1, dy: 1)); p.lineWidth = 1; p.setLineDash([4, 4], count: 2, phase: 0); p.stroke() }
  (URL(fileURLWithPath: f).deletingPathExtension().lastPathComponent as NSString).draw(at: NSPoint(x: x0 + 6, y: y0 + th - 22), withAttributes: [.font: NSFont.boldSystemFont(ofSize: 15), .foregroundColor: NSColor.yellow, .backgroundColor: NSColor.black]) }
img.unlockFocus()
try! NSBitmapImageRep(data: img.tiffRepresentation!)!.representation(using: .jpeg, properties: [.compressionFactor: 0.8])!.write(to: URL(fileURLWithPath: a[1]))
