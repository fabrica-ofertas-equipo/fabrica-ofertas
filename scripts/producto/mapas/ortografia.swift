// Corrector ortográfico del sistema (NSSpellChecker) sin red. Entrada por stdin: {"idioma":"pl","palabras":["..."]}.
// Salida: {"idioma":"pl","disponible":true,"mal":[{"palabra":"...","sugerencias":["..."]}]}
// «disponible» es false si macOS no tiene el diccionario del idioma: en ese caso el llamador NO debe dar la capa por pasada.
import AppKit
import Foundation

let datos = FileHandle.standardInput.readDataToEndOfFile()
guard let obj = try? JSONSerialization.jsonObject(with: datos) as? [String: Any],
      let idioma = obj["idioma"] as? String, let palabras = obj["palabras"] as? [String] else {
    FileHandle.standardError.write("entrada inválida\n".data(using: .utf8)!)
    exit(2)
}
let c = NSSpellChecker.shared
let disponibles = c.availableLanguages
var elegido = idioma
if !disponibles.contains(idioma) {
    if let alt = disponibles.first(where: { $0.hasPrefix(idioma) }) { elegido = alt }
}
let disponible = disponibles.contains(elegido) && c.setLanguage(elegido)
var mal: [[String: Any]] = []
if disponible {
    for w in palabras {
        let r = c.checkSpelling(of: w, startingAt: 0)
        if r.location != NSNotFound {
            let g = c.guesses(forWordRange: NSRange(location: 0, length: (w as NSString).length), in: w, language: elegido, inSpellDocumentWithTag: 0) ?? []
            mal.append(["palabra": w, "sugerencias": Array(g.prefix(3))])
        }
    }
}
let salida: [String: Any] = ["idioma": elegido, "disponible": disponible, "mal": mal]
let out = try JSONSerialization.data(withJSONObject: salida, options: [])
print(String(data: out, encoding: .utf8)!)
