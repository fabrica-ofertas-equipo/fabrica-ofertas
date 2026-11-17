"""Taxonomía de funnels: componentes, tipos como combinación ordenada de componentes, complejidad y encuadre.

Los datos viven en `taxonomia_funnels.json` (al lado de este archivo); la explicación, en
`references/taxonomia-funnels.md`. Lo usan `ordenar_candidatos.py` y `barrido_por_forma.py`.
Sin red. Solo escribe en la taxonomía cuando se llama a `encuadrar(..., registrar=True)`.

Ideas:
- Un funnel es una secuencia ordenada de componentes de NÚCLEO (quiz, tsl, vsl, advertorial, registro…) más
  EXTRAS que no cambian el nombre (bump, upsell, niveles, video-apoyo…).
- El tipo se llama como su núcleo unido con «+»: `quiz+vsl`, `advertorial+tsl`. El orden importa.
- La complejidad sale de los componentes, no del nombre: un híbrido vale más que cualquiera de sus partes.
- Encuadre: si el núcleo observado coincide (componentes y orden) con un tipo que existe, es ese tipo; si no,
  se crea uno nuevo con nombre compuesto, se guarda el ejemplo que lo originó y queda «nuevo-a-confirmar».
  Nunca se fuerza un funnel distinto dentro de un tipo existente.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

RUTA = Path(__file__).with_name("taxonomia_funnels.json")
ESTADOS = ("base", "previsto", "nuevo-a-confirmar", "confirmado")
SIN_CLASIFICAR = "sin-clasificar"


class ErrorTaxonomia(ValueError):
    """Funnel, componente o archivo que la taxonomía no puede interpretar."""


def cargar(ruta: Path | None = None) -> dict:
    ruta = Path(ruta) if ruta else RUTA
    tax = json.loads(ruta.read_text(encoding="utf-8"))
    for clave in ("componentes", "tipos", "alias", "regla_complejidad"):
        if clave not in tax:
            raise ErrorTaxonomia(f"{ruta}: falta «{clave}»")
    for nombre, c in tax["componentes"].items():
        if c.get("clase") not in ("nucleo", "extra") or not isinstance(c.get("peso"), (int, float)):
            raise ErrorTaxonomia(f"{ruta}: componente «{nombre}» sin clase o peso válidos")
    for nombre, t in tax["tipos"].items():
        if nombre != nombre_tipo(t["componentes"]):
            raise ErrorTaxonomia(f"{ruta}: el tipo «{nombre}» no coincide con sus componentes {t['componentes']}")
        if t.get("estado") not in ESTADOS:
            raise ErrorTaxonomia(f"{ruta}: tipo «{nombre}» con estado «{t.get('estado')}»")
        _exigir_nucleo(tax, t["componentes"], f"tipo «{nombre}»")
    return tax


def nombre_tipo(nucleo: list[str]) -> str:
    return "+".join(nucleo) if nucleo else SIN_CLASIFICAR


def _exigir_nucleo(tax: dict, partes: list[str], donde: str) -> None:
    for p in partes:
        c = tax["componentes"].get(p)
        if c is None:
            conocidos = ", ".join(k for k, v in tax["componentes"].items() if v["clase"] == "nucleo")
            raise ErrorTaxonomia(f"{donde}: componente «{p}» no está en la taxonomía (núcleo conocido: {conocidos}). "
                                 "Si es un componente nuevo, añadirlo a taxonomia_funnels.json con sus señales.")
        if c["clase"] != "nucleo":
            raise ErrorTaxonomia(f"{donde}: «{p}» es un extra, no forma parte del nombre del tipo; va en `extras`.")


def resolver(tax: dict, funnel: str | None = None, componentes: list[str] | None = None,
             extras: list[str] | None = None) -> dict:
    """Devuelve el tipo canónico de un funnel dado por nombre (`funnel`) o por lista de `componentes`.

    Salida: {tipo, nucleo, extras, estado, escrito_como, piso_complejidad}. `estado` es el del tipo en la
    taxonomía o «sin-registrar» si el nombre compuesto es válido pero todavía no existe como tipo.
    """
    extras = list(dict.fromkeys(extras or []))
    piso = None
    if componentes:
        nucleo = [c for c in componentes if tax["componentes"].get(c, {}).get("clase") == "nucleo"]
        for c in componentes:
            if c not in tax["componentes"]:
                raise ErrorTaxonomia(f"componente «{c}» no está en la taxonomía")
            if tax["componentes"][c]["clase"] == "extra" and c not in extras:
                extras.append(c)
    elif funnel in tax["alias"]:
        a = tax["alias"][funnel]
        nucleo = list(tax["tipos"][a["tipo"]]["componentes"])
        extras = list(dict.fromkeys(list(a.get("extras") or []) + extras))
        piso = a.get("piso_complejidad")
    elif funnel in tax["tipos"]:
        nucleo = list(tax["tipos"][funnel]["componentes"])
    elif funnel == SIN_CLASIFICAR:
        nucleo = []
    elif funnel:
        nucleo = [p.strip() for p in funnel.split("+") if p.strip()]
        _exigir_nucleo(tax, nucleo, f"funnel «{funnel}»")
    else:
        raise ErrorTaxonomia("falta `funnel` o `componentes`")
    tipo = nombre_tipo(nucleo)
    estado = tax["tipos"][tipo]["estado"] if tipo in tax["tipos"] else "sin-registrar"
    return {"tipo": tipo, "nucleo": nucleo, "extras": extras, "estado": estado,
            "escrito_como": funnel if funnel else tipo, "piso_complejidad": piso}


def complejidad(tax: dict, nucleo: list[str], extras: list[str], piso: float | None = None) -> float:
    """1 − Π(1 − peso) sobre el núcleo (cada componente una vez) + suma de extras distintos, con tope."""
    regla = tax["regla_complejidad"]
    falta = 1.0
    for c in dict.fromkeys(nucleo):
        falta *= 1.0 - float(tax["componentes"][c]["peso"])
    valor = 1.0 - falta
    for e in dict.fromkeys(extras):
        comp = tax["componentes"].get(e)
        valor += float(comp["peso"]) if comp and comp["clase"] == "extra" else float(regla.get("extra_desconocido", 0.10))
    if piso is not None:
        valor = max(valor, float(piso))
    return min(float(regla.get("tope", 1.0)), valor)


def tipo_canonico(tax: dict, funnel: str | None) -> str | None:
    """Tipo canónico de un nombre guardado (historial); si no se puede interpretar, devuelve el texto tal cual."""
    if not funnel:
        return None
    try:
        return resolver(tax, funnel)["tipo"]
    except ErrorTaxonomia:
        return funnel


def encuadrar(tax: dict, nucleo: list[str], extras: list[str] | None = None, ejemplo: dict | None = None,
              registrar: bool = False, ruta: Path | None = None) -> dict:
    """Regla de encuadre del dueño.

    - Núcleo igual (componentes y orden) a un tipo existente → ese tipo. Si no tenía ejemplo real y se pasa uno
      con `registrar`, se le añade; un tipo «previsto» pasa a «nuevo-a-confirmar» con su primer ejemplo.
    - Núcleo distinto → tipo nuevo con nombre compuesto, estado «nuevo-a-confirmar» y el ejemplo que lo originó.
    - Núcleo vacío → «sin-clasificar»; no se registra nada.
    `ejemplo`: {"pagina", "url", "fecha", "nota"?}. Devuelve {tipo, es_nuevo, estado, mensaje}.
    """
    _exigir_nucleo(tax, nucleo, "encuadre")
    tipo = nombre_tipo(nucleo)
    if not nucleo:
        return {"tipo": tipo, "es_nuevo": False, "estado": "sin-clasificar",
                "mensaje": "No se observó ningún componente de núcleo: queda sin clasificar, no se fuerza un tipo."}
    existe = tipo in tax["tipos"]
    cambio = False
    if existe:
        t = tax["tipos"][tipo]
        es_nuevo = t["estado"] == "nuevo-a-confirmar" or (t["estado"] == "previsto" and bool(ejemplo))
        if registrar and ejemplo and not any(e.get("url") == ejemplo.get("url") and e.get("pagina") == ejemplo.get("pagina")
                                               for e in t["ejemplos"]):
            if t["estado"] == "previsto":
                t["estado"] = "nuevo-a-confirmar"
                t["origen"] = dict(ejemplo)
            if len(t["ejemplos"]) < 5:
                t["ejemplos"].append(dict(ejemplo))
            cambio = True
        mensaje = (f"Encuadra en el tipo existente «{tipo}» ({t['estado']})." if not es_nuevo else
                   f"Primer ejemplo real del tipo «{tipo}»: nuevo, a confirmar por el dueño.")
        estado = t["estado"] if (registrar or not es_nuevo) else "nuevo-a-confirmar"
    else:
        es_nuevo = True
        estado = "nuevo-a-confirmar"
        nombres = " → ".join(tax["componentes"][c]["nombre"] for c in nucleo)
        if registrar:
            if not ejemplo:
                raise ErrorTaxonomia("para registrar un tipo nuevo hace falta el ejemplo que lo originó (página, URL, fecha)")
            tax["tipos"][tipo] = {"componentes": list(nucleo), "estado": estado, "descripcion": nombres + ".",
                                  "origen": dict(ejemplo), "ejemplos": [dict(ejemplo)]}
            cambio = True
        mensaje = f"Tipo NUEVO «{tipo}» ({nombres}): nuevo, a confirmar por el dueño."
    if cambio:
        guardar(tax, ruta)
    return {"tipo": tipo, "es_nuevo": es_nuevo, "estado": estado, "mensaje": mensaje,
            "complejidad": round(complejidad(tax, nucleo, extras or []), 2)}


def guardar(tax: dict, ruta: Path | None = None) -> None:
    """Escritura atómica de la taxonomía (mismo directorio, reemplazo al final)."""
    ruta = Path(ruta) if ruta else RUTA
    fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=".taxonomia-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(_formatear(tax))
    os.replace(tmp, ruta)


def _formatear(tax: dict) -> str:
    """JSON legible: un nivel de sangría para las claves grandes y una línea por tipo y por alias."""
    partes = []
    for clave, valor in tax.items():
        if clave in ("tipos", "alias"):
            filas = ",\n".join(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" for k, v in valor.items())
            partes.append(f" {json.dumps(clave)}: {{\n{filas}\n }}")
        elif clave in ("componentes", "senales_generales", "regla_complejidad", "umbrales_clasificador"):
            partes.append(f" {json.dumps(clave)}: " + json.dumps(valor, ensure_ascii=False, indent=1).replace("\n", "\n "))
        else:
            partes.append(f" {json.dumps(clave)}: {json.dumps(valor, ensure_ascii=False)}")
    return "{\n" + ",\n".join(partes) + "\n}\n"
