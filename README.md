# GUIOS PRO

Sistema web para evaluar la idoneidad de software con la guía GUIOS (Rea Sánchez, 2022).
Hecho con Python 3.12 y Django 5.1. Usa SQLite en desarrollo y PostgreSQL en producción.

**Contenido**

1. [Requisitos](#1-requisitos)
2. [Clonar e instalar](#2-clonar-e-instalar)
3. [Configurar el archivo .env](#3-configurar-el-archivo-env)
4. [Preparar la base de datos](#4-preparar-la-base-de-datos)
5. [Ejecutar y probar](#5-ejecutar-y-probar)
6. [Pruebas automáticas](#6-pruebas-automáticas)
7. [Problemas frecuentes](#7-problemas-frecuentes)
8. [Despliegue en Render + Neon](#8-despliegue-en-render--neon)

> **Regla de oro:** el archivo `.env` tiene tus contraseñas y tu clave de IA. **Nunca** lo subas a Git
> (ya está en `.gitignore`). Cada integrante usa el suyo.

---

## 1. Requisitos

| Necesitas | Para qué |
|---|---|
| [Python 3.12](https://www.python.org/downloads/) | Ejecutar el proyecto (marca "Add Python to PATH" al instalar). |
| [Git](https://git-scm.com/downloads) | Clonar el repositorio. |
| Una cuenta de Gmail con verificación en 2 pasos | Enviar el código de verificación por correo. |
| Una clave de Gemini ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) | Calcular la importancia sugerida con IA. Es gratuita. |

El correo y la IA son opcionales para empezar: sin ellos el sistema funciona igual (ver sección 3).

## 2. Clonar e instalar

Los comandos son para **PowerShell en Windows**, desde la carpeta donde quieras el proyecto.

```powershell
git clone https://github.com/andaya18/Guios.git
cd Guios
git switch feat/fidelidad-figma   # rama con el sistema completo (omítelo si ya está en main)

py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements\development.txt
```

Si PowerShell no deja activar el entorno ("la ejecución de scripts está deshabilitada"), ejecuta una vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentarlo.

## 3. Configurar el archivo .env

Copia la plantilla y edita la copia:

```powershell
Copy-Item .env.example .env
notepad .env
```

El sistema lee `.env` al arrancar. **Después de editarlo, reinicia el servidor.**

### 3.1 Correo para el código de verificación (Gmail)

Sin esta configuración el código **no llega por correo**: se imprime en la terminal donde corre el servidor
(sirve para probar). Para enviarlo de verdad:

1. Entra a tu cuenta de Google → **Seguridad** → activa la **Verificación en 2 pasos**.
2. Abre [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) y crea una
   **contraseña de aplicación** (nombre: "GUIOS PRO"). Son 16 letras: cópialas **sin espacios**.
   No es la contraseña de tu cuenta.
3. En `.env`, reemplaza la línea `EMAIL_BACKEND=...console...` y completa:

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=tu_cuenta@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
DEFAULT_FROM_EMAIL=GUIOS PRO <tu_cuenta@gmail.com>
```

`EMAIL_HOST_USER` y `DEFAULT_FROM_EMAIL` deben ser **la misma cuenta** que generó la contraseña de aplicación.
Si tu correo institucional no permite contraseñas de aplicación, usa un Gmail personal.

### 3.2 IA de la importancia sugerida (Gemini)

```ini
AI_PROVIDER=gemini
AI_API_KEY=tu_clave_de_gemini
AI_MODEL=gemini-3-flash-preview
```

Sin clave, el sistema usa los valores de respaldo del docente (Tabla 17) y lo indica en pantalla.

## 4. Preparar la base de datos

Se hace una sola vez (y otra vez cuando haya migraciones nuevas):

```powershell
python manage.py migrate
python manage.py cargar_catalogo
python manage.py cargar_literatura
python manage.py createsuperuser
```

`createsuperuser` pide **correo y contraseña** (en este sistema el correo es el usuario) y crea la cuenta con
rol **Administrador**. Los decisores no se crean aquí: se registran solos en la página (sección 5).

Opcional, para calcular ya la importancia sugerida con IA (también hay un botón en la pantalla):

```powershell
python manage.py calcular_importancia_sugerida
```

El plan gratuito de Gemini limita las llamadas por minuto; el comando espera y continúa solo, y lo ya
verificado queda guardado.

## 5. Ejecutar y probar

```powershell
python manage.py runserver
```

Abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

**Probar el registro con código de verificación (decisor)**

1. Ve a **Crear cuenta** (`/registro/`) con un correo **institucional** (Gmail y Hotmail se rechazan en el registro).
2. La contraseña debe tener al menos 8 caracteres, una mayúscula y un número, y no parecerse a tu nombre.
3. Llega un correo con el código de 6 dígitos (o aparece en la terminal si no configuraste Gmail).
4. Escribe el código en las 6 casillas. Vence en 10 minutos y tiene 5 intentos; puedes reenviarlo cada 60 s.
5. Si eres el primero de tu dominio, registra tu organización. Luego entras al **Panel de inicio**.

**Probar como administrador**

1. Entra en `/acceso/` con el correo y la contraseña del paso `createsuperuser`.
2. En **Configuración** (tu nombre, abajo a la izquierda):
   - verifica que "Modo de envío" diga **SMTP**;
   - envíate un **correo de prueba**;
   - personaliza el **mensaje del código de verificación** (variables `{nombre}`, `{codigo}`, `{minutos}`).
3. En **Catálogo metodológico → Importancia sugerida** revisa el cálculo con IA y sus fuentes.

## 6. Pruebas automáticas

```powershell
python manage.py test
```

Tardan unos 3 minutos. Nunca llaman a Gemini ni envían correos reales.

## 7. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| "No pudimos enviar el código de verificación" o "Connection unexpectedly closed" | Gmail rechazó la contraseña. Genera una nueva **contraseña de aplicación** con la misma cuenta de `EMAIL_HOST_USER`, cópiala sin espacios y reinicia el servidor. |
| Configuración dice "No configurado" | El servidor no leyó `.env`: debe estar junto a `manage.py`, llamarse exactamente `.env` (no `.env.txt`) y el servidor debe reiniciarse. |
| La importancia sugerida muestra "Valores de respaldo" | Sin clave de IA, o cuota de Gemini agotada. Espera un minuto y pulsa **Recalcular ahora**. |
| "Correo o contraseña incorrectos" | Revisa el correo exacto. Para cambiar la contraseña: `python manage.py changepassword correo@dominio`. |
| `no such table` | Faltan migraciones: `python manage.py migrate`. |

---

## 8. Despliegue en Render + Neon

Render ejecuta la aplicación y Neon guarda la base PostgreSQL. Ambos tienen plan gratuito.
No uses la base PostgreSQL gratuita de Render: se elimina a los 30 días.

### 8.1 Base de datos en Neon

1. Crea una cuenta en [neon.tech](https://neon.tech) y un proyecto (región cercana, por ejemplo `us-east-1`).
2. En **Connection details** copia: host, nombre de la base, usuario y contraseña.

### 8.2 Servicio web en Render

1. Crea una cuenta en [render.com](https://render.com) y conecta tu GitHub.
2. **New → Web Service** → elige el repositorio `andaya18/Guios` y la rama que se va a publicar.
3. Configura:

| Campo | Valor |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements/production.txt && python manage.py collectstatic --noinput && DJANGO_USE_UNPOOLED_DATABASE=true python manage.py migrate && python manage.py cargar_catalogo && python manage.py cargar_literatura` |
| Start Command | `gunicorn guios.wsgi:application` |

4. En **Environment** agrega las variables (el `.env` no se sube; aquí van los valores reales):

| Variable | Valor |
|---|---|
| `PYTHON_VERSION` | `3.12.4` |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Una clave larga y aleatoria. Genérala con `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | `tu-servicio.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://tu-servicio.onrender.com` |
| `DATABASE_URL` | URL pooled de Neon para las peticiones de la aplicación |
| `DATABASE_URL_UNPOOLED` | URL directa de Neon para ejecutar migraciones |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Igual que en la sección 3.1 |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` | Igual que en la sección 3.2 |
| `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | Correo y contraseña del primer administrador |

Para migrar manualmente desde PowerShell, usa la URL directa durante ese comando:

```powershell
$env:DJANGO_USE_UNPOOLED_DATABASE = "true"
try {
    .\.venv\Scripts\python.exe manage.py migrate
} finally {
    Remove-Item Env:DJANGO_USE_UNPOOLED_DATABASE -ErrorAction SilentlyContinue
}
```

5. Pulsa **Create Web Service**. Cuando el log diga *Your service is live*, abre `https://tu-servicio.onrender.com`.

### 8.3 Después del primer despliegue

- Entra con el administrador de `DJANGO_SUPERUSER_EMAIL` y, en **Configuración**, envía un correo de prueba.
- En **Importancia sugerida** pulsa **Recalcular ahora** para el cálculo con IA.
- Cada `git push` a la rama conectada vuelve a desplegar. Las migraciones y las cargas de datos son seguras
  de repetir: no duplican ni borran información.
- El plan gratuito de Render "duerme" el servicio tras 15 minutos sin uso; la primera visita tarda unos segundos.

### 8.4 Subir cambios

```powershell
git add .
git commit -m "feat: descripción del cambio"
git push origin nombre-de-tu-rama
```

Luego abre un Pull Request en GitHub para que el equipo lo revise antes de unirlo a `main`.
