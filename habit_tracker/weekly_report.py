#!/usr/bin/env python3
# weekly_report.py VERSION = 1.1
import csv, os
from datetime import datetime, date, timedelta
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
HABITS = os.path.join(BASE, "habits.csv")
LOG = os.path.join(BASE, "habit_log.csv")

def load_habits():
    cfg = {}
    with open(HABITS, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f, skipinitialspace=True)
        for row in r:
            active = (row.get("active") or "").strip().lower() == "true"
            if not active: 
                continue
            row["target_per_week"] = float((row.get("target_per_week") or "0").strip() or 0)
            row["cadence"] = (row.get("cadence") or "weekly").strip().lower()
            row["unit"] = (row.get("unit") or "").strip()
            cfg[(row.get("habit") or "").strip()] = row
    return cfg

def load_logs():
    entries = []
    if not os.path.exists(LOG): 
        return entries
    with open(LOG, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f, skipinitialspace=True)
        for row in r:
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            except Exception:
                continue
            try:
                v = float(row.get("value") or 1)
            except Exception:
                v = 1.0
            entries.append({
                "date": d,
                "habit": (row.get("habit") or "").strip(),
                "value": v,
                "unit": (row.get("unit") or "").strip(),
                "note": row.get("note") or ""
            })
    return entries

def week_range(any_date=None):
    d = any_date or date.today()
    start = d - timedelta(days=d.weekday())   # Monday
    end   = start + timedelta(days=6)
    return start, end

def compute_streak(entries, habit):
    days = {e["date"] for e in entries if e["habit"] == habit}
    if not days: return 0
    cur = date.today(); streak = 0
    while cur in days:
        streak += 1; cur -= timedelta(days=1)
    return streak

def main():
    cfg = load_habits()
    logs = load_logs()
    wk_start, wk_end = week_range()

    in_week = [e for e in logs if wk_start <= e["date"] <= wk_end]

    totals = defaultdict(float)
    counts = defaultdict(int)
    units  = {}
    for e in in_week:
        totals[e["habit"]] += e["value"]
        counts[e["habit"]] += 1
        if e["unit"]: units[e["habit"]] = e["unit"]

    rows = []
    for habit, h in cfg.items():
        unit = units.get(habit) or h.get("unit","")
        target = h["target_per_week"]
        total = totals.get(habit, 0.0)
        done  = counts.get(habit, 0)
        pct   = round((total/target*100.0), 1) if target > 0 else (100.0 if total>0 else 0.0)
        streak = compute_streak(logs, habit)
        rows.append({
            "habit": habit,
            "cadence": h["cadence"],
            "target_per_week": target,
            "total_this_week": total,
            "unit": unit,
            "entries_this_week": done,
            "completion_pct": pct,
            "daily_streak_days": streak
        })

    out_name = f"weekly_report_{wk_start.isoformat()}_to_{wk_end.isoformat()}.csv"
    out_path = os.path.join(BASE, out_name)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["habit","cadence","target_per_week","total_this_week","unit",
                      "entries_this_week","completion_pct","daily_streak_days"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows: w.writerow(r)

    print(f"Week: {wk_start} to {wk_end}")
    if not rows:
        print("No active habits or logs yet.")
        print(f"Report saved to: {out_path}")
        return

    # pretty print
    fieldnames = list(rows[0].keys())
    widths = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in fieldnames}
    header = " | ".join(k.ljust(widths[k]) for k in fieldnames)
    print(header)
    print("-"*len(header))
    for r in rows:
        print(" | ".join(str(r[k]).ljust(widths[k]) for k in fieldnames))
    print(f"\nReport saved to: {out_path}")

if __name__ == "__main__":
    main()
