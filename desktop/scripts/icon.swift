import AppKit
import Foundation
let directory = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
for (name, size) in [("icon_16x16",16),("icon_16x16@2x",32),("icon_32x32",32),("icon_32x32@2x",64),("icon_128x128",128),("icon_128x128@2x",256),("icon_256x256",256),("icon_256x256@2x",512),("icon_512x512",512),("icon_512x512@2x",1024)] {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let scale = CGFloat(size) / 64
    let transform = NSAffineTransform(); transform.scale(by: scale); transform.concat()
    NSColor(red: 0.10, green: 0.23, blue: 0.19, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 3, y: 3, width: 58, height: 58), xRadius: 15, yRadius: 15).fill()
    let drop = NSBezierPath(); drop.move(to: NSPoint(x: 32, y: 53))
    drop.curve(to: NSPoint(x: 17, y: 24), controlPoint1: NSPoint(x: 26, y: 43), controlPoint2: NSPoint(x: 17, y: 34))
    drop.curve(to: NSPoint(x: 47, y: 24), controlPoint1: NSPoint(x: 17, y: 4), controlPoint2: NSPoint(x: 47, y: 4))
    drop.curve(to: NSPoint(x: 32, y: 53), controlPoint1: NSPoint(x: 47, y: 34), controlPoint2: NSPoint(x: 38, y: 43))
    NSColor(red: 0.75, green: 0.86, blue: 0.73, alpha: 1).setFill(); drop.fill()
    NSColor(red: 0.10, green: 0.23, blue: 0.19, alpha: 1).setStroke()
    for offset in [0.0, 6.0] {
        let wave = NSBezierPath(); wave.move(to: NSPoint(x: 25, y: 22 - offset))
        wave.curve(to: NSPoint(x: 42, y: 28 - offset), controlPoint1: NSPoint(x: 30, y: 27 - offset), controlPoint2: NSPoint(x: 35, y: 28 - offset))
        wave.lineWidth = 2.4; wave.lineCapStyle = .round; wave.stroke()
    }
    NSGraphicsContext.restoreGraphicsState()
    try bitmap.representation(using: .png, properties: [:])!.write(to: directory.appendingPathComponent(name + ".png"))
}
