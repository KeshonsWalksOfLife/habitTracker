#!/usr/bin/env python3
# habit_checkin_clean.py VERSION = 1.0
import argparse, csv, os, sys
from datetime import datetime, date

BASE = os.path.dirname(os.path.abspath(__file__))
HABITS = os.path.join(BASE, "habits.csv")
LOG = os.path.join(BASE, "habit_log.csv")

def load_habits():
    habits = {}
    with open(HABITS, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f, skipinitialspace=True)
        for row in r:
            name = (row.get("habit") or "").strip()
            if not name: 
                continue
            active_raw = (row.get("active") or "").strip().lower()
            if active_raw != "true": 
                continue
            row["unit"] = (row.get("unit") or "").strip()
            habits[name] = row
    return habits

def ensure_log():
    if not os.path.exists(LOG):
        with open(LOG, "w", newline="") as f:
            csv.writer(f).writerow(["date","habit","value","unit","note"])

def main():
    p = argparse.ArgumentParser(description="Quick habit check-in.")
    p.add_argument("--habit", required=True)
    p.add_argument("--value", required=False)
    p.add_argument("--note", default="")
    p.add_argument("--date", help="YYYY-MM-DD")
    args = p.parse_args()

    habits = load_habits()
    if args.habit not in habits:
        print("Habit not found. Available:")
        for n in habits: print(" -", n)
        sys.exit(2)

    unit = habits[args.habit].get("unit","")
    d = args.date or date.today().isoformat()
    try: datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        print("Invalid --date, expected YYYY-MM-DD"); sys.exit(2)

    val = args.value if (args.value not in (None, "")) else "1"

    ensure_log()
    with open(LOG, "a", newline="") as f:
        csv.writer(f).writerow([d, args.habit, val, unit, args.note])

    print(f"Logged: {d} | {args.habit} -> {val} {unit} {('- ' + args.note) if args.note else ''}")

if __name__ == "__main__":
    main()
