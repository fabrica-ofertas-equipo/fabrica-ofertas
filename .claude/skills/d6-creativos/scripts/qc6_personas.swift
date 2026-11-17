// Detección de personas, rostros y manos con el framework Vision de macOS (sin red, sin dependencias).
// Es el motor de «caras y manos» del control de calidad de 6 puntos (qc6.py): solo detecta PRESENCIA;
// si las caras y las manos están bien hechas lo juzga una persona o el QA (rubric.md R5).
// Imprime un JSON {"rostros":N,"personas":N,"manos":N}.
// Uso: swiftc -O qc6_personas.swift -o /ruta/qc6_personas   y luego   /ruta/qc6_personas imagen.png
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2, let img = NSImage(contentsOfFile: args[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("no se pudo abrir la imagen\n".data(using: .utf8)!)
    exit(2)
}
let rostros = VNDetectFaceRectanglesRequest()
let personas = VNDetectHumanRectanglesRequest()
let manos = VNDetectHumanHandPoseRequest()
manos.maximumHandCount = 6
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
var errores: [String] = []
do { try handler.perform([rostros, personas, manos]) } catch { errores.append("\(error)") }
let salida: [String: Any] = [
    "rostros": (rostros.results ?? []).count,
    "personas": (personas.results ?? []).count,
    "manos": (manos.results ?? []).count,
    "errores": errores,
]
let data = try JSONSerialization.data(withJSONObject: salida, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
