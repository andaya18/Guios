# GUIOS PRO: fix current screens and complete the system
Functional source of truth: `doc/GUIOS_PRO_Gabriela.pdf` (sections cited as §). Visual source: Figma linked in that PDF.
Orchestrator session: 01a1d175-78b7-750f-b6ca-4e315b3b11fa. Workers never commit; they report changed files and test output.

## Specs
- S1 "Fidelidad 100% a Figma (UI y Copy): Cada pantalla debe ser visual y textualmente idéntica a Figma. Corrige los errores actuales: textos incorrectos, vistas pegadas al borde superior, desorden visual y problemas de espaciado/alineación. Usa únicamente las imágenes/assets ya existentes en el proyecto."
- S2 "Clean Code y Arquitectura: Mantén el proyecto ordenado, modular y escalable (principios SOLID/DRY, separación clara de carpetas y componentes reutilizables)."
- S3 Catalog per §4.2, §5, §5.1 and §5.3: 3 dimensions, 18 factors, 61 subfactors, CatalogVersion 1 "Catálogo base de la tesis" (publicada) and 2 "Actualización 2020 a 2025" (activa), 36 FactorVersion, exactly 6 factors with different IS between v1 and v2, loaded by `python manage.py cargar_catalogo` inside a transaction.
- S4 "toda la matemática vive en evaluations/services.py como funciones puras" (§4.1-§4.10), covered by every case of §10.1.
- S5 Remaining screens and flows per §6 and §7 (D01, D02, E1-E5, H01-H03, C01, X01, AD01, U01/U02, O01/O02, M01-M03, I01, G01-G03).

## Tasks
- T0 [done] Scaffold and register apps catalog/evaluations/exports. Route: orchestrator inline.
- T1 [in progress] Phase 1 UI fix: tokens, auth layout, A01-A03 copy, base templates T01/T02. S1, S2. Route: orchestrator. Surface: templates/**, static/**, apps/accounts/**.
- T2 [handoff odd/handoff/T2-catalog.md → session 01a1d178-4969-715f-8948-2cc5bfd5dd1e] Catalog app. S2, S3. Surface: apps/catalog/**.
- T3 [handoff odd/handoff/T3-services.md → session 01a1d178-8724-700f-82ae-bf8e79b285e1] Pure calculation services and tests. S2, S4. Surface: apps/evaluations/services.py, apps/evaluations/tests/**.
- T4 [pending T2,T3] Evaluation models + D02, E1-E5 with HTMX autosave. S5.
- T5 [pending T4] D01, H01-H03, duplicate, delete draft. S5.
- T6 [pending T4] C01 compare, X01 PDF/CSV export. S5.
- T7 [pending T2] Admin AD01, U01/U02, O01/O02, M01-M03. S5.
- T8 [pending] I01 help, G01-G03 error/empty states. S1, S5.

## Log
- L1 (user, verbatim summary of original request) "Vamos a corregir y completar el proyecto GIOS Pro ... refactorizar lo actual y terminar las pantallas faltantes." Rules: S1, S2, token saving, explain before coding each module.
- L2 (user) "ordenales, tu eres el orchestador" — orchestrator dispatches T2 and T3 to the two peer sessions.
- L3 Figma not reachable (JS-rendered, no API token/MCP). T1 visual fidelity blocked until user provides access or PNG exports in doc/figma/.
- L4 (user) "ya exporté cada frame para q puedas verlo en la carpeta de doc/design/". 3 canvases split into 29 frames at 1x in doc/design/frames/ (auth frames renamed A01/A02-*/A03). Cross-session messaging unavailable: handoffs written to odd/handoff/.
