# GUIOS PRO

Sistema web para evaluar la idoneidad de software con la guía GUIOS (Rea Sánchez, 2022), desarrollado
con Python 3.12 y Django 5.1.

## Presentación: todo local

La aplicación se ejecuta en el computador desde el que se presenta y guarda los datos en SQLite (`db.sqlite3`).
No necesita hosting ni una base de datos remota. El envío de códigos usa el servidor SMTP que configures y las
sugerencias de IA usan Gemini; ambas integraciones requieren credenciales propias e internet.

### Recorrido rápido

1. Clona el repositorio e instala las dependencias.
2. Copia `.env.example` a `.env` y agrega tus propias credenciales de SMTP y Gemini.
3. Crea las tablas, carga los datos iniciales y prepara las cuentas de prueba.
4. Inicia Django localmente y abre `http://127.0.0.1:8000/`.

> **No compartas ni subas `.env`.** Puede contener contraseñas de las cuentas de prueba.
> Cada instalación debe configurar su propio archivo; Git ignora `.env`.

## 1. Requisitos

| Requisito | Uso |
|---|---|
| Python 3.12 | Ejecutar Django |
| Git | Clonar el proyecto |
| PowerShell | Ejecutar los comandos de esta guía en Windows |

No necesitas Render ni Neon. Para usar correo real necesitas una cuenta con acceso SMTP; para las sugerencias
de IA necesitas una clave de Gemini. Cada persona debe configurar sus propias credenciales en `.env`.

## 2. Clonar e instalar

En PowerShell, desde la carpeta donde guardarás el proyecto:

```powershell
git clone https://github.com/andaya18/Guios.git
Set-Location Guios
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\development.txt
Copy-Item .env.example .env
notepad .env
```

Si `py -3.12` no se reconoce, instala Python 3.12 y vuelve a abrir PowerShell. Mantén el archivo `.env`
junto a `manage.py`; Django lo lee al arrancar.

## 3. Configurar `.env`

### Base local

SQLite se guarda en `db.sqlite3` junto a `manage.py`. Asegúrate de que `.env` tenga esta configuración local:

```ini
DATABASE_URL=
DATABASE_URL_UNPOOLED=
DJANGO_USE_UNPOOLED_DATABASE=false
DB_ENGINE=django.db.backends.sqlite3
```

Si ya tenías una `.env` con una URL de PostgreSQL, bórrala o déjala vacía para usar SQLite. Reinicia Django
después de editar la configuración.

Confirma que Django seleccionó SQLite:

```powershell
.\.venv\Scripts\python.exe manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
```

Debe mostrar `django.db.backends.sqlite3`. Si no coincide, revisa `.env` y las variables de entorno de Windows:
las variables del proceso tienen prioridad.

### Correo de verificación

Configura en `.env` el servidor SMTP de tu proveedor de correo y completa estos campos con sus valores:

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=tu-correo-verificado@ejemplo.com
```

El remitente debe estar autorizado por el proveedor SMTP. Al registrar una cuenta, Django enviará el código a
ese correo. Si SMTP no está configurado correctamente, el envío fallará; no hay un fallback automático a la
terminal.

### Sugerencias de IA

Para habilitar Gemini, configura tu propia clave en `.env`:

```ini
AI_PROVIDER=gemini
AI_API_KEY=tu-clave-de-gemini
AI_MODEL=gemini-3-flash-preview
AI_GROUNDING=url
```

La app necesita conexión a internet para consultar Gemini. Sin clave, sin conexión o si se alcanza la cuota,
se usan los valores de respaldo de la Tabla 17.

### Cuentas de prueba

Agrega a tu `.env` correos y contraseñas propios para crear un administrador y un decisor. No uses las
credenciales de ejemplo en un archivo del repositorio:

```ini
GUIOS_TEST_ADMIN_EMAIL=
GUIOS_TEST_ADMIN_PASSWORD=
GUIOS_TEST_DECISOR_EMAIL=
GUIOS_TEST_DECISOR_PASSWORD=
# Opcionales:
GUIOS_TEST_ADMIN_FIRST_NAME=Administrador
GUIOS_TEST_DECISOR_FIRST_NAME=Decisor
```

Las contraseñas deben cumplir las validaciones del proyecto. El comando de provisión no cambia cuentas
existentes; si los correos ya existen con otra contraseña o rol, informa el conflicto.

## 4. Preparar la base local y las cuentas

Ejecuta estos comandos desde la raíz del proyecto. Django crea y actualiza `db.sqlite3` localmente:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Carga el catálogo metodológico y la literatura inicial:

```powershell
.\.venv\Scripts\python.exe manage.py cargar_catalogo
.\.venv\Scripts\python.exe manage.py cargar_literatura
```

Si configuraste las cuatro variables `GUIOS_TEST_*` en `.env`, crea las cuentas de demostración:

```powershell
.\.venv\Scripts\python.exe manage.py provision_test_users --confirm
```

El administrador recibe permisos de administración. El decisor se crea sin organización; asígnale una desde
la aplicación si necesitas demostrar funciones filtradas por organización. Si prefieres crear el administrador
manualmente, usa `python manage.py createsuperuser`; el decisor puede registrarse desde la página **Crear
cuenta**.

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
$names = @(
    "DATABASE_URL", "DATABASE_URL_UNPOOLED", "DJANGO_USE_UNPOOLED_DATABASE",
    "DB_ENGINE", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT",
    "DB_SSLMODE", "EMAIL_BACKEND", "AI_PROVIDER"
)
$previous = @{}
foreach ($name in $names) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    $env:DATABASE_URL = ""
    $env:DATABASE_URL_UNPOOLED = ""
    $env:DJANGO_USE_UNPOOLED_DATABASE = "false"
    $env:DB_ENGINE = "django.db.backends.sqlite3"
    $env:DB_NAME = Join-Path $PWD "db.sqlite3"
    $env:DB_USER = ""
    $env:DB_PASSWORD = ""
    $env:DB_HOST = ""
    $env:DB_PORT = ""
    $env:DB_SSLMODE = ""
    $env:EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    $env:AI_PROVIDER = "disabled"
    .\.venv\Scripts\python.exe manage.py test
} finally {
    foreach ($name in $names) {
        if ($null -eq $previous[$name]) {
            Remove-Item "Env:$name" -ErrorAction SilentlyContinue
        } else {
            Set-Item "Env:$name" $previous[$name]
        }
    }
}
```

Las pruebas no llaman a Gemini ni envían correos reales.

## 7. Problemas frecuentes

| Síntoma | Qué revisar |
|---|---|
| Django no selecciona SQLite | Revisa `.env` y las variables de entorno de Windows; deben coincidir con la configuración local de esta guía. |
| `no such table` o tabla inexistente | Ejecuta `migrate` y carga el catálogo y la literatura en la base local. |
| No llega el código de registro | Revisa el host, puerto, usuario, contraseña y remitente SMTP; el proveedor debe permitir el envío. |
| Se muestran valores de respaldo | Revisa la clave Gemini, la conexión a internet y la cuota disponible. |
| Inicio de sesión rechazado | Comprueba que usas el correo y la contraseña de la cuenta creada en `db.sqlite3`. |

Al cambiar `.env`, detén y vuelve a iniciar `runserver` para que Django lea la nueva configuración.
