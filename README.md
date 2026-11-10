# Columbus Language Center – Web + examen de nivel (Flask)

## Correr en local
    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    export ADMIN_PASSWORD="tu-clave" SECRET_KEY="algo-largo-y-secreto"   # Windows: set VAR=valor
    python app.py        # abre http://127.0.0.1:5000

- Panel del profesor: /admin  (clave = ADMIN_PASSWORD) · botones para descargar CSV de respaldo
- Datos del negocio (nombre, WhatsApp, dirección): diccionario SITE en app.py
- Correo público: variable CONTACT_EMAIL (si no se define, no se muestra en el sitio)
- Avisos por correo (opcional): NOTIFY_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
- En producción SECRET_KEY y ADMIN_PASSWORD son obligatorias: sin ellas la app no arranca
- Preguntas: questions.py (agrega o cambia; el nivel se calcula solo)
- Niveles (de menor a mayor): Level 1, Level 2, Grammar & Writing, Level 3, Level 4 (lista LEVELS en questions.py). Si no se aprueba el primero: Pre-Level 1
- Nivel = el más alto aprobado (>=75% de aciertos) sin saltarse niveles
- Producción: usa gunicorn (gunicorn app:app) y cambia las variables de entorno

## Despliegue en Render
1. Sube la carpeta a un repositorio de GitHub.
2. En Render: New > Web Service > conecta el repositorio.
3. Build: `pip install -r requirements.txt` · Start: `gunicorn app:app`
4. Variables de entorno: `SECRET_KEY`, `ADMIN_PASSWORD`, `PYTHON_VERSION=3.12.3` (y opcionales: `CONTACT_EMAIL`, `NOTIFY_EMAIL` + `SMTP_*`)
5. Para conservar la base de datos entre reinicios (plan de pago): agrega un Disk montado en
   `/var/data` y la variable `DATABASE_PATH=/var/data/academy.db`

> **Importante:** en el plan gratuito de Render el disco se borra en cada reinicio o deploy.
> Usa el disco persistente o descarga los CSV del panel /admin con frecuencia.
