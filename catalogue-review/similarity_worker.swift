// Local-only Apple Vision worker. Inputs are paths selected by the server;
// this process never reads credentials, downloads images or changes sources.
import Foundation
import Vision

struct ImageEntry: Decodable {
    let id: String
    let key: String
    let path: String?
}

struct SortRequest: Decodable {
    let groups: [[ImageEntry]]
    let reverse: Bool
    let cache: String
    let result: String
    let status: String
}

struct SortProgress: Encodable {
    let phase: String
    let completed: Int
    let total: Int
}

struct SortResult: Encodable {
    let order: [String]
    let missing_ids: [String]
    let total: Int
    let analysed: Int
    let new_features: Int
    let cached_features: Int
    let algorithm = "Apple Vision feature print revision 2; nearest neighbour"
}

enum WorkerError: Error {
    case invalidRequest
    case unavailable
}

func save<T: Encodable>(_ value: T, to path: String) throws {
    try JSONEncoder().encode(value).write(to: URL(fileURLWithPath: path), options: .atomic)
}

@available(macOS 14.0, *)
func feature(_ image: ImageEntry, cache: URL) -> (VNFeaturePrintObservation?, Bool) {
    guard let path = image.path else { return (nil, false) }
    let file = URL(fileURLWithPath: path)
    guard FileManager.default.fileExists(atPath: file.path) else { return (nil, false) }
    let saved = cache.appendingPathComponent(image.key + ".feature")
    if let data = try? Data(contentsOf: saved),
       let observation = try? NSKeyedUnarchiver.unarchivedObject(
            ofClass: VNFeaturePrintObservation.self, from: data),
       observation.requestRevision == VNGenerateImageFeaturePrintRequestRevision2 {
        return (observation, true)
    }
    do {
        let request = VNGenerateImageFeaturePrintRequest()
        request.revision = VNGenerateImageFeaturePrintRequestRevision2
        request.imageCropAndScaleOption = .scaleFit
        try VNImageRequestHandler(url: file, options: [:]).perform([request])
        guard let observation = request.results?.first else { return (nil, false) }
        let data = try NSKeyedArchiver.archivedData(withRootObject: observation,
                                                  requiringSecureCoding: true)
        try data.write(to: saved, options: .atomic)
        return (observation, false)
    } catch {
        // An unavailable or undecodable preview remains visible at the end of
        // its group. A damaged feature cache can be rebuilt on the next sort.
        return (nil, false)
    }
}

@available(macOS 14.0, *)
func run(_ request: SortRequest) throws {
    let entries = request.groups.flatMap { $0 }
    guard !request.groups.isEmpty, entries.count <= 20_000,
          request.groups.allSatisfy({ !$0.isEmpty }),
          Set(entries.map { $0.id }).count == entries.count,
          entries.allSatisfy({ $0.key.count == 64 && $0.key.allSatisfy { "0123456789abcdef".contains($0) } })
    else { throw WorkerError.invalidRequest }
    let cache = URL(fileURLWithPath: request.cache, isDirectory: true)
    try FileManager.default.createDirectory(at: cache, withIntermediateDirectories: true)
    var features: [String: VNFeaturePrintObservation] = [:]
    var missing: [String] = []
    var created = 0
    var cached = 0
    try save(SortProgress(phase: "analysing", completed: 0, total: entries.count), to: request.status)
    for (index, entry) in entries.enumerated() {
        autoreleasepool {
            let (observation, reused) = feature(entry, cache: cache)
            if let observation {
                features[entry.id] = observation
                if reused { cached += 1 } else { created += 1 }
            } else {
                missing.append(entry.id)
            }
        }
        try save(SortProgress(phase: "analysing", completed: index + 1, total: entries.count), to: request.status)
    }
    var order: [String] = []
    var completed = 0
    try save(SortProgress(phase: "ordering", completed: 0, total: entries.count), to: request.status)
    for group in request.groups {
        var remaining = group.map { $0.id }.filter { features[$0] != nil }
        var sorted: [String] = []
        if !remaining.isEmpty {
            sorted.append(remaining.removeFirst())
            while !remaining.isEmpty {
                let previous = features[sorted.last!]!
                var closest = 0
                var best = Float.infinity
                for (index, candidate) in remaining.enumerated() {
                    var distance: Float = 0
                    try previous.computeDistance(&distance, to: features[candidate]!)
                    // Strict comparison keeps earlier sort rules as the
                    // deterministic tie breaker for identical feature prints.
                    if distance < best { best = distance; closest = index }
                }
                sorted.append(remaining.remove(at: closest))
                try save(SortProgress(phase: "ordering", completed: completed + sorted.count,
                                      total: entries.count), to: request.status)
            }
        }
        if request.reverse { sorted.reverse() }
        order += sorted + group.map { $0.id }.filter { features[$0] == nil }
        completed += group.count
        try save(SortProgress(phase: "ordering", completed: completed, total: entries.count), to: request.status)
    }
    try save(SortResult(order: order, missing_ids: missing, total: entries.count,
                        analysed: features.count, new_features: created,
                        cached_features: cached), to: request.result)
}

do {
    guard CommandLine.arguments.count == 2 else { throw WorkerError.invalidRequest }
    let path = URL(fileURLWithPath: CommandLine.arguments[1])
    let request = try JSONDecoder().decode(SortRequest.self, from: Data(contentsOf: path))
    if #available(macOS 14.0, *) {
        try run(request)
    } else {
        throw WorkerError.unavailable
    }
} catch {
    // Paths and framework diagnostics may contain private catalogue data.
    FileHandle.standardError.write(Data("Local image similarity could not finish.\n".utf8))
    exit(1)
}
