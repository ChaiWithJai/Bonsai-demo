// Apple Vision OCR fallback for PDF pages without embedded text. Not Bonsai inference.
import Foundation
import Vision
import ImageIO
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(url: url, options: [:])
do {
    try handler.perform([request])
    let lines = (request.results ?? []).compactMap { result -> [String: Any]? in
        guard let candidate = result.topCandidates(1).first else { return nil }
        let box = result.boundingBox
        return ["text": candidate.string, "confidence": candidate.confidence,
                "bbox_normalized_bottom_left": [box.origin.x, box.origin.y, box.size.width, box.size.height]]
    }
    let data = try JSONSerialization.data(withJSONObject: lines, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
} catch {
    FileHandle.standardError.write(Data(String(describing: error).utf8))
    exit(1)
}
