import SwiftUI
import Charts
import SeagreenCore

enum Palette {
    static let paper = Color(red: 0.963, green: 0.960, blue: 0.930)
    static let surface = Color(red: 0.993, green: 0.992, blue: 0.975)
    static let ink = Color(red: 0.10, green: 0.23, blue: 0.19)
    static let muted = Color(red: 0.37, green: 0.44, blue: 0.39)
    static let green = Color(red: 0.18, green: 0.45, blue: 0.33)
    static let mint = Color(red: 0.75, green: 0.88, blue: 0.73)
    static let line = Color(red: 0.85, green: 0.88, blue: 0.82)
}

struct Panel<Content: View>: View {
    var title: String?
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if let title { Text(title).font(.system(size: 17, weight: .semibold)).foregroundStyle(Palette.ink) }
            content
        }
        .padding(24).frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.surface, in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(Palette.line.opacity(0.75), lineWidth: 1))
    }
}

struct Eyebrow: View {
    let text: String
    var body: some View { Text(text.uppercased()).font(.system(size: 10, weight: .semibold, design: .monospaced)).tracking(2).foregroundStyle(Palette.muted) }
}

struct Tag: View {
    let text: String
    var body: some View { Text(text).font(.system(size: 10, weight: .medium)).padding(.horizontal, 9).padding(.vertical, 5).background(Palette.green.opacity(0.08), in: Capsule()).foregroundStyle(Palette.green) }
}

struct PrimaryButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.system(size: 12, weight: .semibold)).padding(.horizontal, 17).padding(.vertical, 11)
            .foregroundStyle(Palette.surface).background(Palette.ink.opacity(configuration.isPressed ? 0.75 : 1), in: Capsule())
    }
}

struct SecondaryButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.system(size: 12, weight: .medium)).padding(.horizontal, 15).padding(.vertical, 10)
            .foregroundStyle(Palette.ink).background(Palette.line.opacity(configuration.isPressed ? 0.8 : 0.35), in: Capsule())
    }
}

struct SeagreenMark: View {
    var body: some View {
        Group {
            if let path = Bundle.main.path(forResource: "Seagreen", ofType: "icns"), let image = NSImage(contentsOfFile: path) {
                Image(nsImage: image).resizable().interpolation(.high).scaledToFit()
            } else {
                Image(systemName: "drop.fill").resizable().scaledToFit().padding(8).foregroundStyle(Palette.green)
            }
        }.frame(width: 44, height: 44).accessibilityHidden(true)
    }
}

struct ContourArt: View {
    var body: some View {
        Canvas { context, size in
            for i in 0..<23 {
                let inset = Double(i) * 4.3
                var path = Path()
                let rect = CGRect(x: inset, y: inset * 0.55, width: size.width - inset * 2, height: size.height - inset * 1.1)
                path.addEllipse(in: rect)
                context.stroke(path, with: .color(Palette.mint.opacity(0.12 + Double(i) * 0.014)), lineWidth: 0.8)
            }
        }.rotationEffect(.degrees(-28)).accessibilityHidden(true)
    }
}

struct MetricCard: View {
    let label: String
    let value: String
    let unit: String
    let detail: String
    let icon: String
    var body: some View {
        Panel {
            HStack { Eyebrow(text: label); Spacer(); Image(systemName: icon).foregroundStyle(Palette.green) }
            HStack(alignment: .firstTextBaseline, spacing: 5) {
                Text(value).font(.system(size: 34, weight: .regular, design: .rounded)).monospacedDigit()
                Text(unit).font(.system(size: 12)).foregroundStyle(Palette.muted)
            }.foregroundStyle(Palette.ink)
            Text(detail).font(.system(size: 11)).foregroundStyle(Palette.muted).lineLimit(2).frame(height: 30, alignment: .top)
        }
    }
}

struct HistoryChart: View {
    let points: [TimelinePoint]
    var power = false
    struct PlotPoint: Identifiable {
        let id: Int
        let date: Date
        let value: Double
        let segment: Int
    }
    var plotted: [PlotPoint] {
        var result: [PlotPoint] = []
        var previous: TimelinePoint?
        var segment = 0
        for (index, point) in points.enumerated() {
            guard let value = power ? point.watts : point.cpu else { previous = nil; continue }
            if previous == nil || point.date.timeIntervalSince(previous!.date) > 15 || (power && point.powerKey != previous!.powerKey) { segment += 1 }
            result.append(PlotPoint(id: index, date: point.date, value: value, segment: segment))
            previous = point
        }
        return result
    }
    var body: some View {
        Chart(plotted) { point in
            LineMark(x: .value("Time", point.date), y: .value(power ? "Watts" : "CPU %", point.value), series: .value("Continuous samples", point.segment))
                .foregroundStyle(Palette.green).lineStyle(StrokeStyle(lineWidth: 2))
        }
        .chartYScale(domain: power ? 0...max(10, (points.compactMap(\.watts).max() ?? 10) * 1.2) : 0...100)
        .chartXAxis { AxisMarks(values: .automatic(desiredCount: 5)) { _ in AxisValueLabel(format: .dateTime.hour().minute()); AxisGridLine().foregroundStyle(Palette.line.opacity(0.4)) } }
        .chartYAxis { AxisMarks(position: .leading, values: .automatic(desiredCount: 4)) { _ in AxisValueLabel(); AxisGridLine().foregroundStyle(Palette.line.opacity(0.5)) } }
        .frame(height: 170)
        .accessibilityLabel(power ? "Power history in watts" : "System CPU history, percent of all cores")
    }
}

func decimal(_ value: Double?, places: Int = 1) -> String {
    guard let value, value.isFinite else { return "—" }
    return String(format: "%.*f", places, value)
}
func bytes(_ value: UInt64) -> String { ByteCountFormatter.string(fromByteCount: Int64(clamping: value), countStyle: .memory) }
func durationText(_ seconds: Double) -> String {
    let seconds = max(0, Int(seconds))
    return seconds >= 3600 ? "\(seconds / 3600)h \(seconds % 3600 / 60)m" : "\(seconds / 60)m \(seconds % 60)s"
}
