# T7 · Administrator area (AD01, U01/U02, O01/O02, M01-M03)
Read AGENTS.md, then odd/tasks/guios-pro.md until ## Log (task T7, specs S1, S2, S5), then doc/GUIOS_PRO_Gabriela.pdf §1, §3, §5.2, §6.9, §7:
`py -I -c "import pypdf,sys;sys.stdout.reconfigure(encoding='utf-8');r=pypdf.PdfReader(sys.argv[1]);[print(p.extract_text()) for p in r.pages[1:4]+r.pages[11:12]+r.pages[15:18]]" doc/GUIOS_PRO_Gabriela.pdf`

Visual source (must match layout and copy exactly): doc/design/frames/AD01-panel-admin.png, U01-usuarios.png, U01-usuarios-zoom.png, O01-organizaciones.png, O02-modal-organizacion.png, M01-catalogo-editar.png, M02-revisar-publicar.png, M03-versiones.png. The functional PDF wins when Figma contradicts it.

## Already in place (read, do not edit)
- `apps/management/` scaffold, registered in settings and mounted at `/gestion/` (app_name "management").
- `templates/base_admin.html` (sidebar T02 + top bar). Extend it; set `{% block topbar_title %}` and, when the frame shows a breadcrumb, `{% block topbar_subtitle %}`.
- Shared CSS components in `static/css/components.css`: `.panel`, `.panel__header`, `.panel__title`, `.stat`, `.pill--success|draft|neutral|danger|dark`, `.table`, `.table-wrap`, `.button--primary|secondary|dark|link`, `.field` (+ `templates/components/field.html`), `.modal`, `.empty` (+ `components/empty.html`), `.alert`, icons via `{% include "components/icon.html" with name="users" %}`. Tokens in `static/css/tokens.css`. Template filters in `apps/core/templatetags/ui.py` (`{% load ui %}`: `short_date`, `today_long`).
- Models: `apps/accounts/models.py` (Organization, User role decisor/administrador), `apps/catalog/models.py` (CatalogVersion borrador/activa/publicada, Factor, Subfactor, FactorVersion, `cargar_catalogo` command). Catalog data loader logic: `apps/catalog/services.py`.

## Do (test-first for every rule: failing test, RED, then implement)
1. Access: every `/gestion/` view requires role administrador; a decisor gets 403 (§3, §10.2 "Entrar como decisor a /gestion/: pantalla 403"). One reusable mixin/decorator in `apps/management/permissions.py`.
2. AD01 `/gestion/`: user counts (active / deactivated), catalog state (active version, factors 18, subfactors 61, number of changes in the draft version if any), organizations (active / deactivated, públicas/privadas). DECIDED (user, L9): signup is automatic per §6.1. Do NOT build "Solicitudes de registro pendientes", the "por atender" badge, approve/reject actions, nor a "Pendientes" tab in U01. The AD01 bottom area stays out; U01 tabs are only Activos and Desactivados.
3. U01 `/gestion/usuarios/` list with search and active/deactivated tabs; U02 `/gestion/usuarios/nuevo/` and `/gestion/usuarios/<id>/`: create (any role), edit, deactivate. Never delete users. Administrators have no organization; decisors must have one.
4. O01 `/gestion/organizaciones/` list with tabs; O02 (modal in the frame; a page or modal is fine) create/edit name and sector, deactivate; domain not editable once it has users (§6.9).
5. M03 `/gestion/catalogo/` versions with status; set any published version as active (exactly one active, §5.2); compare `/gestion/catalogo/comparar/?a=1&b=2` factor by factor (IS and scope) highlighting the 6 differences between v1 and v2.
6. M01 `/gestion/catalogo/<version>/`: create a new draft version copying the active one; edit IS (1-4) and default scope per factor of a DRAFT only; no adding/removing factors or subfactors.
7. M02 `/gestion/catalogo/<version>/publicar/`: show changes vs the active version, require justification and authorizing name, publish (previous active becomes publicada, new one activa, published_at set) in one transaction. Existing evaluations are never altered.
Put rules in `apps/management/services.py` (or reuse catalog services); views stay thin. Page CSS only in `static/css/pages/management.css`.

## Allowed edit surfaces
- apps/management/**
- templates/management/**
- static/css/pages/management.css

Do not edit components.css, base templates, other apps, settings or urls outside apps/management. If you need a new shared component, write it in management.css and report it. No commits, no .env.

## Verify
`.venv\Scripts\python.exe manage.py test apps.management` and the full `.venv\Scripts\python.exe manage.py test`. Visual check: run the server, log in as an administrator (create one with `createsuperuser`, then set role administrador in /admin/) and compare each screen with its frame at 1440x900.
Report: changed files, RED evidence, GREEN tail, screens done vs frame, new components added, S# covered.
