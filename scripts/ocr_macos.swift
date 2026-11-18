// Offline OCR using Apple's system frameworks. No network or third-party models.
import Foundation
import AppKit
import PDFKit
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8)); exit(1)
}
let args = CommandLine.arguments
if args.count == 2 && args[1] == "--check" {
    let request = VNRecognizeTextRequest()
    do {
        let languages = try request.supportedRecognitionLanguages()
        let result: [String: Any] = ["backend": "Apple Vision", "languages": languages, "offline": true]
        FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]))
        exit(0)
    } catch { fail("Vision unavailable: \(error)") }
}
guard args.count == 4, let pageNumber = Int(args[2]), pageNumber > 0 else {
    fail("Usage: document-ocr INPUT.pdf PAGE_NUMBER OUTPUT.png")
}
guard let document = PDFDocument(url: URL(fileURLWithPath: args[1])) else { fail("Cannot open PDF") }
if document.isLocked { fail("Locked PDFs are not supported by the OCR backend") }
guard let page = document.page(at: pageNumber - 1) else { fail("Page out of range") }
let bounds = page.bounds(for: .mediaBox)
let scale = min(2.5, 2600 / max(bounds.width, bounds.height))
let image = page.thumbnail(of: NSSize(width: bounds.width * scale, height: bounds.height * scale), for: .mediaBox)
var rect = CGRect(origin: .zero, size: image.size)
guard let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else { fail("Cannot render PDF page") }
let bitmap = NSBitmapImageRep(cgImage: cg)
guard let png = bitmap.representation(using: .png, properties: [:]) else { fail("Cannot encode page image") }
do {
    try png.write(to: URL(fileURLWithPath: args[3]))
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    let supported = try request.supportedRecognitionLanguages()
    request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"].filter { supported.contains($0) }
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try handler.perform([request])
    let lines: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let b = observation.boundingBox
        return ["text": candidate.string, "confidence": candidate.confidence,
                "bbox": [b.minX, 1 - b.maxY, b.width, b.height]]
    }
    let result: [String: Any] = ["page": pageNumber, "lines": lines, "bbox_units": "normalized-top-left", "image": args[3]]
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]))
} catch { fail("OCR failed: \(error)") }
