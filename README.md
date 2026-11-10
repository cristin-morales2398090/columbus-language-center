# Columbus Language Center – Web + examen de nivel (Flask)

## Correr en local
    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    export ADMIN_PASSWORD="tu-clave" SECRET_KEY="algo-largo-y-secreto"   # Windows: set VAR=valor
    python app.py        # abre http://127.0.0.1:5000

- Panel del profesor: /admin  (clave = ADMIN_PASSWORD)
- Datos del negocio (nombre, WhatsApp, correo): diccionario SITE en app.py
- Preguntas: questions.py (agrega o cambia; el nivel se calcula solo; niveles: Level 1, Level 2, Grammar & Writing, Level 3, Level 4)
- Nivel = el más alto aprobado (>=75% de aciertos) sin saltarse niveles
- Producción: usa gunicorn (gunicorn app:app) y cambia las variables de entorno

## Despliegue en Render
1. Sube la carpeta a un repositorio de GitHub.
2. En Render: New > Web Service > conecta el repositorio.
3. Build: `pip install -r requirements.txt` · Start: `gunicorn app:app`
4. Variables de entorno: `SECRET_KEY`, `ADMIN_PASSWORD`, `PYTHON_VERSION=3.12.3`
5. Para conservar la base de datos entre reinicios (plan de pago): agrega un Disk montado en
   `/var/data` y la variable `DATABASE_PATH=/var/data/academy.db`
