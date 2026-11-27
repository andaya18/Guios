# GUIOS PRO
Sistema web de evaluación GUIOS con Python 3.12, Django 5.x y SQLite local.

## Comandos (PowerShell, desde la raíz)
- Crear entorno: `py -3.12 -m venv .venv`
- Instalar: `.venv\Scripts\python.exe -m pip install -r requirements\development.txt`
- Ejecutar: `.venv\Scripts\python.exe manage.py runserver`
- Pruebas completas: `.venv\Scripts\python.exe manage.py test`
- Pruebas de accounts: `.venv\Scripts\python.exe manage.py test apps.accounts`
- Lint/build: no configurados todavía.

## Estructura
- `guios/`: configuración, URLs y entrada ASGI/WSGI.
- `apps/accounts/`: usuarios, organizaciones, registro y autenticación.
- `catalog/`, `evaluations/`, `exports/`: módulos de dominio previstos.
- `templates/` y `static/`: interfaz HTML y tokens visuales.
- `doc/`: especificación funcional y referencia de Figma.

## Reglas
- Mantener las reglas matemáticas aisladas en servicios de dominio.
- Ejecutar las pruebas del código tocado antes de declarar terminado.
- No leer archivos `.env` ni archivos de credenciales.
- No agregar dependencias sin solicitarlo y fijar sus versiones.
- Mantener idioma español, nombres semánticos y filtros por organización.

La fuente de verdad funcional es `doc/GUIOS_PRO_Gabriela.pdf` y el diseño visual es el archivo Figma enlazado allí.
