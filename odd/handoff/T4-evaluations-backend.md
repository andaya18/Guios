# T4 · Evaluations backend (models, workflow, selectors)
Read AGENTS.md, then odd/tasks/guios-pro.md until ## Log (task T4, specs S2, S4, S5), then doc/GUIOS_PRO_Gabriela.pdf §4.4-§4.9, §5, §5.1, §5.2, §6.3-§6.7, §7.1 (D01 data table) and §10.2:
`py -I -c "import pypdf,sys;sys.stdout.reconfigure(encoding='utf-8');r=pypdf.PdfReader(sys.argv[1]);[print(p.extract_text()) for p in r.pages[5:18]+r.pages[21:22]]" doc/GUIOS_PRO_Gabriela.pdf`

Existing code you build on (read, do not rewrite):
- `apps/evaluations/services.py`: pure math (importancia_relativa, es_relevante, resumen_factor, clasificar_foda, recomendar, comparar, TEXTOS_RECOMENDACION, MENSAJE_EMPATE, formatear_pm). Reuse it; never duplicate a rule.
- `apps/catalog/models.py` (+ `cargar_catalogo`): CatalogVersion (status borrador/activa/publicada), Factor, Subfactor, FactorVersion.
- `apps/accounts/models.py`: Organization, User (role decisor/administrador, organization, area).
- `apps/evaluations/selectors.py`: a stub with `DashboardSummary`, `recommendation_breakdown`, `decisor_dashboard`, `history_count`. Keep those names and the dataclass fields; replace the stub bodies with real queries.

## Do (test-first for every rule: write failing tests, observe RED, then implement)
1. `models.py`: Software, Evaluation, EvaluationFactor, EvaluationSubfactor exactly as §5.1 (immutable finalized Evaluation in save()/delete()), plus `__str__` (Software: "LibreOffice 24.2" = name + " " + version), `Meta.ordering`, `get_absolute_url` (`/historial/<id>/`), migration, `admin.py`.
2. `workflow.py` (orchestration with the ORM; all math delegated to services.py; multi-table writes in `transaction.atomic`):
   - `register_software(organization, name, version, license_type)` (get or create; unique per org/name/version).
   - `create_evaluation(user, software)`: draft on the ACTIVE catalog version, 18 EvaluationFactor with IS and default scope copied (§6.3). Org of user/software/evaluation must match (§5.2).
   - `set_decision_importance(ev_factor, value)` and `set_scope(ev_factor, scope)`: validate 1..4 / interno|externo, recompute IR and is_relevant, touch evaluation.updated_at.
   - `start_stage_two(evaluation)`: requires 18 IDs and >=1 relevant ("Debes marcar al menos un factor como relevante para continuar." when none); creates missing EvaluationSubfactor rows for relevant factors (never deletes answers); current_step=2.
   - `answer_subfactor(evaluation, answer_id, value)`; `go_to_results(evaluation)` (current_step=3 only if nothing is missing).
   - `factor_progress(evaluation)` -> per relevant factor: answered, total, live PM (Decimal or None).
   - `results(evaluation)` -> per relevant factor scope, IR, PM, cumple, FODA; recommendation letter, its text, supporting factors (§4.7: problematic factors, or all relevant when A); works for drafts (not saved) and finalized (read saved values).
   - `missing_items(evaluation)` -> list of {"message": "Compatibilidad: faltan 3 subfactores", "url": "/evaluaciones/<id>/etapa-2/?factor=<factor_id>"} plus messages for missing IDs / no relevant factor (§4.8).
   - `finalize(evaluation)`: validate §4.8 (raise ValidationError with the missing list), save PM (4 decimals), FODA, recommendation, finished_at, status in one transaction. Irrelevant factors keep pm NULL and foda "".
   - `duplicate(evaluation, user)` (§6.5): new draft for `user`, same software, duplicated_from, same IDs/scopes/answers, ACTIVE version; if the version differs re-copy IS and recompute IR; return (new_evaluation, warning or None) with warning "Esta evaluación usa el catálogo versión X, distinto al de la original".
   - `delete_draft(evaluation, user)`: only own drafts.
   - `resume_label(evaluation)` -> "Etapa 1 de 3 · Factores relevantes · 12 de 18 factores", "Etapa 2 de 3 · Ponderación · Factor: Compatibilidad (5 de 8 subfactores)" (first relevant factor with unanswered subfactors, §7.1), "Etapa 3 de 3 · Resultado"; and `resume_progress(evaluation)` -> int percent = ((step-1) + fraction_of_current_stage) / 3 * 100.
3. `permissions.py`: `visible_evaluations(user)` (finalized of the user's organization + user's own drafts, §6.6); `get_editable_draft(user, pk)` raises PermissionDenied (403) when not the author's draft or finalized (§5.2, §6.4); `get_visible_evaluation(user, pk)` (404 for other orgs). Never show another organization's data.
4. `selectors.py`: implement `decisor_dashboard(user)` per the §7.1 table (finished_count = org finalized; drafts_count = own drafts; last = own most recent finalized by finished_at; resume = own draft with highest updated_at as an object with software, step_label, progress, updated_at, url to its current stage; recent = 4 most recent finalized of the org with select_related; by_letter = recommendation_breakdown(counts, finished_count)), `history_count(user)`, and `history(user, status=None, recommendation=None, query="")` (§6.6 filters, search by software name).

Tests in `apps/evaluations/tests/test_workflow.py` and `tests/test_selectors.py` (use `call_command("cargar_catalogo")` in setUpTestData). Cover §10.2 items that are backend-testable: Ana's draft hidden from Luis while her finalized one is visible; saving on a finalized evaluation is refused; one unanswered subfactor blocks finalize and names it; duplicate keeps answers and leaves the original intact; active version switch 2->1->2 keeps old evaluations' version; dashboard numbers match the DB.

## Allowed edit surfaces
- apps/evaluations/models.py
- apps/evaluations/admin.py
- apps/evaluations/migrations/**
- apps/evaluations/workflow.py
- apps/evaluations/permissions.py
- apps/evaluations/selectors.py
- apps/evaluations/tests/test_workflow.py
- apps/evaluations/tests/test_selectors.py
- apps/evaluations/tests/test_models.py

No views, urls, templates, or other apps. No commits, no .env. Run `.venv\Scripts\python.exe manage.py test apps.evaluations` and `.venv\Scripts\python.exe manage.py makemigrations --check`.
Report: changed files, RED evidence, GREEN tail, the public function signatures, S# covered.
