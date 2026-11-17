"""Código determinista del Jurado de creativos (pieza 3 del sistema de Juan Pablo Mentor).

La IA vota (agente ``jurado-votante``, una pieza por llamada); este paquete hace todo lo demás, sin red y sin
llamar nunca a un LLM: construir avatares desde la voz del cliente, armar paquetes ciegos, agregar votos,
medir la calibración contra lo cobrado y decidir apagado o promoción. El jurado NUNCA decide gasto: solo ordena
y avisa. Ver ``scripts/jurado/README.md`` y ``.claude/skills/jurado-creativos/SKILL.md``.
"""
