import SwiftUI
import SeagreenCore

struct NewRecordingView: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) var dismiss
    @State private var title = ""
    @State private var notes = ""
    @State private var units = "1"
    @State private var unitName = "task"
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Eyebrow(text: "An experiment starts here")
            Text("Record a real workload.").font(.system(size: 30, design: .serif))
            Text("Record the same task before and after a change. Keep other apps, display brightness, power source, and task output consistent.").font(.system(size: 12)).foregroundStyle(Palette.muted).lineSpacing(4)
            TextField("Session name, e.g. Local model · baseline", text: $title).textFieldStyle(.roundedBorder)
            TextField("Notes: workload, model, settings, conditions…", text: $notes).textFieldStyle(.roundedBorder)
            HStack {
                VStack(alignment: .leading) { Text("Expected completed work").font(.caption); TextField("1", text: $units).textFieldStyle(.roundedBorder) }
                VStack(alignment: .leading) { Text("Unit").font(.caption); TextField("task / render / tokens", text: $unitName).textFieldStyle(.roundedBorder) }
            }
            Text("You can correct completed work after recording. Energy comparisons require matching sources and at least 90% power coverage. Sessions auto-save and stop after two hours.").font(.system(size: 11)).foregroundStyle(Palette.muted)
            HStack { Button("Cancel") { dismiss() }.buttonStyle(SecondaryButton()); Spacer(); Button("Start recording") {
                model.beginRecording(title: title, notes: notes, units: units, unitName: unitName); dismiss()
            }.buttonStyle(PrimaryButton()) }
        }.padding(32).frame(width: 510).background(Palette.paper).foregroundStyle(Palette.ink)
    }
}

struct ExperimentsView: View {
    @EnvironmentObject var model: AppModel
    @Binding var showRecording: Bool
    @State private var selected: Recording?
    @State private var compareIDs: Set<UUID> = []
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Eyebrow(text: "Evidence over assumptions")
            Text("Make every change measurable.").font(.system(size: 32, design: .serif))
            Text("Compare completed work, elapsed time, and energy from the same source. A lower CPU graph alone is not proof of savings.").font(.system(size: 12)).foregroundStyle(Palette.muted)
        }.sheet(item: $selected) { recording in RecordingDetail(recording: recording).environmentObject(model) }
        if let active = model.active {
            Panel {
                HStack { Tag(text: "Recording"); Text(active.title).font(.headline); Spacer(); Text(durationText(active.duration)).monospacedDigit() }
                HistoryChart(points: Array(active.points.suffix(150)))
                HStack { Text("Power coverage: \(decimal(active.coverage * 100, places: 0))% · \(active.points.count) samples").font(.caption).foregroundStyle(Palette.muted); Spacer(); Button("Finish & save") { model.finishRecording() }.buttonStyle(PrimaryButton()) }
            }
        }
        if model.recordings.isEmpty && model.active == nil {
            Panel {
                VStack(spacing: 18) {
                    Image(systemName: "waveform.path").font(.system(size: 44, weight: .ultraLight)).foregroundStyle(Palette.green)
                    Text("Your first baseline.").font(.system(size: 26, design: .serif))
                    Text("Run a build, render a scene, or test a local model.\nSeagreen records the resources used while you work.").multilineTextAlignment(.center).font(.system(size: 13)).foregroundStyle(Palette.muted).lineSpacing(5)
                    Button("Create a recording") { showRecording = true }.buttonStyle(PrimaryButton())
                }.frame(maxWidth: .infinity).padding(.vertical, 40)
            }
        }
        let comparisons = model.recordings.filter { compareIDs.contains($0.id) }
        if comparisons.count == 2 { ComparisonView(a: comparisons[0], b: comparisons[1]) }
        if !model.recordings.isEmpty {
            Panel(title: "Saved locally") {
                Text("Choose two sessions to compare. Open a session to review its data, edit completed work, or export.").font(.system(size: 11)).foregroundStyle(Palette.muted)
                ForEach(model.recordings) { recording in
                    HStack(spacing: 15) {
                        Toggle("Compare \(recording.title)", isOn: Binding(get: { compareIDs.contains(recording.id) }, set: { on in
                            if on { if compareIDs.count >= 2 { compareIDs.removeAll() }; compareIDs.insert(recording.id) } else { compareIDs.remove(recording.id) }
                        })).labelsHidden().toggleStyle(.checkbox)
                        Button { selected = recording } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(recording.title).font(.system(size: 13, weight: .medium))
                                    Text(recording.started.formatted(date: .abbreviated, time: .shortened)).font(.system(size: 10)).foregroundStyle(Palette.muted)
                                }
                                Spacer()
                                Text(durationText(recording.duration)).frame(width: 75, alignment: .trailing)
                                Text(recording.coveredSeconds > 0 ? "\(decimal(recording.energyWh, places: 3)) Wh" : "No power data").frame(width: 100, alignment: .trailing)
                                Image(systemName: "chevron.right").font(.caption).foregroundStyle(Palette.muted)
                            }.contentShape(Rectangle())
                        }.buttonStyle(.plain)
                    }.padding(.vertical, 10)
                    Divider()
                }
            }
        }
    }
}

struct ComparisonView: View {
    let a: Recording
    let b: Recording
    var body: some View {
        Panel(title: "Session comparison") {
            Text("\(b.title) → \(a.title)").font(.system(size: 14, weight: .medium))
            if let issue = Recording.comparisonIssue(a, b) {
                Label(issue, systemImage: "info.circle").font(.system(size: 12)).foregroundStyle(Palette.muted)
                Text("Runtime: \(durationText(b.duration)) → \(durationText(a.duration)). Energy savings are not calculated for this pair.").font(.system(size: 12))
            } else if let latest = a.energyPerUnit, let baseline = b.energyPerUnit, baseline > 0 {
                let change = (latest - baseline) / baseline * 100
                HStack(spacing: 30) {
                    VStack(alignment: .leading, spacing: 7) { Eyebrow(text: "Energy per \(a.unitName)"); Text("\(decimal(baseline, places: 4)) → \(decimal(latest, places: 4)) Wh").font(.system(size: 23, design: .rounded)) }
                    Spacer()
                    Text("\(change >= 0 ? "+" : "")\(decimal(change))%").font(.system(size: 32, design: .rounded)).foregroundStyle(change < 0 ? Palette.green : Palette.ink)
                }
                Text("Observed change, not a causal guarantee. These readings cover \(a.powerKeys.first ?? "the selected source"). Repeat the workload to account for background activity and variation.").font(.system(size: 11)).foregroundStyle(Palette.muted)
            } else { Text("The baseline has no positive energy total to compare.").font(.caption) }
        }
    }
}

struct RecordingDetail: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) var dismiss
    @State var recording: Recording
    @State private var units = ""
    @State private var confirmDelete = false
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack { Text(recording.title).font(.system(size: 25, design: .serif)); Spacer(); Button("Done") { dismiss() } }
            Text(recording.notes.isEmpty ? "No session notes." : recording.notes).font(.system(size: 12)).foregroundStyle(Palette.muted)
            HistoryChart(points: recording.points)
            HStack(spacing: 25) {
                Text("Duration: \(durationText(recording.duration))")
                Text("Power coverage: \(decimal(recording.coverage * 100, places: 0))%")
                Text("Recorded energy: \(recording.coveredSeconds > 0 ? decimal(recording.energyWh, places: 3) + " Wh" : "Unavailable")")
            }.font(.system(size: 11))
            Text(recording.powerKeys.isEmpty ? "No supported power readings were recorded. CPU and memory data remain available." : recording.powerKeys.joined(separator: " · ")).font(.system(size: 11)).foregroundStyle(Palette.muted)
            HStack {
                Text("Completed work:").font(.caption)
                TextField("Units", text: $units).textFieldStyle(.roundedBorder).frame(width: 80)
                TextField("Unit", text: $recording.unitName).textFieldStyle(.roundedBorder).frame(width: 100)
                Button("Save") {
                    guard let value = Double(units), value.isFinite, value > 0, !recording.unitName.isEmpty else { model.message = "Completed work must be a positive number with a unit."; return }
                    recording.completedUnits = value; model.save(recording); model.reload()
                }.buttonStyle(SecondaryButton())
            }
            HStack {
                Button("Export CSV") { model.export(recording, csv: true) }.buttonStyle(SecondaryButton())
                Button("Export JSON") { model.export(recording, csv: false) }.buttonStyle(SecondaryButton())
                Spacer(); Button("Delete", role: .destructive) { confirmDelete = true }
            }
        }.padding(28).frame(width: 710).background(Palette.paper)
            .onAppear { units = recording.completedUnits.map { String($0) } ?? "" }
            .confirmationDialog("Delete this recording permanently?", isPresented: $confirmDelete) { Button("Delete recording", role: .destructive) { model.delete(recording); dismiss() } }
    }
}
