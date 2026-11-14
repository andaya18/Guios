# Suggested importance (IS) computed automatically with AI
Gemini verifies every literature citation (Table 14 of doc/sugerida.pdf); the teacher's formulas turn validated citations into IL and IS.
Formula (doc/sugerida.pdf): r = TC / NS; IL = quartile of r over the 18 factors (QUARTILE.INC, a value equal to a cut goes to the lower quartile); IS = MATRIZ[IE][IL], IE = 3.

## Specs
- S1 "importancia_sugerida = f(importancia_lectura, importancia_experto)" / "importancia_experto es fija: 3 (constante configurable, no la calcula la IA)."
- S2 "importancia_lectura la calcula la IA. Para ello debe investigar en internet cada cita asociada a la lectura y evaluar su relevancia." (L3: "la is debe ser calculada automáticamente con la IA puede hacerlo con las formulas descritas")
- S3 "Determinismo: si vuelvo a calcular sin cambios, el resultado debe ser idéntico." "Usa temperature = 0 y un formato de salida estructurado (JSON con valor numérico y justificación breve)." "Guarda el resultado en la base de datos junto con un hash del conjunto actual de documentos y citas." "Si el hash no cambió, devuelve el valor guardado sin volver a llamar a la IA." "Si se agrega o elimina un documento o una cita, el hash cambia y se recalcula automáticamente."
- S4 "Rúbrica explícita: define en el prompt a la IA los criterios y la escala"
- S5 "Trazabilidad: guarda en la BD las fuentes consultadas, la justificación, la fecha del cálculo y el origen del valor ("ia" o "respaldo")."
- S6 "Manejo de errores: timeouts, límites de la API y fallos de búsqueda, sin romper el flujo ni guardar valores inválidos."
- S7 "agrega pruebas que verifiquen la repetibilidad y el recálculo al eliminar un documento o cita."
- S8 Fallback: "Guárdalos aparte (fixture, archivo JSON o tabla separada), sin mezclarlos con los valores calculados por la IA." "Úsalos únicamente si la IA no puede calcular el valor (timeout, límite de la API, clave inválida, fallo de búsqueda o respuesta inválida). En ese caso, marca el resultado con origen = "respaldo"." "Nunca uses el respaldo en lugar de la IA cuando la IA funciona." "Cuando un valor con origen "respaldo" se vuelva a solicitar y la IA ya esté disponible, recalcúlalo con la IA y reemplaza el respaldo." "registra la diferencia entre el valor de la IA y el de respaldo (sin sobrescribir nada)" "Deja claro en la interfaz o en los logs cuándo se está mostrando un valor de respaldo."
- S9 "Integra el proveedor de IA mediante una clave en variables de entorno (nunca en el código)." "Aísla la lógica en un servicio ... para poder cambiar de proveedor fácilmente."

## Tasks
- T1 [done 00ca93f] Pure formulas (quartile inclusive, IL, IS) + tests reproducing Tables 13, 16, 17. S1.
- T2 [done 00ca93f] Table 14 data (13 documents, 71 citations, 37 subfactors) + fallback IS (Table 17 = catalog v2). S2, S8.
- T3 [done 0261c32] apps/literature: models, hashes, compute with cache/fallback/discrepancy, loader + compute commands. S3, S5, S6, S7, S8.
- T4 [done 0261c32] Gemini verifier (googleSearch + JSON schema, strict validation, error mapping). S2, S4, S6, S9.
- T5 [in progress] Admin tab "Importancia sugerida": IS table with IA/Respaldo origin, documents and citations with scores and sources, add/delete, recalculate, draft catalog version. S3, S5, S8.

## Log
- L1 (user) request of 2026-11-14 with sections 1-4 (IS with AI, AI API, SMTP, closing checklist); formula source doc/sugerida.pdf.
- L2 Design agreed: AI validates each citation of Table 14 against the web using the review's inclusion criteria as rubric; IL/IS computed by the thesis formulas; IS feeds a catalog draft version (formal validation via M02). Replaces the per-evaluation IS idea.
- L3 (user, verbatim) "perfecto, ten en cuenta q la is debe ser calculada automáticamente con la IA  puede hacerlo con las formulas descritas, así queda perfecto, entonces continuemos con eso para terminar todo"
- L4 Gemini docs: structured output + googleSearch only on Gemini 3+; Google recommends temperature 1.0 for Gemini 3 -> AI_TEMPERATURE configurable, default 0 per S3; repeatability guaranteed by hash cache.
- L5 Subagent runtime unavailable (spawn pi ENOENT): T2 extracted inline. Documents without citations are never sent to the AI (found by view test).
