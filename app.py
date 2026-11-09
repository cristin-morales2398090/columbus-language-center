import json, os, re, sqlite3
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g, abort)
from questions import QUESTIONS, LEVELS, grade

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # evita que el navegador guarde estilos viejos
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cambiar123")
DB = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "academy.db"))
os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)

SITE = {  # Datos del negocio
    "teacher": "Columbus Language Center",
    "brand": "Columbus Language Center",
    "address": "Escribe aquí la dirección de la sede",
    "schedule": "Mañana, tarde y noche · horarios a convenir",
    "map_embed": "",  # opcional: pega aquí la URL de "Insertar un mapa" de Google Maps
    "whatsapp": "16096433272",
    "email": "profe@example.com",
}

LEVEL_INFO = {
    "Pre-A1": "Estás empezando, ¡y eso es genial! Arrancamos desde cero con bases sólidas.",
    "A1": "Puedes entender y usar frases muy básicas. Vamos a darte vocabulario y confianza.",
    "A2": "Te comunicas en situaciones cotidianas sencillas. Toca ampliar y conectar ideas.",
    "B1": "Te defiendes en la mayoría de situaciones de viaje y trabajo. Hora de ganar fluidez.",
    "B2": "Hablas con soltura y espontaneidad. Afinamos precisión, matices y vocabulario avanzado.",
    "C1": "Tu inglés es avanzado y flexible. Trabajamos nivel académico y profesional de alto nivel.",
}

LEVEL_DESC = [
    ("A1", "Principiante: entiendes y usas expresiones muy básicas, te presentas y haces preguntas sencillas."),
    ("A2", "Básico: te comunicas en situaciones cotidianas como compras, rutinas y direcciones."),
    ("B1", "Intermedio: te defiendes en viajes y trabajo, y puedes contar experiencias y opiniones."),
    ("B2", "Intermedio alto: conversas con fluidez y entiendes textos complejos sobre temas variados."),
    ("C1", "Avanzado: te expresas con soltura y precisión en contextos académicos y profesionales."),
]

COURSES = [
    ("Inglés desde cero", "A1", "Saludos, rutinas y lo esencial para hablar desde la primera clase."),
    ("Conversación diaria", "A2–B1", "Practica situaciones reales: viajes, trabajo, redes y amigos."),
    ("Inglés para el trabajo", "B1–B2", "Entrevistas, reuniones, correos y presentaciones en inglés."),
    ("Preparación de exámenes", "B2–C1", "IELTS, TOEFL y Cambridge con simulacros y feedback."),
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

@app.context_processor
def inject():
    def static_v(name):
        """URL de un archivo estático con versión (fecha de modificación) para romper la caché."""
        p = os.path.join(app.static_folder, name)
        v = int(os.path.getmtime(p)) if os.path.exists(p) else 0
        return url_for("static", filename=name, v=v)
    return {"site": SITE, "levels": LEVELS, "static_v": static_v}

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
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
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
