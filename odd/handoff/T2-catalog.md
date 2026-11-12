# T2 · Catalog app (worker session)
Read AGENTS.md, then odd/tasks/guios-pro.md until ## Log (task T2, specs S2-S3), then doc/GUIOS_PRO_Gabriela.pdf §4.2, §5, §5.1, §5.3:
`py -I -c "import pypdf,sys;sys.stdout.reconfigure(encoding='utf-8');r=pypdf.PdfReader(sys.argv[1]);[print(p.extract_text()) for p in r.pages[4:13]]" doc/GUIOS_PRO_Gabriela.pdf`

Do: in apps/catalog/ create models CatalogVersion, Dimension, Factor, Subfactor, FactorVersion exactly as §5.1 (+__str__, Meta ordering, admin.py), migration, and command `cargar_catalogo` (transactional, idempotent): 3 dimensions, 18 factors, 61 subfactors, versions 1 "Catálogo base de la tesis" (publicada) and 2 "Actualización 2020 a 2025" (activa), IS from §4.2, default scope interno/externo.
Data (dimension names, factor→dimension, 61 subfactor texts, default scopes) comes from doc/TESIS VRS.pdf, read as text with `py -I`. Store it in apps/catalog/data/ (JSON), not hardcoded.
Tests in apps/catalog/tests.py: 18 / 61 / 36 FactorVersion, subfactors per factor equals §4.2, exactly 6 factors with different IS, only one active version.
If the thesis lacks any subfactor text or default scope: STOP and report what is missing. Never invent.

Allowed edit surface: apps/catalog/** ONLY (app already registered). No commits, no .env.
Run: `.venv\Scripts\python.exe manage.py test apps.catalog`
Report: changed files, test output tail, S# covered, data gaps.
