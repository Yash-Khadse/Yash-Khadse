"""Generate light/dark GitHub streak cards from the GraphQL contribution calendar.
Env: USERNAME, GH_TOKEN. Output: profile-streak/streak.svg and streak-dark.svg
No third-party dependencies."""
import datetime as dt
import json
import os
import urllib.request

API = "https://api.github.com/graphql"

THEMES = {
    "streak.svg": dict(bg="#ffffff", border="#d0d7de", accent="#0e75b6", num="#24292f", label="#0e75b6", sub="#57606a"),
    "streak-dark.svg": dict(bg="#0d1117", border="#30363d", accent="#58a6ff", num="#c9d1d9", label="#58a6ff", sub="#8b949e"),
}


def gql(query, variables, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "streak-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_days(user, token):
    created = gql("query($u:String!){user(login:$u){createdAt}}", {"u": user}, token)["user"]["createdAt"]
    start = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    q = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
      contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    days = {}
    for year in range(start.year, now.year + 1):
        f = max(start, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
        t = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        cal = gql(q, {"u": user, "f": f.isoformat(), "t": t.isoformat()}, token)["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return days, start.year


def compute(days, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    dates = sorted(dt.date.fromisoformat(d) for d in days)
    total = sum(days.values())
    # longest streak
    best = (0, None, None)
    run, run_start, prev = 0, None, None
    for d in dates:
        if days[d.isoformat()] > 0:
            if prev is not None and (d - prev).days == 1 and run > 0:
                run += 1
            else:
                run, run_start = 1, d
            if run > best[0]:
                best = (run, run_start, d)
        else:
            run = 0
        prev = d
    # current streak (today may still be empty)
    cur_end = today if days.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
    cur, d = 0, cur_end
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    cur_start = cur_end - dt.timedelta(days=cur - 1) if cur else None
    return dict(total=total, cur=cur, cur_range=(cur_start, cur_end if cur else None), best=best[0], best_range=(best[1], best[2]))


def fmt(d):
    return f"{d:%b} {d.day}" if d else ""


def rng(r):
    a, b = r
    if not a:
        return "—"
    return fmt(a) if a == b else f"{fmt(a)} – {fmt(b)}"


def render(s, since, th):
    f = "font-family:'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="495" height="150" viewBox="0 0 495 150" role="img" aria-label="GitHub streak: {s['cur']} day current streak, {s['best']} day longest, {s['total']} total contributions">
  <rect x="0.5" y="0.5" width="494" height="149" rx="10" fill="{th['bg']}" stroke="{th['border']}"/>
  <line x1="165" y1="30" x2="165" y2="120" stroke="{th['border']}"/>
  <line x1="330" y1="30" x2="330" y2="120" stroke="{th['border']}"/>
  <g text-anchor="middle" style="{f}">
    <text x="82" y="70" font-size="30" font-weight="700" fill="{th['num']}">{s['total']:,}</text>
    <text x="82" y="95" font-size="13" font-weight="600" fill="{th['label']}">Total Contributions</text>
    <text x="82" y="114" font-size="11" fill="{th['sub']}">{since} – Present</text>

    <circle cx="247" cy="62" r="34" fill="none" stroke="{th['accent']}" stroke-width="5"/>
    <text x="247" y="72" font-size="28" font-weight="700" fill="{th['num']}">{s['cur']}</text>
    <text x="247" y="118" font-size="13" font-weight="600" fill="{th['label']}">Current Streak</text>
    <text x="247" y="136" font-size="11" fill="{th['sub']}">{rng(s['cur_range'])}</text>

    <text x="412" y="70" font-size="30" font-weight="700" fill="{th['num']}">{s['best']}</text>
    <text x="412" y="95" font-size="13" font-weight="600" fill="{th['label']}">Longest Streak</text>
    <text x="412" y="114" font-size="11" fill="{th['sub']}">{rng(s['best_range'])}</text>
  </g>
</svg>
'''


def main():
    user, token = os.environ["USERNAME"], os.environ["GH_TOKEN"]
    days, since = fetch_days(user, token)
    stats = compute(days)
    os.makedirs("profile-streak", exist_ok=True)
    for name, th in THEMES.items():
        with open(os.path.join("profile-streak", name), "w", encoding="utf-8") as fh:
            fh.write(render(stats, since, th))
    print("streak:", stats)


if __name__ == "__main__":
    main()
