# T3 · Pure calculation services (worker session)
Read AGENTS.md, then odd/tasks/guios-pro.md until ## Log (task T3, specs S2, S4), then doc/GUIOS_PRO_Gabriela.pdf §4.1-§4.10 and §10.1:
`py -I -c "import pypdf,sys;sys.stdout.reconfigure(encoding='utf-8');r=pypdf.PdfReader(sys.argv[1]);[print(p.extract_text()) for p in r.pages[4:9]+r.pages[21:22]]" doc/GUIOS_PRO_Gabriela.pdf`

Do test-first (write failing tests, observe RED, then implement): apps/evaluations/services.py, pure functions, no ORM imports: ESCALA, MATRIZ, importancia_relativa, es_relevante, resumen_factor (integer rule suma >= 3*n, never rounded PM), clasificar_foda, recomendar, clave_comparacion, comparar; texts RA/RB/RC verbatim from §4.7; tie message "Las evaluaciones están empatadas: cualquiera de las alternativas puede adoptarse" (§4.9); helper formatting PM with 2 decimals and comma ("2,88"). Keep the Spanish names of §4.10.
Tests in apps/evaluations/tests/__init__.py + tests/test_services.py: every row of §10.1 exactly as written (PM shown 2,88 / 3,00) plus all 16 MATRIZ cells.

Allowed edit surface: apps/evaluations/services.py and apps/evaluations/tests/** ONLY. No models, no other apps, no commits, no .env.
Run: `.venv\Scripts\python.exe manage.py test apps.evaluations`
Report: changed files, RED evidence, GREEN output tail, S# covered.
