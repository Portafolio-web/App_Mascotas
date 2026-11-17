from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = os.environ.get("VERCEL") == "1"
DB_PATH = (
    os.path.join(tempfile.gettempdir(), "petfeeder.db")
    if IS_VERCEL
    else os.path.join(BASE_DIR, "petfeeder.db")
)

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "public", "static"),
    static_url_path="/static",
)
app.secret_key = os.environ.get("SECRET_KEY", "petfeeder-dev-secret")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    species TEXT NOT NULL DEFAULT 'perro',
    weight_kg REAL NOT NULL,
    stage TEXT NOT NULL,
    activity TEXT NOT NULL,
    meals_per_day INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    grams INTEGER NOT NULL,
    label TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS water (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    label TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    label TEXT,
    grams INTEGER,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS device (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    connected INTEGER NOT NULL DEFAULT 0,
    last_sync TEXT
);
CREATE TABLE IF NOT EXISTS membership (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active INTEGER NOT NULL DEFAULT 0,
    since TEXT
);
CREATE TABLE IF NOT EXISTS advice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'En revisión',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SPECIES = {"perro": "Perro", "gato": "Gato"}
STAGES = {"cachorro": "Cachorro", "joven": "Joven", "adulto": "Adulto", "senior": "Senior"}
ACTIVITIES = {"baja": "Actividad baja", "normal": "Actividad normal", "alta": "Actividad alta"}
STAGE_FACTORS = {
    "perro": {"cachorro": 2.2, "joven": 1.9, "adulto": 1.6, "senior": 1.4},
    "gato": {"cachorro": 2.5, "joven": 1.8, "adulto": 1.4, "senior": 1.2},
}
ACTIVITY_ADJ = {"baja": -0.15, "normal": 0.0, "alta": 0.2}

MEAL_TIMES = {
    1: ["08:00"],
    2: ["08:00", "20:00"],
    3: ["07:30", "13:00", "19:30"],
    4: ["07:00", "12:00", "17:00", "21:00"],
}
MEAL_LABELS = {
    1: ["Comida"],
    2: ["Desayuno", "Cena"],
    3: ["Desayuno", "Comida", "Cena"],
    4: ["Desayuno", "Almuerzo", "Comida", "Cena"],
}
DEFAULT_WATER = [("08:00", "Agua fresca"), ("14:00", "Agua fresca"), ("20:00", "Agua fresca")]

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

TUTORIALS = [
    {
        "id": "intro",
        "title": "Cómo introducir el comedero",
        "duration": "3 min",
        "level": "Básico",
        "desc": "Una transición tranquila para que tu mascota acepte el comedero automático.",
        "steps": [
            "Coloca el comedero en el lugar habitual donde come, sin encenderlo, durante un día.",
            "Sirve una porción pequeña a mano junto al comedero para crear una asociación positiva.",
            "Activa la primera dispensación y deja que tu mascota explore el sonido y la caída del alimento.",
            "Divide la ración diaria en varias dispensaciones durante la primera semana.",
        ],
    },
    {
        "id": "rutina",
        "title": "Rutina de comidas en 3 pasos",
        "duration": "4 min",
        "level": "Básico",
        "desc": "Horarios estables que reducen la ansiedad y mejoran la digestión.",
        "steps": [
            "Define dos o tres comidas a la misma hora cada día, incluidos los fines de semana.",
            "Pesa la porción con una balanza de cocina en lugar de usar tazas.",
            "Retira el alimento sobrante después de 20 minutos si tu mascota no termina.",
        ],
    },
    {
        "id": "agua",
        "title": "Hidratación diaria",
        "duration": "2 min",
        "level": "Esencial",
        "desc": "Cómo asegurar agua limpia y suficiente durante todo el día.",
        "steps": [
            "Cambia el agua al menos dos veces al día y lava el bebedero a diario.",
            "Programa tomas de agua en los mismos horarios de las comidas.",
            "Observa la cantidad que bebe: un cambio brusco merece una visita al veterinario.",
        ],
    },
    {
        "id": "peso",
        "title": "Control de peso saludable",
        "duration": "5 min",
        "level": "Avanzado",
        "desc": "Ajusta las porciones según la condición corporal, no solo según la báscula.",
        "steps": [
            "Pesa a tu mascota cada dos semanas en la misma báscula y a la misma hora.",
            "Revisa la condición corporal: costillas palpables y cintura visible.",
            "Ajusta la ración diaria un 10 % y vuelve a valorar en dos semanas.",
            "Consulta con tu veterinario antes de iniciar una dieta de pérdida de peso.",
        ],
    },
    {
        "id": "premios",
        "title": "Premios sin desbalancear",
        "duration": "3 min",
        "level": "Intermedio",
        "desc": "Incluye premios dentro del cálculo diario sin exceder las calorías.",
        "steps": [
            "Reserva un máximo del 10 % de las calorías diarias para premios.",
            "Resta los gramos de premios de la porción de la comida principal.",
            "Prefiere premios bajos en calorías o trocitos del mismo alimento.",
        ],
    },
    {
        "id": "transicion",
        "title": "Cambio de alimento",
        "duration": "4 min",
        "level": "Intermedio",
        "desc": "Cambia de pienso de forma gradual para evitar molestias digestivas.",
        "steps": [
            "Durante 3 días mezcla 25 % del alimento nuevo con 75 % del anterior.",
            "Aumenta al 50 % durante los siguientes 3 días.",
            "Sube al 75 % y, tras una semana, completa la transición al 100 %.",
            "Detén el cambio si aparecen vómitos o diarrea y consulta al veterinario.",
        ],
    },
]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)
        columns = [row[1] for row in db.execute("PRAGMA table_info(pets)")]
        if "species" not in columns:
            db.execute("ALTER TABLE pets ADD COLUMN species TEXT NOT NULL DEFAULT 'perro'")


init_db()


CO_TZ = timezone(timedelta(hours=-5), "America/Bogota")


def now_local() -> datetime:
    return datetime.now(CO_TZ)


def to_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=CO_TZ)
    return value.astimezone(CO_TZ)


def clock_12(hour: int, minute: int) -> str:
    suffix = "a. m." if hour < 12 else "p. m."
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


def now_iso() -> str:
    return now_local().replace(tzinfo=None).isoformat(timespec="seconds")


def get_user() -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM users WHERE id = 1").fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_user():
            return redirect(url_for("setup"))
        return view(*args, **kwargs)

    return wrapped


def clean(value, default: str = "", maxlen: int = 80) -> str:
    text = (value or "").strip()
    return text[:maxlen] or default


def parse_weight(value, default: float = 8.0) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(0.5, min(120.0, weight)), 1)


def parse_int(value, default: int, lo: int, hi: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def valid_time(value, default: str = "08:00") -> str:
    if value and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        return value
    return default


def calc_guide(weight, stage="adulto", activity="normal", meals=2, species="perro") -> dict:
    w = max(0.5, float(weight or 0))
    rer = 70 * (w ** 0.75)
    factors = STAGE_FACTORS.get(species, STAGE_FACTORS["perro"])
    base = factors.get(stage, factors["adulto"])
    factor = max(1.0, base + ACTIVITY_ADJ.get(activity, 0.0))
    kcal = rer * factor
    grams = round(kcal / 3.6)
    meals = max(1, min(4, int(meals or 2)))
    per_meal = max(1, round(grams / meals))
    return {
        "weight": round(w, 1),
        "rer": round(rer),
        "factor": round(factor, 2),
        "kcal": round(kcal),
        "grams": grams,
        "meals": meals,
        "per_meal": per_meal,
        "species": species,
    }


def suggested_meals(per_meal: int, count: int) -> list[dict]:
    count = max(1, min(4, int(count or 2)))
    return [
        {"time": time, "grams": max(1, int(per_meal)), "label": MEAL_LABELS[count][i]}
        for i, time in enumerate(MEAL_TIMES[count])
    ]


def minutes_of(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def next_meal(meals) -> dict | None:
    enabled = [meal for meal in meals if meal["enabled"]]
    if not enabled:
        return None
    ordered = sorted(enabled, key=lambda meal: minutes_of(meal["time"]))
    now = now_local()
    now_minutes = now.hour * 60 + now.minute
    upcoming = next((meal for meal in ordered if minutes_of(meal["time"]) > now_minutes), ordered[0])
    tomorrow = minutes_of(upcoming["time"]) <= now_minutes
    hours, minutes = (int(part) for part in upcoming["time"].split(":"))
    target = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    if tomorrow:
        target += timedelta(days=1)
    return {"meal": upcoming, "target": target, "tomorrow": tomorrow}


def video_embed(url: str) -> dict:
    youtube = re.search(
        r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([\w-]{6,})", url or ""
    )
    if youtube:
        return {"kind": "iframe", "src": f"https://www.youtube.com/embed/{youtube.group(1)}"}
    vimeo = re.search(r"vimeo\.com/(\d+)", url or "")
    if vimeo:
        return {"kind": "iframe", "src": f"https://player.vimeo.com/video/{vimeo.group(1)}"}
    return {"kind": "video", "src": url}


@app.template_filter("fecha")
def fecha_filter(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        value = to_local(value)
    return f"{WEEKDAYS[value.weekday()]} {value.day} de {MONTHS[value.month - 1]}"


@app.template_filter("hora")
def hora_filter(value):
    if isinstance(value, datetime):
        local = to_local(value)
        return clock_12(local.hour, local.minute)
    if isinstance(value, str):
        if re.fullmatch(r"\d{1,2}:\d{2}", value):
            hour, minute = (int(part) for part in value.split(":"))
            return clock_12(hour, minute)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        local = to_local(parsed)
        return clock_12(local.hour, local.minute)
    return value


@app.template_filter("stage")
def stage_filter(value):
    return STAGES.get(value, value)


@app.template_filter("activity")
def activity_filter(value):
    return ACTIVITIES.get(value, value)


@app.template_filter("species")
def species_filter(value):
    return SPECIES.get(value, value)


@app.context_processor
def inject_globals():
    try:
        user = get_user()
    except sqlite3.Error:
        user = None
    return {
        "current_user": user,
        "stages": STAGES,
        "activities": ACTIVITIES,
        "species_options": SPECIES,
    }


@app.get("/")
@login_required
def index():
    db = get_db()
    user = get_user()
    pet = db.execute("SELECT * FROM pets WHERE id = 1").fetchone()
    meals = db.execute("SELECT * FROM meals ORDER BY time").fetchall()
    water = db.execute("SELECT * FROM water ORDER BY time").fetchall()
    device = db.execute("SELECT * FROM device WHERE id = 1").fetchone()
    guide = calc_guide(
        pet["weight_kg"], pet["stage"], pet["activity"], pet["meals_per_day"], pet["species"]
    )
    nxt = next_meal(meals)
    today = now_local().strftime("%Y-%m-%d")
    logs = db.execute(
        "SELECT * FROM logs WHERE substr(at, 1, 10) = ? ORDER BY at DESC", (today,)
    ).fetchall()
    meal_logs = [log for log in logs if log["type"] == "meal"]
    water_logs = [log for log in logs if log["type"] == "water"]
    goal = sum(meal["grams"] for meal in meals if meal["enabled"]) or guide["grams"]
    return render_template(
        "index.html",
        user=user,
        pet=pet,
        meals=meals,
        water=water,
        device=device,
        guide=guide,
        nxt=nxt,
        logs=logs[:6],
        meal_logs=meal_logs,
        water_logs=water_logs,
        goal=goal,
        grams_today=sum(log["grams"] or 0 for log in meal_logs),
        enabled_meals=sum(1 for meal in meals if meal["enabled"]),
        enabled_water=sum(1 for item in water if item["enabled"]),
        now=now_local(),
    )


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if get_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        user_name = clean(request.form.get("user_name"), "Tutor", 40)
        pet_name = clean(request.form.get("pet_name"), "Mi mascota", 40)
        species = request.form.get("species") if request.form.get("species") in SPECIES else "perro"
        weight = parse_weight(request.form.get("weight_kg"))
        stage = request.form.get("stage") if request.form.get("stage") in STAGES else "adulto"
        activity = (
            request.form.get("activity") if request.form.get("activity") in ACTIVITIES else "normal"
        )
        meals_per_day = parse_int(request.form.get("meals_per_day"), 3, 1, 4)
        guide = calc_guide(weight, stage, activity, meals_per_day, species)
        db = get_db()
        db.execute(
            "INSERT INTO users (id, name, created_at) VALUES (1, ?, ?)", (user_name, now_iso())
        )
        db.execute(
            "INSERT INTO pets (id, name, species, weight_kg, stage, activity, meals_per_day) "
            "VALUES (1, ?, ?, ?, ?, ?, ?)",
            (pet_name, species, weight, stage, activity, meals_per_day),
        )
        for meal in suggested_meals(guide["per_meal"], meals_per_day):
            db.execute(
                "INSERT INTO meals (time, grams, label, enabled) VALUES (?, ?, ?, 1)",
                (meal["time"], meal["grams"], meal["label"]),
            )
        for time, label in DEFAULT_WATER:
            db.execute(
                "INSERT INTO water (time, label, enabled) VALUES (?, ?, 1)", (time, label)
            )
        db.execute("INSERT INTO device (id, connected, last_sync) VALUES (1, 0, NULL)")
        db.execute("INSERT INTO membership (id, active, since) VALUES (1, 0, NULL)")
        db.commit()
        flash(f"¡Todo listo! {pet_name} ya tiene su rutina.", "success")
        return redirect(url_for("index"))
    return render_template("setup.html")


@app.get("/schedule")
@login_required
def schedule():
    db = get_db()
    pet = db.execute("SELECT * FROM pets WHERE id = 1").fetchone()
    meals = db.execute("SELECT * FROM meals ORDER BY time").fetchall()
    water = db.execute("SELECT * FROM water ORDER BY time").fetchall()
    guide = calc_guide(
        pet["weight_kg"], pet["stage"], pet["activity"], pet["meals_per_day"], pet["species"]
    )
    return render_template("schedule.html", meals=meals, water=water, guide=guide)


@app.post("/meals/add")
@login_required
def add_meal():
    time = valid_time(request.form.get("time"))
    grams = parse_int(request.form.get("grams"), 50, 1, 2000)
    label = clean(request.form.get("label"), "Comida", 40)
    db = get_db()
    db.execute(
        "INSERT INTO meals (time, grams, label, enabled) VALUES (?, ?, ?, 1)",
        (time, grams, label),
    )
    db.commit()
    flash("Comida añadida.", "success")
    return redirect(url_for("schedule"))


@app.post("/meals/<int:meal_id>/toggle")
@login_required
def toggle_meal(meal_id: int):
    db = get_db()
    meal = db.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
    if not meal:
        flash("Ese horario no existe.", "error")
        return redirect(url_for("schedule"))
    db.execute("UPDATE meals SET enabled = ? WHERE id = ?", (0 if meal["enabled"] else 1, meal_id))
    db.commit()
    return redirect(url_for("schedule"))


@app.route("/meals/<int:meal_id>/edit", methods=["GET", "POST"])
@login_required
def edit_meal(meal_id: int):
    db = get_db()
    meal = db.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
    if not meal:
        flash("Ese horario no existe.", "error")
        return redirect(url_for("schedule"))
    if request.method == "POST":
        time = valid_time(request.form.get("time"), meal["time"])
        grams = parse_int(request.form.get("grams"), meal["grams"], 1, 2000)
        label = clean(request.form.get("label"), meal["label"], 40)
        db.execute(
            "UPDATE meals SET time = ?, grams = ?, label = ? WHERE id = ?",
            (time, grams, label, meal_id),
        )
        db.commit()
        flash("Comida actualizada.", "success")
        return redirect(url_for("schedule"))
    return render_template(
        "edit.html",
        kind="meal",
        item=meal,
        title="Editar comida",
        action=url_for("edit_meal", meal_id=meal_id),
        delete_action=url_for("delete_meal", meal_id=meal_id),
    )


@app.post("/meals/<int:meal_id>/delete")
@login_required
def delete_meal(meal_id: int):
    db = get_db()
    db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    db.commit()
    flash("Comida eliminada.", "success")
    return redirect(url_for("schedule"))


@app.post("/water/add")
@login_required
def add_water():
    time = valid_time(request.form.get("time"), "12:00")
    label = clean(request.form.get("label"), "Agua fresca", 40)
    db = get_db()
    db.execute("INSERT INTO water (time, label, enabled) VALUES (?, ?, 1)", (time, label))
    db.commit()
    flash("Toma de agua añadida.", "success")
    return redirect(url_for("schedule"))


@app.post("/water/<int:water_id>/toggle")
@login_required
def toggle_water(water_id: int):
    db = get_db()
    item = db.execute("SELECT * FROM water WHERE id = ?", (water_id,)).fetchone()
    if not item:
        flash("Esa toma de agua no existe.", "error")
        return redirect(url_for("schedule"))
    db.execute(
        "UPDATE water SET enabled = ? WHERE id = ?", (0 if item["enabled"] else 1, water_id)
    )
    db.commit()
    return redirect(url_for("schedule"))


@app.route("/water/<int:water_id>/edit", methods=["GET", "POST"])
@login_required
def edit_water(water_id: int):
    db = get_db()
    item = db.execute("SELECT * FROM water WHERE id = ?", (water_id,)).fetchone()
    if not item:
        flash("Esa toma de agua no existe.", "error")
        return redirect(url_for("schedule"))
    if request.method == "POST":
        time = valid_time(request.form.get("time"), item["time"])
        label = clean(request.form.get("label"), item["label"], 40)
        db.execute("UPDATE water SET time = ?, label = ? WHERE id = ?", (time, label, water_id))
        db.commit()
        flash("Toma de agua actualizada.", "success")
        return redirect(url_for("schedule"))
    return render_template(
        "edit.html",
        kind="water",
        item=item,
        title="Editar toma de agua",
        action=url_for("edit_water", water_id=water_id),
        delete_action=url_for("delete_water", water_id=water_id),
    )


@app.post("/water/<int:water_id>/delete")
@login_required
def delete_water(water_id: int):
    db = get_db()
    db.execute("DELETE FROM water WHERE id = ?", (water_id,))
    db.commit()
    flash("Toma de agua eliminada.", "success")
    return redirect(url_for("schedule"))


@app.get("/guide")
@login_required
def guide_page():
    pet = get_db().execute("SELECT * FROM pets WHERE id = 1").fetchone()
    species = (
        request.args.get("species") if request.args.get("species") in SPECIES else pet["species"]
    )
    weight = parse_weight(request.args.get("weight", pet["weight_kg"]), pet["weight_kg"])
    stage = request.args.get("stage") if request.args.get("stage") in STAGES else pet["stage"]
    activity = (
        request.args.get("activity")
        if request.args.get("activity") in ACTIVITIES
        else pet["activity"]
    )
    meals = parse_int(request.args.get("meals_per_day", pet["meals_per_day"]), pet["meals_per_day"], 1, 4)
    result = calc_guide(weight, stage, activity, meals, species)
    reference = [
        calc_guide(w, "adulto", "normal", 3, species) for w in [5, 10, 15, 20, 30, 40]
    ]
    return render_template(
        "guide.html",
        pet=pet,
        species=species,
        weight=weight,
        stage=stage,
        activity=activity,
        meals=meals,
        result=result,
        reference=reference,
    )


@app.post("/guide/apply")
@login_required
def apply_plan():
    weight = parse_weight(request.form.get("weight"))
    species = request.form.get("species") if request.form.get("species") in SPECIES else "perro"
    stage = request.form.get("stage") if request.form.get("stage") in STAGES else "adulto"
    activity = (
        request.form.get("activity") if request.form.get("activity") in ACTIVITIES else "normal"
    )
    meals = parse_int(request.form.get("meals_per_day"), 3, 1, 4)
    guide = calc_guide(weight, stage, activity, meals, species)
    db = get_db()
    db.execute(
        "UPDATE pets SET species = ?, weight_kg = ?, stage = ?, activity = ?, "
        "meals_per_day = ? WHERE id = 1",
        (species, weight, stage, activity, meals),
    )
    db.execute("DELETE FROM meals")
    for meal in suggested_meals(guide["per_meal"], meals):
        db.execute(
            "INSERT INTO meals (time, grams, label, enabled) VALUES (?, ?, ?, 1)",
            (meal["time"], meal["grams"], meal["label"]),
        )
    db.commit()
    flash(f"Plan aplicado: {guide['per_meal']} g por comida.", "success")
    return redirect(url_for("schedule"))


@app.get("/premium")
@login_required
def premium():
    db = get_db()
    membership = db.execute("SELECT * FROM membership WHERE id = 1").fetchone()
    advice = db.execute("SELECT * FROM advice ORDER BY created_at DESC").fetchall()
    videos = db.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
    return render_template(
        "premium.html",
        premium=bool(membership and membership["active"]),
        membership=membership,
        advice=advice,
        videos=videos,
        tutorials=TUTORIALS,
    )


@app.post("/premium/activate")
@login_required
def activate_premium():
    db = get_db()
    db.execute(
        "UPDATE membership SET active = 1, since = ? WHERE id = 1", (now_iso(),)
    )
    db.commit()
    flash("Membresía Premium activada (demo).", "success")
    return redirect(url_for("premium"))


@app.post("/premium/cancel")
@login_required
def cancel_premium():
    db = get_db()
    db.execute("UPDATE membership SET active = 0 WHERE id = 1")
    db.commit()
    flash("Membresía cancelada.", "success")
    return redirect(url_for("premium"))


@app.post("/premium/advice")
@login_required
def add_advice():
    text = clean(request.form.get("text"), "", 1000)
    if not text:
        flash("Escribe qué necesitas para enviar la solicitud.", "error")
        return redirect(url_for("premium"))
    db = get_db()
    db.execute(
        "INSERT INTO advice (text, status, created_at) VALUES (?, 'En revisión', ?)",
        (text, now_iso()),
    )
    db.commit()
    flash("Solicitud enviada. Te contactaremos pronto.", "success")
    return redirect(url_for("premium"))


@app.post("/premium/videos")
@login_required
def add_video():
    title = clean(request.form.get("title"), "Video", 80)
    url = clean(request.form.get("url"), "", 500)
    if not re.match(r"^https?://", url, re.IGNORECASE):
        flash("Introduce una URL válida que empiece por http:// o https://", "error")
        return redirect(url_for("premium"))
    db = get_db()
    db.execute(
        "INSERT INTO videos (title, url, created_at) VALUES (?, ?, ?)",
        (title, url, now_iso()),
    )
    db.commit()
    flash("Video añadido a tu biblioteca.", "success")
    return redirect(url_for("premium"))


@app.post("/premium/videos/<int:video_id>/delete")
@login_required
def delete_video(video_id: int):
    db = get_db()
    db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    db.commit()
    flash("Video eliminado.", "success")
    return redirect(url_for("premium"))


@app.get("/premium/videos/<int:video_id>")
@login_required
def video_detail(video_id: int):
    video = get_db().execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not video:
        flash("Ese video no existe.", "error")
        return redirect(url_for("premium"))
    return render_template("video.html", video=video, embed=video_embed(video["url"]))


@app.get("/settings")
@login_required
def settings():
    db = get_db()
    user = get_user()
    pet = db.execute("SELECT * FROM pets WHERE id = 1").fetchone()
    return render_template("settings.html", user=user, pet=pet)


@app.post("/settings")
@login_required
def update_settings():
    user_name = clean(request.form.get("user_name"), "Tutor", 40)
    pet_name = clean(request.form.get("pet_name"), "Mi mascota", 40)
    species = request.form.get("species") if request.form.get("species") in SPECIES else "perro"
    weight = parse_weight(request.form.get("weight_kg"))
    stage = request.form.get("stage") if request.form.get("stage") in STAGES else "adulto"
    activity = (
        request.form.get("activity") if request.form.get("activity") in ACTIVITIES else "normal"
    )
    db = get_db()
    db.execute("UPDATE users SET name = ? WHERE id = 1", (user_name,))
    db.execute(
        "UPDATE pets SET name = ?, species = ?, weight_kg = ?, stage = ?, activity = ? WHERE id = 1",
        (pet_name, species, weight, stage, activity),
    )
    db.commit()
    flash("Perfil guardado.", "success")
    return redirect(url_for("settings"))


@app.post("/settings/reset")
@login_required
def reset_data():
    db = get_db()
    for table in ["logs", "meals", "water", "advice", "videos", "device", "membership", "pets", "users"]:
        db.execute(f"DELETE FROM {table}")
    db.commit()
    flash("Todos los datos han sido borrados.", "success")
    return redirect(url_for("setup"))


@app.post("/device/connect")
@login_required
def connect_device():
    db = get_db()
    db.execute("UPDATE device SET connected = 1, last_sync = ? WHERE id = 1", (now_iso(),))
    db.commit()
    flash("Comedero conectado correctamente.", "success")
    return redirect(request.referrer or url_for("index"))


@app.post("/device/disconnect")
@login_required
def disconnect_device():
    db = get_db()
    db.execute("UPDATE device SET connected = 0 WHERE id = 1")
    db.commit()
    flash("Comedero desconectado.", "success")
    return redirect(request.referrer or url_for("index"))


@app.post("/device/dispense")
@login_required
def dispense():
    db = get_db()
    device = db.execute("SELECT * FROM device WHERE id = 1").fetchone()
    if not device or not device["connected"]:
        flash("Conecta el comedero antes de dispensar.", "error")
        return redirect(request.referrer or url_for("index"))
    pet = db.execute("SELECT * FROM pets WHERE id = 1").fetchone()
    meals = db.execute("SELECT * FROM meals ORDER BY time").fetchall()
    nxt = next_meal(meals)
    if nxt:
        grams = nxt["meal"]["grams"]
        label = nxt["meal"]["label"]
    else:
        grams = calc_guide(
            pet["weight_kg"], pet["stage"], pet["activity"], pet["meals_per_day"], pet["species"]
        )["per_meal"]
        label = "Comida"
    db.execute(
        "INSERT INTO logs (type, label, grams, at) VALUES ('meal', ?, ?, ?)",
        (label, grams, now_iso()),
    )
    db.execute("UPDATE device SET last_sync = ? WHERE id = 1", (now_iso(),))
    db.commit()
    flash(f"{grams} g dispensados · {label}.", "success")
    return redirect(request.referrer or url_for("index"))


@app.post("/water/log")
@login_required
def log_water():
    db = get_db()
    db.execute(
        "INSERT INTO logs (type, label, grams, at) VALUES ('water', 'Agua fresca', NULL, ?)",
        (now_iso(),),
    )
    db.commit()
    flash("Toma de agua registrada.", "success")
    return redirect(request.referrer or url_for("index"))


@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json"
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug)
