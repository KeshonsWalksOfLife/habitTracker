# habit_checkin.py VERSION = 2.0 (CSV + Notion)
import argparse, csv, os, sys
from datetime import datetime, date

# ---------- Paths ----------
BASE = os.path.dirname(os.path.abspath(__file__))
HABITS = os.path.join(BASE, "habits.csv")
LOG    = os.path.join(BASE, "habit_log.csv")

# ---------- Notion ----------
import requests
NOTION_TOKEN  = os.getenv("NOTION_TOKEN")
NOTION_DB_LOG = os.getenv("NOTION_DB_LOG")
NOTION_API    = "https://api.notion.com/v1/pages"
NOTION_VER    = "2022-06-28"

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VER
    }

def rt(text):
    return [{"type":"text","text":{"content": str(text)}}] if text else []

def send_to_notion(d, habit, val, unit, note):
    """Send a single check-in to Notion. Skips if token/db not set."""
    if not (NOTION_TOKEN and NOTION_DB_LOG):
        return "(notion skipped: env not set)"
    payload = {
        "parent": {"database_id": NOTION_DB_LOG},
        "properties": {
            "Name":  {"title": rt(f"{habit} — {d}")},
            "Date":  {"date": {"start": d}},
            "Habit": {"rich_text": rt(habit)},
            "Value": {"number": float(val)},
            "Unit":  {"rich_text": rt(unit or "")},
            "Note":  {"rich_text": rt(note or "")}
        }
    }
    r = requests.post(NOTION_API, headers=notion_headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        return f"(notion error {r.status_code})"
    return r.json().get("id", "(ok)")

# ---------- CSV ----------
def load_habits():
    """Load active habits; tolerate BOM + spaces after commas."""
    habits = {}
    with open(HABITS, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f, skipinitialspace=True)
        for row in r:
            name = (row.get("habit") or "").strip()
            if not name: 
                continue
            active = (row.get("active") or "").strip().lower() == "true"
            if not active:
                continue
            row["unit"] = (row.get("unit") or "").strip()
            habits[name] = row
    return habits

def ensure_log():
    if not os.path.exists(LOG):
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["date","habit","value","unit","note"])

def write_csv(d, habit, val, unit, note):
    ensure_log()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([d, habit, val, unit, note])

# ---------- CLI ----------
def main():
    p = argparse.ArgumentParser(description="Quick habit check-in (CSV + Notion).")
    p.add_argument("--habit", required=True, help="Name as in habits.csv")
    p.add_argument("--value", help="Numeric value or '1' for done")
    p.add_argument("--note", default="", help="Optional note")
    p.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    args = p.parse_args()

    habits = load_habits()
    if args.habit not in habits:
        print("Habit not found. Available:")
        for n in habits: print(" -", n)
        sys.exit(2)

    d = args.date or date.today().isoformat()
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        print("Invalid --date, expected YYYY-MM-DD"); sys.exit(2)

    unit = habits[args.habit].get("unit","")
    val  = args.value if args.value not in (None, "") else "1"

    # 1) CSV
    write_csv(d, args.habit, val, unit, args.note)

    # 2) Notion (best-effort; won’t block CSV)
    notion_id = send_to_notion(d, args.habit, val, unit, args.note)

    print(f"Logged CSV ✅ | Notion: {notion_id} | {d} | {args.habit} -> {val} {unit} {('- ' + args.note) if args.note else ''}")

if __name__ == "__main__":
    main()
