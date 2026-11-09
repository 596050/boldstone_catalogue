// Local image feature extraction and nearest-neighbour gallery ordering.
// Reads cached images only. No image, review, or native Dropbox writes.
import Foundation
import Vision
import ImageIO
import Accelerate

struct Item: Decodable { let id: String; let key: String; let path: String? }
struct Job: Decodable {
    let groups: [[Item]]; let cache: String; let result: String; let status: String
    let reverse: Bool
}
func writeJSON(_ value: Any, _ path: String) throws {
    try JSONSerialization.data(withJSONObject: value).write(to: URL(fileURLWithPath: path), options: .atomic)
}
func features(_ path: String) throws -> [Float] {
    guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: 512
          ] as CFDictionary) else { throw NSError(domain: "Image unavailable", code: 1) }
    let request = VNGenerateImageFeaturePrintRequest()
    request.revision = VNGenerateImageFeaturePrintRequestRevision2
    request.imageCropAndScaleOption = .scaleFit
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    guard let observation = request.results?.first, observation.elementType == .float,
          observation.elementCount == 768 else { throw NSError(domain: "Unsupported feature print", code: 2) }
    return observation.data.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
}
func distance(_ a: [Float], _ b: [Float]) -> Float {
    var sum: Float = 0
    vDSP_distancesq(a, 1, b, 1, &sum, vDSP_Length(a.count))
    return sum
}
do {
    let job = try JSONDecoder().decode(Job.self, from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])))
    try FileManager.default.createDirectory(atPath: job.cache, withIntermediateDirectories: true)
    let items = job.groups.flatMap { $0 }
    var vectors = [String: [Float]](), reused = 0, analysed = 0
    var lastProgress = Date.distantPast
    for (index, item) in items.enumerated() {
        autoreleasepool {
            guard let path = item.path else { return }
            let cache = URL(fileURLWithPath: job.cache).appendingPathComponent(item.key + ".f32")
            if let bytes = try? Data(contentsOf: cache), bytes.count == 768 * 4 {
                let vector = bytes.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
                if vector.allSatisfy({ $0.isFinite }) { vectors[item.id] = vector; reused += 1; return }
            }
            if let vector = try? features(path), vector.allSatisfy({ $0.isFinite }) {
                vectors[item.id] = vector; analysed += 1
                try? vector.withUnsafeBytes { Data($0) }.write(to: cache, options: .atomic)
            }
        }
        if Date().timeIntervalSince(lastProgress) > 0.4 || index == items.count - 1 {
            try writeJSON(["phase": "analysing", "completed": index + 1, "total": items.count], job.status)
            lastProgress = Date()
        }
    }
    try writeJSON(["phase": "ordering", "completed": items.count, "total": items.count], job.status)
    var ordered = [String]()
    // Earlier sort criteria define these independent groups. The input order is
    // the deterministic anchor/tie-breaker from the later criteria.
    for group in job.groups {
        let known = group.filter { vectors[$0.id] != nil }
        let unknown = group.filter { vectors[$0.id] == nil }.map { $0.id }
        var chain = [String]()
        if !known.isEmpty {
            let values = known.map { vectors[$0.id]! }
            var visited = Array(repeating: false, count: known.count)
            var current = 0
            for step in 0..<known.count {
                chain.append(known[current].id); visited[current] = true
                if step == known.count - 1 { break }
                var best = Float.infinity, next = -1
                for candidate in known.indices where !visited[candidate] {
                    let d = distance(values[current], values[candidate])
                    if d < best - 0.0000001 { best = d; next = candidate }
                }
                current = next
            }
        }
        ordered += (job.reverse ? Array(chain.reversed()) : chain) + unknown
    }
    try writeJSON(["order": ordered, "analysed": vectors.count, "new_features": analysed,
                   "cached_features": reused, "total": items.count,
                   "missing_ids": items.filter { vectors[$0.id] == nil }.map { $0.id },
                   "algorithm": "Apple Vision feature prints (revision 2), nearest-neighbour order"], job.result)
} catch {
    FileHandle.standardError.write(Data("Local similarity analysis failed: \(error)\n".utf8))
    exit(1)
}
