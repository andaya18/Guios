# GUIOS PRO

Sistema web para evaluar la idoneidad de software con la guía GUIOS (Rea Sánchez, 2022), desarrollado
con Python 3.12 y Django 5.1.

## Presentación: todo local

La aplicación y su base de datos SQLite (`db.sqlite3`) se ejecutan en tu computador. No requiere hosting ni
credenciales de base de datos. Para enviar códigos y consultar Gemini, cada persona configura su propia cuenta
SMTP y clave de API; esas dos funciones requieren internet.

### Recorrido rápido

1. Clona el repositorio e instala las dependencias.
2. Crea `.env` copiando `.env.example`; agrega tus credenciales SMTP y Gemini.
3. Migra la base local, carga el catálogo y crea las cuentas de administrador y decisor.
4. Inicia Django localmente y abre `http://127.0.0.1:8000/`.

> **No compartas ni subas `.env`.** Puede contener contraseñas de las cuentas de prueba.
> Cada instalación debe configurar su propio archivo; Git ignora `.env`.

## 1. Requisitos

| Requisito | Uso |
|---|---|
| Python 3.12 | Ejecutar Django |
| Git | Clonar el proyecto |
| PowerShell | Ejecutar los comandos de esta guía en Windows |

Para el correo real necesitas una cuenta con acceso SMTP; para las sugerencias de IA necesitas una clave de
Gemini. Cada persona debe usar sus propias credenciales en `.env`.

## 2. Clonar e instalar

En PowerShell, desde la carpeta donde guardarás el proyecto. El comando solo crea `.env` si todavía no existe;
si ya tienes uno, se conserva y lo editas:

```powershell
git clone https://github.com/andaya18/Guios.git
Set-Location Guios
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\development.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Si `py -3.12` no se reconoce, instala Python 3.12 y vuelve a abrir PowerShell. Mantén el archivo `.env`
junto a `manage.py`; Django lo lee al arrancar. Completa `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`DEFAULT_FROM_EMAIL` y `AI_API_KEY` con tus propios datos.

## 3. Configurar `.env`

### Base local

La base de datos ya está configurada para SQLite y se crea como `db.sqlite3` junto a `manage.py`. No agregues
variables de conexión a bases de datos. Si `.env` ya existía, elimina cualquier URL o credencial de base de
datos que haya quedado allí. Reinicia Django después de editar `.env`.

Confirma que Django seleccionó SQLite:

```powershell
.\.venv\Scripts\python.exe manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
```

Debe mostrar `django.db.backends.sqlite3`.

### Correo de verificación

En `.env.example` ya está el ejemplo para Gmail. Reemplaza usuario, contraseña de aplicación y remitente por
tus propios valores. No uses la contraseña normal de tu cuenta de correo:

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=tu-cuenta@gmail.com
EMAIL_HOST_PASSWORD=tu-contrasena-de-aplicacion
DEFAULT_FROM_EMAIL=GUIOS PRO <tu-cuenta@gmail.com>
```

El remitente debe estar autorizado por tu proveedor. Si usas otro servicio SMTP, reemplaza el host, puerto y
configuración TLS por los que te indique. Sin credenciales SMTP válidas, el correo no se enviará.

### Sugerencias de IA

En `.env.example`, reemplaza `AI_API_KEY` por tu propia clave de Gemini:

```ini
AI_PROVIDER=gemini
AI_API_KEY=tu-clave-de-gemini
AI_MODEL=gemini-3-flash-preview
AI_GROUNDING=url
```

La app necesita conexión a internet para consultar Gemini. Sin clave, sin conexión o si se alcanza la cuota,
se usan los valores de respaldo de la Tabla 17.

## 4. Preparar la base y crear cuentas

Ejecuta desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Carga el catálogo metodológico y la literatura inicial:

```powershell
.\.venv\Scripts\python.exe manage.py cargar_catalogo
.\.venv\Scripts\python.exe manage.py cargar_literatura
```

Crear el administrador:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

El decisor se registra desde **Crear cuenta** en la aplicación. Su código de verificación llegará al correo
configurado en SMTP.

## 5. Ejecutar la presentación

Inicia la aplicación local:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Inicia sesión en `/acceso/` con la cuenta de
administrador o decisor. Para completar un registro nuevo, revisa el correo indicado en el formulario y usa
el código de seis dígitos que envía Django mediante SMTP.

Para que el docente pueda abrir la presentación desde otro computador, ambos equipos necesitarían una red
accesible o un servidor web; esta guía deliberadamente no configura ese despliegue.

## 6. Pruebas automáticas

La suite debe ejecutarse contra SQLite, nunca contra una base de datos remota. En PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

Las pruebas usan SQLite y no envían correos reales ni consultan Gemini.

## 7. Problemas frecuentes

| Síntoma | Qué revisar |
|---|---|
| Django no selecciona SQLite | Confirma que el proyecto usa el `settings.py` incluido y reinicia Django. |
| `no such table` o tabla inexistente | Ejecuta `migrate` y carga el catálogo y la literatura en la base local. |
| No llega el código de registro | Revisa el host, puerto, usuario, contraseña y remitente SMTP; el proveedor debe permitir el envío. |
| Se muestran valores de respaldo | Revisa la clave Gemini, la conexión a internet y la cuota disponible. |
| Inicio de sesión rechazado | Comprueba que usas el correo y la contraseña de la cuenta creada en `db.sqlite3`. |

Al cambiar `.env`, detén y vuelve a iniciar `runserver` para que Django lea la nueva configuración.
