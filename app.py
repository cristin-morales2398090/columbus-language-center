import csv, io, json, os, re, secrets, smtplib, sqlite3, threading, time
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from hmac import compare_digest
from flask import (Flask, Response, render_template, request, redirect, url_for,
                   session, flash, g, abort)
from werkzeug.middleware.proxy_fix import ProxyFix
from questions import QUESTIONS, LEVELS, START_LEVEL, grade

IS_LOCAL = __name__ == "__main__"  # True solo con `python app.py`


def required_env(name, dev_default):
    """En producción (gunicorn) la variable es obligatoria; en local se permite un valor de prueba."""
    v = os.environ.get(name)
    if v:
        return v
    if IS_LOCAL:
        return dev_default
    raise RuntimeError(f"Falta la variable de entorno {name}. Defínela antes de iniciar la app.")


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # IP real detrás del proxy de Render
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # evita que el navegador guarde estilos viejos
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=not IS_LOCAL)
app.secret_key = required_env("SECRET_KEY", "clave-solo-para-desarrollo-local")
ADMIN_PASSWORD = required_env("ADMIN_PASSWORD", "cambiar123")
DB = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "academy.db"))
os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)

SITE = {  # Datos del negocio
    "teacher": "Columbus Language Center",
    "brand": "Columbus Language Center",
    "address": "349 Hamilton Ave., Trenton, NJ",
    "schedule": "Mañana, tarde y noche · horarios a convenir",
    "map_embed": "https://www.google.com/maps?q=349+Hamilton+Ave,+Trenton,+NJ&output=embed",
    "whatsapp": "16096433272",
    "phone": "609-643-3272",
    "email": os.environ.get("CONTACT_EMAIL", ""),  # si está vacío no se muestra en el sitio
    "street": "349 Hamilton Ave.", "city": "Trenton", "region": "NJ",
}

LEVEL_INFO = {
    START_LEVEL: "Estás empezando, ¡y eso es genial! Arrancamos desde cero con bases sólidas.",
    "Level 1": "Puedes entender y usar frases muy básicas. Vamos a darte vocabulario y confianza.",
    "Level 2": "Te comunicas en situaciones cotidianas sencillas. Toca ampliar y conectar ideas.",
    "Grammar & Writing": "Te defiendes en la mayoría de situaciones de viaje y trabajo. Hora de ganar fluidez.",
    "Level 3": "Hablas con soltura y espontaneidad. Afinamos precisión, matices y vocabulario avanzado.",
    "Level 4": "Tu inglés es avanzado y flexible. Trabajamos nivel académico y profesional de alto nivel.",
}

# Equivalencia de cada nivel con el MCER (escala de Cambridge/IELTS), solo informativa
LEVEL_CEFR = {"Level 1": "A1", "Level 2": "A2", "Grammar & Writing": "B1", "Level 3": "B2", "Level 4": "C1"}

LEVEL_DESC = [
    ("Level 1", "Principiante: entiendes y usas expresiones muy básicas, te presentas y haces preguntas sencillas."),
    ("Level 2", "Básico: te comunicas en situaciones cotidianas como compras, rutinas y direcciones."),
    ("Grammar & Writing", "Intermedio: te defiendes en viajes y trabajo, y puedes contar experiencias y opiniones."),
    ("Level 3", "Intermedio alto: conversas con fluidez y entiendes textos complejos sobre temas variados."),
    ("Level 4", "Avanzado: te expresas con soltura y precisión en contextos académicos y profesionales."),
]

COURSES = [
    ("Inglés desde cero", "Level 1", "Saludos, rutinas y lo esencial para hablar desde la primera clase."),
    ("Conversación diaria", "Level 2 – Grammar & Writing", "Practica situaciones reales: viajes, trabajo, redes y amigos."),
    ("Inglés para el trabajo", "Grammar & Writing – Level 3", "Entrevistas, reuniones, correos y presentaciones en inglés."),
    ("Preparación de exámenes", "Level 3 – Level 4", "IELTS, TOEFL y Cambridge con simulacros y feedback."),
]

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS results(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT,
            level TEXT, score INTEGER, total INTEGER, detail TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS leads(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT,
            schedule TEXT, message TEXT, created_at TEXT)""")
        migrate_levels(c)

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("csrf", "")
        sent = request.form.get("csrf_token", "")
        if not expected or not compare_digest(sent.encode(), expected.encode()):
            abort(400)


@app.errorhandler(400)
def bad_request(_):
    flash("La sesión expiró. Por favor inténtalo de nuevo.")
    return redirect(url_for("index"))


def notify(subject, body):
    """Aviso por correo al dueño (opcional). Se activa con SMTP_HOST y NOTIFY_EMAIL."""
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("NOTIFY_EMAIL")
    if not (host and to):
        return
    subject = re.sub(r"\s+", " ", subject)[:150]

    def send():
        try:
            user = os.environ.get("SMTP_USER", "")
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = subject, user or to, to
            msg.set_content(body)
            with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=15) as smtp:
                smtp.starttls()
                if user:
                    smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
        except Exception as e:  # el aviso nunca debe romper la página
            app.logger.warning("No se pudo enviar el aviso por correo: %s", e)
    threading.Thread(target=send, daemon=True).start()


_fails = {}  # ip -> [intentos, primer_intento]  (límite de intentos del login)
MAX_FAILS, LOCK_SECONDS = 5, 900


def is_locked(ip):
    f = _fails.get(ip)
    if f and time.time() - f[1] > LOCK_SECONDS:
        _fails.pop(ip, None)
        return False
    return bool(f and f[0] >= MAX_FAILS)


def register_fail(ip):
    f = _fails.setdefault(ip, [0, time.time()])
    f[0] += 1


def _safe_cell(v):
    v = "" if v is None else str(v)
    if v[:1] in ("=", "@", "\t", "\r") or (v[:1] in ("+", "-") and not re.fullmatch(r"[+\-]?[\d\s().\-]+", v)):
        return "'" + v  # evita fórmulas maliciosas al abrir el CSV en Excel
    return v


def csv_response(rows, cols, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([_safe_cell(r[c]) for c in cols])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


OLD_LEVELS = {"Pre-A1": START_LEVEL, "A1": "Level 1", "A2": "Level 2", "B1": "Grammar & Writing",
              "B2": "Level 3", "C1": "Level 4"}


def migrate_levels(c):
    """Renombra los niveles guardados con los códigos antiguos (idempotente)."""
    for old, new in OLD_LEVELS.items():
        c.execute("UPDATE results SET level=? WHERE level=?", (new, old))
    for rid, detail in c.execute("SELECT id, detail FROM results").fetchall():
        try:
            d = json.loads(detail)
        except (TypeError, ValueError):
            continue
        if any(k in OLD_LEVELS for k in d):
            c.execute("UPDATE results SET detail=? WHERE id=?",
                      (json.dumps({OLD_LEVELS.get(k, k): v for k, v in d.items()}), rid))


@app.context_processor
def inject():
    def static_v(name):
        """URL de un archivo estático con versión (fecha de modificación) para romper la caché."""
        p = os.path.join(app.static_folder, name)
        v = int(os.path.getmtime(p)) if os.path.exists(p) else 0
        return url_for("static", filename=name, v=v)
    return {"site": SITE, "levels": LEVELS, "start_level": START_LEVEL, "level_cefr": LEVEL_CEFR, "static_v": static_v, "csrf_token": csrf_token}

@app.route("/")
def index():
    return render_template("index.html", courses=COURSES, level_desc=LEVEL_DESC)

@app.route("/reservar", methods=["POST"])
def book():
    f = request.form
    name, phone = f.get("name", "").strip()[:80], f.get("phone", "").strip()[:30]
    if f.get("website"):  # honeypot anti-spam
        return redirect(url_for("index"))
    if len(name) < 2 or len(re.sub(r"\D", "", phone)) < 7:
        flash("Escribe tu nombre y un número de WhatsApp válido para poder contactarte.")
        return redirect(url_for("index") + "#reserva")
    db().execute("INSERT INTO leads(name,phone,schedule,message,created_at) VALUES(?,?,?,?,?)",
                 (name, phone, f.get("schedule", "")[:30], f.get("message", "").strip()[:600],
                  datetime.now().strftime("%Y-%m-%d %H:%M")))
    db().commit()
    digits = re.sub(r"\D", "", phone)
    notify(f"Nueva solicitud de clase: {name}",
           f"Nombre: {name}\nWhatsApp: {phone}\nHorario: {f.get('schedule', '')}\n"
           f"Mensaje: {f.get('message', '').strip()[:600]}\n\nhttps://wa.me/{digits}")
    flash(f"¡Gracias, {name.split()[0]}! Recibimos tu solicitud y te escribiremos pronto.")
    return redirect(url_for("index") + "#reserva")

@app.route("/examen", methods=["GET", "POST"])
def start_test():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        if len(name) < 2 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash("Escribe tu nombre y un correo válido para continuar.")
            return render_template("start.html", name=name, email=email, phone="")
        session["student"] = {"name": name, "email": email,
                              "phone": request.form.get("phone", "").strip()}
        return redirect(url_for("take_test"))
    return render_template("start.html", name="", email="", phone="")

@app.route("/examen/preguntas")
def take_test():
    if "student" not in session:
        return redirect(url_for("start_test"))
    public = [{"id": q["id"], "text": q["text"], "options": q["options"]} for q in QUESTIONS]
    return render_template("test.html", questions=public)

@app.route("/examen/enviar", methods=["POST"])
def submit_test():
    s = session.get("student")
    if not s:
        return redirect(url_for("start_test"))
    answers = {}
    for q in QUESTIONS:
        v = request.form.get(f"q{q['id']}")
        answers[q["id"]] = int(v) if v and v.isdigit() else None
    level, score, total, per = grade(answers)
    cur = db().execute(
        "INSERT INTO results(name,email,phone,level,score,total,detail,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (s["name"], s["email"], s["phone"], level, score, total, json.dumps(per),
         datetime.now().strftime("%Y-%m-%d %H:%M")))
    db().commit()
    notify(f"Nuevo examen de nivel: {s['name']} ({level})",
           f"Nombre: {s['name']}\nCorreo: {s['email']}\nWhatsApp: {s['phone'] or '-'}\n"
           f"Nivel: {level}  ·  Puntaje: {score}/{total}")
    session.pop("student", None)
    session["last_result"] = cur.lastrowid
    return redirect(url_for("result", rid=cur.lastrowid))

@app.route("/resultado/<int:rid>")
def result(rid):
    if session.get("last_result") != rid and not session.get("admin"):
        abort(403)
    r = db().execute("SELECT * FROM results WHERE id=?", (rid,)).fetchone() or abort(404)
    return render_template("result.html", r=r, info=LEVEL_INFO[r["level"]],
                           per=json.loads(r["detail"]))

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **k)
    return w

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if is_locked(ip):
            flash("Demasiados intentos. Espera unos minutos e inténtalo de nuevo.")
            return render_template("login.html"), 429
        if compare_digest(request.form.get("password", "").encode(), ADMIN_PASSWORD.encode()):
            _fails.pop(ip, None)
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))
        register_fail(ip)
        flash("Contraseña incorrecta.")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    lv = request.args.get("nivel", "")
    q = "SELECT * FROM results" + (" WHERE level=?" if lv else "") + " ORDER BY id DESC"
    rows = db().execute(q, (lv,) if lv else ()).fetchall()
    counts = {r["level"]: r["n"] for r in db().execute(
        "SELECT level, COUNT(*) n FROM results GROUP BY level")}
    leads = db().execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return render_template("admin.html", rows=rows, counts=counts, sel=lv, leads=leads)

@app.route("/admin/exportar/solicitudes.csv")
@admin_required
def export_leads():
    rows = db().execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return csv_response(rows, ["created_at", "name", "phone", "schedule", "message"], "solicitudes.csv")


@app.route("/admin/exportar/resultados.csv")
@admin_required
def export_results():
    rows = db().execute("SELECT * FROM results ORDER BY id DESC").fetchall()
    return csv_response(rows, ["created_at", "name", "email", "phone", "level", "score", "total"], "resultados.csv")


@app.route("/robots.txt")
def robots():
    body = ("User-agent: *\nDisallow: /admin\nDisallow: /resultado/\n"
            f"Sitemap: {url_for('sitemap', _external=True)}\n")
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    urls = [url_for("index", _external=True), url_for("start_test", _external=True)]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    return Response(xml, mimetype="application/xml")


@app.route("/admin/solicitud/borrar/<int:lid>", methods=["POST"])
@admin_required
def admin_delete_lead(lid):
    db().execute("DELETE FROM leads WHERE id=?", (lid,))
    db().commit()
    return redirect(url_for("admin"))

@app.route("/admin/borrar/<int:rid>", methods=["POST"])
@admin_required
def admin_delete(rid):
    db().execute("DELETE FROM results WHERE id=?", (rid,))
    db().commit()
    return redirect(url_for("admin"))

init_db()
if __name__ == "__main__":
    app.run(debug=True)
