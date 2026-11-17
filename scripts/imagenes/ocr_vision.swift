// OCR con el framework Vision de macOS (sin red, sin dependencias). Imprime un JSON {"lineas":[...], "idiomas":[...]}.
// Uso: swiftc -O scripts/imagenes/ocr_vision.swift -o /ruta/ocr_vision   y luego   /ruta/ocr_vision imagen.png [idioma,idioma]
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2, let img = NSImage(contentsOfFile: args[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("no se pudo abrir la imagen\n".data(using: .utf8)!)
    exit(2)
}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
let soportados = (try? req.supportedRecognitionLanguages()) ?? []
var elegidos: [String] = []
if args.count >= 3 {
    elegidos = args[2].split(separator: ",").map(String.init).filter { soportados.contains($0) }
}
if !elegidos.isEmpty { req.recognitionLanguages = elegidos }
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try? handler.perform([req])
var lineas: [String] = []
for o in (req.results ?? []) {
    if let t = o.topCandidates(1).first { lineas.append(t.string) }
}
let salida: [String: Any] = ["lineas": lineas, "idiomas": elegidos.isEmpty ? Array(soportados.prefix(40)) : elegidos]
let data = try JSONSerialization.data(withJSONObject: salida, options: [.prettyPrinted])
print(String(data: data, encoding: .utf8)!)
