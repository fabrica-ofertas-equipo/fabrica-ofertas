// Texto de un PDF: capa de texto (PDFKit) y OCR (Vision) de cada página renderizada. Sin red.
// Uso: ocr_pdf RUTA.pdf [idiomas=pl-PL,en-US] [dpi=200]   ->   {"paginas":[{"n":1,"capa":"...","ocr":["línea",...]}]}
import Foundation
import PDFKit
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write("no se pudo abrir el PDF\n".data(using: .utf8)!)
    exit(2)
}
let idiomas = (args.count >= 3 ? args[2] : "pl-PL,en-US").split(separator: ",").map(String.init)
let dpi = args.count >= 4 ? (Double(args[3]) ?? 200) : 200
var paginas: [[String: Any]] = []
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let capa = page.string ?? ""
    let caja = page.bounds(for: .mediaBox)
    let k = dpi / 72.0
    let tam = NSSize(width: caja.width * k, height: caja.height * k)
    let img = page.thumbnail(of: tam, for: .mediaBox)
    var lineas: [String] = []
    if let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) {
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = false
        let soportados = (try? req.supportedRecognitionLanguages()) ?? []
        let elegidos = idiomas.filter { soportados.contains($0) }
        if !elegidos.isEmpty { req.recognitionLanguages = elegidos }
        try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
        for o in (req.results ?? []) { if let t = o.topCandidates(1).first { lineas.append(t.string) } }
    }
    paginas.append(["n": i + 1, "capa": capa, "ocr": lineas])
}
let data = try JSONSerialization.data(withJSONObject: ["paginas": paginas], options: [])
print(String(data: data, encoding: .utf8)!)
