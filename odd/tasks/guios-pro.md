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
- T2 [done b9436a1, 22 tests] Catalog app. S2, S3. Surface: apps/catalog/**.
- T3 [done, worker mwe1like-2-2mww, 34 tests GREEN] Pure calculation services and tests. S2, S4. Surface: apps/evaluations/services.py, apps/evaluations/tests/**.
- T4a [session 2: odd/handoff/T4-evaluations-backend.md] Evaluation models, workflow, permissions, selectors. S2, S4, S5.
- T4b [orchestrator, after T4a] Views/templates D02, E1-E5 with HTMX autosave. S1, S5.
- T5 [pending T4] D01, H01-H03, duplicate, delete draft. S5.
- T6 [pending T4] C01 compare, X01 PDF/CSV export. S5.
- T7 [session 3: odd/handoff/T7-admin.md] Admin AD01, U01/U02, O01/O02, M01-M03. S1, S2, S5.
- T8 [pending] I01 help, G01-G03 error/empty states. S1, S5.

## Log
- L1 (user, verbatim summary of original request) "Vamos a corregir y completar el proyecto GIOS Pro ... refactorizar lo actual y terminar las pantallas faltantes." Rules: S1, S2, token saving, explain before coding each module.
- L2 (user) "ordenales, tu eres el orchestador" — orchestrator dispatches T2 and T3 to the two peer sessions.
- L3 Figma not reachable (JS-rendered, no API token/MCP). T1 visual fidelity blocked until user provides access or PNG exports in doc/figma/.
- L4 (user) "ya exporté cada frame para q puedas verlo en la carpeta de doc/design/". 3 canvases split into 29 frames at 1x in doc/design/frames/ (auth frames renamed A01/A02-*/A03). Cross-session messaging unavailable: handoffs written to odd/handoff/.
- L5 (user) "hazlo y a darle con todo al proyecto, hay qcorregir al maximo para q sea perfectamente igual a lo q documentamos y al figma". Decision: add UppercaseDigitValidator so "Mín. 8 caracteres, una mayúscula y un número" is enforced.
- L6 T1 auth part done (24 accounts tests GREEN, visual diff vs frames). Found and fixed: verification attempts rolled back by @transaction.atomic (unlimited guesses), no AUTH_PASSWORD_VALIDATORS, no 60 s resend cooldown, reset form revealed accounts. Peer sessions never picked up T2/T3 -> reassigned to background workers mwe1lijy-1-59lz (T2) and mwe1like-2-2mww (T3).
- L7 Catalog data decisions (orchestrator, reversible, pending user confirmation): Soporte default scope = interno (thesis Table 5.4 marks it either; only concrete value is the §6.3 example); scopes identical in v1 and v2; Apoyo=1/Actitud=2 per §4.2; Documentación merged line split; names per §4.2. Commit 189b92e = T1 auth part. Open conflict: Figma AD01 shows registration approval queue, contradicting §6.1 automatic signup -> decide before T7.
- L8 (user) "continua y dame las tareas para las sesiones 2 y 3". T4 worker failed with no output (session limit) -> T4a to session 2, T7 to session 3. Commits: 189b92e T1-auth, b9436a1 T2, e910ac5 T3, e0049f6 shell+D01. apps/management scaffold mounted at /gestion/.
- L10 Figma vs guide conflicts resolved in favour of the guide (AGENTS.md: PDF is the functional source): PM shown with 2 decimals (Figma shows 1); E3 recommendation text uses RA/RB/RC verbatim (Figma shows free text). Templates E1-E3 + E4/E5 modals done against frames (365d54e + E2/E3 commit); views pending T4a.
- L9 (user) "haz el registro automático". Figma registration-approval queue (AD01 table, U01 Pendientes tab) is dropped; §6.1 automatic signup stands.
- L11 Pending refactor from GGA review: replace hardcoded paths (/comparar/, /evaluaciones/nueva/, /historial/, /ayuda/) with {% url %} once T4b/T5 views and url names exist.
- L12 (user) "hazlo": ReportLab authorized, pinned, added by session 2 in T6. Session 1 owns T4b. Session 3: drop pending signups, add published_by/authorized_at, fix 2 management tests.
