
from flask import Flask, render_template, request, jsonify
import os, csv, requests
from datetime import date, datetime
from pathlib import Path

# .env support
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# -------- paths ----------
BASE   = Path(__file__).resolve().parent
HABITS = BASE / "habits.csv"
LOG    = BASE / "habit_log.csv"

# -------- Notion ----------
NOTION_TOKEN  = os.getenv("NOTION_TOKEN")
NOTION_DB_LOG = os.getenv("NOTION_DB_LOG")
NOTION_API    = "https://api.notion.com/v1/pages"
NOTION_VER    = "2025-09-03"   # fixed string, not today's date

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}" if NOTION_TOKEN else "",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VER
    }

def send_to_notion(d, habit, val, unit, note):
    if not (NOTION_TOKEN and NOTION_DB_LOG):
        return "(notion skipped)"
    payload = {
        "parent": {"database_id": NOTION_DB_LOG},
        "properties": {
            "Name":  {"title":[{"type":"text","text":{"content": f"{habit} — {d}"}}]},
            "Date":  {"date":{"start": d}},
            "Habit": {"rich_text":[{"type":"text","text":{"content": habit}}]},
            "Value": {"number": float(val)},
            "Unit":  {"rich_text":[{"type":"text","text":{"content": unit or ""}}]},
            "Note":  {"rich_text":[{"type":"text","text":{"content": note or ""}}]},
        }
    }
    r = requests.post(NOTION_API, headers=notion_headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        return f"(notion error {r.status_code})"
    return r.json().get("id","(ok)")

# -------- CSV helpers ----------
def load_habits():
    habits = {}
    if not HABITS.exists(): return habits
    with open(HABITS, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f, skipinitialspace=True)
        for row in r:
            name = (row.get("habit") or "").strip()
            if not name: continue
            if (row.get("active") or "").strip().lower() != "true": continue
            unit = (row.get("unit") or "").strip()
            habits[name] = {"unit": unit}
    return habits

def ensure_log():
    if not LOG.exists():
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["date","habit","value","unit","note"])

def write_csv(d, habit, val, unit, note):
    ensure_log()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([d, habit, val, unit, note])

def recent(n=10):
    if not LOG.exists(): return []
    with open(LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))[-n:]
    
def load_logs_all():
    if not LOG.exists(): return []
    with open(LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, skipinitialspace=True))

def compute_levels():
    """Aggregate totals & XP per habit -> level + progress."""
    habits = {}
    # read xp_per_unit from habits.csv
    with open(HABITS, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, skipinitialspace=True):
            name = (r.get("habit") or "").strip()
            if not name: continue
            habits[name] = {
                "unit": (r.get("unit") or "").strip(),
                "active": (r.get("active") or "").strip().lower()=="true",
                "xp_per_unit": float((r.get("xp_per_unit") or "0") or 0),
            }

    totals = {h: 0.0 for h in habits}
    xp     = {h: 0.0 for h in habits}

    for row in load_logs_all():
        h = (row.get("habit") or "").strip()
        if h not in habits: continue
        val = float((row.get("value") or "1") or 1)
        totals[h] += val
        xp[h]     += val * habits[h]["xp_per_unit"]

    # simple leveling curve; tweak if you prefer
    # lvl 1 at 0 XP; thresholds grow: 0, 100, 300, 600, 1000, 1500, ...
    def level_from_xp(x):
        thresholds = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500]
        lvl = 1
        for t in thresholds:
            if x >= t: lvl += 1
        next_t = next((t for t in thresholds if t > x), thresholds[-1] + 600)
        return lvl-1, x, next_t

    out = []
    for h in habits:
        lvl, cur_xp, next_t = level_from_xp(xp[h])
        out.append({
            "habit": h,
            "unit": habits[h]["unit"],
            "total": totals[h],
            "xp": round(xp[h], 1),
            "level": lvl,
            "next_level_xp": next_t,
            "progress_pct": round( (cur_xp / next_t * 100) if next_t else 100, 1)
        })
    return sorted(out, key=lambda r: (-r["level"], r["habit"]))

# --- Habits CRUD helpers ---
def read_habits_rows():
    rows = []
    if not HABITS.exists(): return rows
    with open(HABITS, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, skipinitialspace=True))
    return rows

def write_habits_rows(rows):
    fieldnames = ["habit","category","cadence","target_per_week","unit","active"]
    with open(HABITS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({
                "habit": (r.get("habit") or "").strip(),
                "category": r.get("category",""),
                "cadence": (r.get("cadence") or "weekly"),
                "target_per_week": r.get("target_per_week","0"),
                "unit": r.get("unit",""),
                "active": ("true" if str(r.get("active","true")).lower()=="true" else "false")
            })

# -------- Flask app (create BEFORE routes) ----------
app = Flask(__name__)

# -- levels for Stats ---

@app.get("/api/stats")
def api_stats():
    return jsonify({"stats": compute_levels()})

@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.get("/api/habits")
def api_habits():
    h = load_habits()
    return jsonify({
        "habits": sorted(h.keys()),
        "units": {k: v["unit"] for k, v in h.items()}
    })

@app.get("/")
def index():
    h = load_habits()
    return render_template("index.html",
        habits=sorted(h.keys()),
        today=date.today().isoformat(),
        recent=recent(10),
        units={k:v["unit"] for k,v in h.items()}
    )

# ---------- FIXED /log route (all logic stays inside) ----------
@app.post("/log")
def log():
    data  = request.form
    habit = (data.get("habit") or "").strip()
    value = (data.get("value") or "1").strip()
    note  = (data.get("note")  or "").strip()
    d     = (data.get("date")  or date.today().isoformat()).strip()

    # validate date
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        return jsonify({"ok": False, "error": "Date must be YYYY-MM-DD"}), 400

    # habit exists?
    h = load_habits()
    if habit not in h:
        return jsonify({"ok": False, "error": "Unknown habit"}), 400

    unit = h[habit]["unit"]
    write_csv(d, habit, value, unit, note)
    notion_id = send_to_notion(d, habit, value, unit, note)
    return jsonify({"ok": True, "notion": notion_id})

# ---------- Manage routes ----------
@app.get("/manage")
def manage():
    rows = read_habits_rows()
    return render_template("manage.html", rows=rows)

@app.post("/manage/add")
def manage_add():
    form = request.form
    name = (form.get("habit") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Habit name is required"}), 400

    rows = read_habits_rows()
    if any((r.get("habit") or "").strip().lower() == name.lower() for r in rows):
        return jsonify({"ok": False, "error": "Habit already exists"}), 400

    rows.append({
        "habit": name,
        "category": form.get("category",""),
        "cadence": form.get("cadence","weekly"),
        "target_per_week": form.get("target_per_week","0"),
        "unit": form.get("unit",""),
        "active": "true",
    })
    
    write_habits_rows(rows)
    fieldnames = ["habit","category","cadence","target_per_week","unit","active","xp_per_unit"]
    with open(HABITS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({
                "habit": (r.get("habit") or "").strip(),
                "category": r.get("category",""),
                "cadence": (r.get("cadence") or "weekly"),
                "target_per_week": r.get("target_per_week","0"),
                "unit": r.get("unit",""),
                "active": ("true" if str(r.get("active","true")).lower()=="true" else "false"),
                "xp_per_unit": r.get("xp_per_unit","0"),
            })

@app.post("/manage/toggle")
def manage_toggle():
    name = (request.form.get("habit") or "").strip()
    rows = read_habits_rows()
    for r in rows:
        if (r.get("habit") or "").strip().lower() == name.lower():
            r["active"] = "false" if str(r.get("active","true")).lower()=="true" else "true"
            write_habits_rows(rows)
            return jsonify({"ok": True, "active": r["active"]})
    return jsonify({"ok": False, "error": "Habit not found"}), 404

@app.post("/manage/delete")
def manage_delete():
    name = (request.form.get("habit") or "").strip()
    rows = read_habits_rows()
    new_rows = [r for r in rows if (r.get("habit") or "").strip().lower() != name.lower()]
    if len(new_rows) == len(rows):
        return jsonify({"ok": False, "error": "Habit not found"}), 404
    write_habits_rows(new_rows)
    return jsonify({"ok": True})

if __name__ == "__main__":
    import webbrowser, threading, time
    def _open(): time.sleep(0.8); webbrowser.open("http://127.0.0.1:6500")
    threading.Thread(target=_open, daemon=True).start()
    app.run(debug=True, port=6500)