"""Standalone extract of georgekobaidze's contribution-city only.

Source geometry (tools/profile/render.py, build_city):
  iso tile 25 x 12.5, origin (152.5, 262), tallest building 118px,
  height = 8 + (118-8) * sqrt(n / peak), roofs by GitHub-style quartiles,
  deterministic windows (seeded PRNG, 55% lit, 3% flicker), stars/moon/plane.

What was stripped: the whole console frame (header, stats, projects,
stack, writing slices, embedded JetBrains Mono font). This file draws
only the city, on a dark-purple card.

Recolour — user palette, exactly:
  empty lot / card background : #000000 (was #160529, changed to black 2026-10-26)
  roof level 0 (quietest)     : #3C096C
  roof level 1                : #6A0DAD
  roof level 2                : #7B1FA2
  roof level 3 (busiest)      : #8A2BE2
  lit windows (left face)     : #D180FF
  lit windows (right face)    : #8A2BE2
  Building side faces are a darkened shade of that day's roof colour
  (same _shade helper as the original), so no extra colours are introduced
  for the buildings themselves. Text/stars stay neutral grey-white.
"""
import datetime, hashlib, html, json, math, os, pathlib, re, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
# When this file lives at tools/contribution-city/generate.py in the
# profile repo, the SVG goes to assets/contribution-city-purple.svg
# at the repo root. When run locally from this folder, fall back to
# writing next to the script.
ROOT = HERE.parent.parent
OUT = (ROOT / "assets" / "contribution-city-purple.svg"
       if (ROOT / "assets").exists() or os.environ.get("GITHUB_ACTIONS")
       else HERE / "contribution-city-purple.svg")

# user palette — buildings/windows ONLY. Everything else is a brightened
# black / neutral grey, no purple accents outside the buildings.
# 2026-10-26 follow-up: pure #000000 was too black to see the grid, so
# the background is now #0f1117 (brightened black) and the ground grid
# is drawn explicitly underneath every building.
BG = "#0f1117"
GRID_FILL, GRID_STROKE = "#1c2029", "#454b5c"
ROOFS = ["#3C096C", "#6A0DAD", "#7B1FA2", "#8A2BE2"]  # quiet -> busiest
WIN_ON, WIN_ON_SIDE, WIN_OFF = "#D180FF", "#8A2BE2", "#0f1117"
ACCENT = "#f0f6fc"  # neutral white for headings/info, NOT a palette colour

CITY_TW, CITY_TH = 25, 12.5
CITY_OX, CITY_OY = 152.5, 262
CITY_HMAX = 118
W, H = 880, 680
e = html.escape


def _shade(hexc, f):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * f))) for c in (r, g, b))


def _p(x, y):
    return f"{x:.1f},{y:.1f}"


def _rng(seed):
    state = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    while True:
        state = (state * 6364136223846793005 + 1442695040888963407) % 2**64
        yield (state >> 11) / 2**53


def _levels(counts):
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [1, 1, 1]
    q = lambda f: nz[min(len(nz) - 1, int(len(nz) * f))]
    return [q(.25), q(.5), q(.75)]


def load_calendar():
    """Last ~365 days of contributions via the GitHub GraphQL API.

    Env: GITHUB_TOKEN (provided automatically in Actions, public data
    only — private contributions are NOT included, same as the original
    Oct 26 build), USERNAME (defaults to the repo owner in Actions,
    else soumaydutt). No token -> the workflow fails visibly instead
    of silently committing a stale city.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    user = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "soumaydutt"
    today = datetime.datetime.now(datetime.timezone.utc).date()
    end = today
    start = today - datetime.timedelta(days=365)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    body = json.dumps({"query": query, "variables": {
        "login": user,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{end.isoformat()}T23:59:59Z"}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "contribution-city-updater"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
    if res.get("errors"):
        raise SystemExit("GraphQL error: " + "; ".join(e.get("message", "?") for e in res["errors"]))
    days = {}
    cal = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            days[day["date"]] = day["contributionCount"]
    out, d = [], start
    while d <= end:
        out.append([d.isoformat(), days.get(d.isoformat(), 0)])
        d += datetime.timedelta(days=1)
    return out, end.isoformat()


def build_city(calendar, updated):
    days = [(datetime.date.fromisoformat(d), n) for d, n in calendar]
    counts = [n for _, n in days]
    total, peak = sum(counts), max(counts) if counts else 0
    # NOTE: the original's quartile thresholds collapse on this data
    # (quartiles [1, 2, 2] -> no day ever lands on level 2, so #7B1FA2
    # would never render as a roof). Count bands keep the same
    # quiet->busiest order and make all four roof colours appear:
    # 1 -> level 0, 2 -> level 1, 3-4 -> level 2, 5+ -> level 3.
    rnd = _rng(f"{updated}-{total}")
    start = days[0][0]

    cells = []
    for d, n in days:
        idx = (d - start).days
        cells.append((idx // 7, (d.weekday() + 1) % 7, n))
    cells.sort(key=lambda c: (c[0] + c[1], c[0]))

    # Ground grid, drawn FIRST so buildings sit on it: every day's tile,
    # plus a 1-tile border around the whole city so the platform extends
    # visibly beyond the front and back rows. Empty tiles stay visible
    # (fill lighter than the background, grey outline) instead of blending in.
    grid = []
    for w in range(-1, 54):
        for dow in range(-1, 8):
            cx = CITY_OX + (w - dow) * CITY_TW / 2
            cy = CITY_OY + (w + dow) * CITY_TH / 2
            L, R = (cx - CITY_TW / 2, cy), (cx + CITY_TW / 2, cy)
            T, B = (cx, cy - CITY_TH / 2), (cx, cy + CITY_TH / 2)
            grid.append(f'<path d="M{_p(*T)}L{_p(*R)}L{_p(*B)}L{_p(*L)}Z" fill="{GRID_FILL}" stroke="{GRID_STROKE}" stroke-width=".7"/>')

    shapes, flick = [], 0
    for w, dow, n in cells:
        cx = CITY_OX + (w - dow) * CITY_TW / 2
        cy = CITY_OY + (w + dow) * CITY_TH / 2
        L, R = (cx - CITY_TW / 2, cy), (cx + CITY_TW / 2, cy)
        T, B = (cx, cy - CITY_TH / 2), (cx, cy + CITY_TH / 2)
        if n == 0:
            continue  # its grid tile (above) already shows the empty lot
        h = 8 + (CITY_HMAX - 8) * math.sqrt(n / peak)
        level = 0 if n == 1 else 1 if n == 2 else 2 if n <= 4 else 3
        roof = ROOFS[level]
        Tu, Ru, Bu, Lu = [(x, y - h) for x, y in (T, R, B, L)]
        # More defined: faces further apart in brightness (0.70 / 0.40,
        # was 0.55 / 0.35) and a black outline on every face and roof.
        shapes.append(f'<path d="M{_p(*L)}L{_p(*B)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{_shade(roof, 0.70)}" stroke="#000000" stroke-width=".5"/>'
                      f'<path d="M{_p(*B)}L{_p(*R)}L{_p(*Ru)}L{_p(*Bu)}Z" fill="{_shade(roof, 0.40)}" stroke="#000000" stroke-width=".5"/>'
                      f'<path d="M{_p(*Tu)}L{_p(*Ru)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{roof}" stroke="#000000" stroke-width=".8"/>')
        on, side, off, fl = [], [], [], []
        for face, (a, b) in (("l", (L, B)), ("r", (B, R))):
            for r in range(int((h - 6) // 7)):
                v0 = 5 + r * 7
                for u0 in (.18, .58):
                    lit = next(rnd) < .55
                    if not lit and next(rnd) < .5:
                        continue
                    pts = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - v)
                           for u, v in ((u0, v0), (u0 + .30, v0), (u0 + .30, v0 + 3.6), (u0, v0 + 3.6))]
                    seg = "M" + "L".join(_p(*q) for q in pts) + "Z"
                    if not lit:
                        off.append(seg)
                    else:
                        # Blink probability by building tier, so the tallest
                        # buildings blink the most, quiet ones barely at all:
                        # level 0: 1%, 1: 3%, 2: 6%, 3 (tallest): 15%.
                        # Only a few windows overall, but skewed to the top.
                        p = (0.01, 0.03, 0.06, 0.15)[level]
                        if next(rnd) < p:
                            fl.append((seg, face, roof))
                        else:
                            (on if face == "l" else side).append(seg)
        if off:
            shapes.append(f'<path d="{"".join(off)}" fill="{WIN_OFF}"/>')
        if on:
            shapes.append(f'<path d="{"".join(on)}" fill="{WIN_ON}"/>')
        if side:
            shapes.append(f'<path d="{"".join(side)}" fill="{WIN_ON_SIDE}"/>')
        # Colour blink, NOT opacity: window colour -> building (roof) colour
        # -> window colour again. Each flick window gets its own duration
        # (18/24/30/36s) and a random delay, so the durations drift apart
        # and a different set of windows is blinking at any given moment.
        # The animation name encodes face + roof tier, so the keyframes
        # below know both the start colour and the building colour.
        for seg, face, roof in fl:
            flick += 1
            lvl = ROOFS.index(roof)
            dur = (18, 24, 30, 36)[flick % 4]
            delay = next(rnd) * 36
            orig = WIN_ON if face == "l" else WIN_ON_SIDE
            shapes.append(f'<path d="{seg}" fill="{orig}" style="animation: blink{"L" if face == "l" else "R"}{lvl} {dur}s infinite; animation-delay: {delay:.1f}s"/>')

    stars = []
    for i in range(46):
        x, y = 470 + next(rnd) * 350, 118 + next(rnd) * 150
        if x > 700 and y < 215:
            continue
        cls = f' class="s{i % 3}"' if i % 3 == 0 else ""
        stars.append(f'<circle{cls} cx="{x:.1f}" cy="{y:.1f}" r="{(.6, .8, 1.1)[i % 3]}" fill="#c9d1d9" opacity="{.35 + next(rnd) * .5:.2f}"/>')
    busiest_d, busiest_n = max(days, key=lambda t: t[1]) if days else (None, 0)
    info = [f'<tspan font-weight="700" fill="{ACCENT}">{total:,}</tspan> contributions · last 365 days',
            f'busiest day <tspan fill="#f0f6fc">{busiest_d:%b} {busiest_d.day}</tspan> · {busiest_n}' if busiest_n else "",
            f'{sum(1 for n in counts if n)} active days']
    info_svg = "".join(f'<text x="{W-36}" y="{300 + i*20}" text-anchor="end" fill="#8b949e" style="font-size:12px">{t}</text>'
                       for i, t in enumerate(info) if t)
    # FIX: legend squares used to start at the same x as the "quiet" label
    # and paint over it (that's why it read as "...iet" on the live profile).
    # "quiet" at x=52, squares start clear of it at x=100, "skyscraper" after.
    legend = "".join(f'<rect x="{100 + i*16}" y="{642}" width="11" height="11" fill="{c}"'
                     + (' stroke="#484f58" stroke-width="1"/>' if i == 0 else '/>')
                     for i, c in enumerate([BG] + ROOFS))
    body = f'''
<text x="52" y="44" font-weight="700" fill="{ACCENT}" style="font-size:20px">~/contribution-city</text>
<text x="52" y="96" fill="#8b949e"><tspan fill="{ACCENT}">$</tspan> render-city --last 365d <tspan fill="#484f58"># one building per day · soumaydutt</tspan></text>
<g>{"".join(stars)}</g>
<circle cx="{W-80}" cy="160" r="40" fill="url(#moonglow)"/>
<circle cx="{W-80}" cy="160" r="14" fill="#e6edf3"/>
<circle cx="{W-74}" cy="155" r="12.5" fill="{BG}"/>
<g class="plane"><g transform="translate(0 132)"><rect x="0" y="0" width="14" height="2" rx="1" fill="#484f58"/><circle class="bl" cx="0" cy="1" r="1.6" fill="{ACCENT}"/><circle class="bl" cx="14" cy="1" r="1.6" fill="#f0f6fc" style="animation-delay:.7s"/></g></g>
{info_svg}
<g>{"".join(grid)}</g>
{"".join(shapes)}
<text x="52" y="652" fill="#8b949e" style="font-size:11px">quiet</text>{legend}<text x="{100 + 5*16 + 6}" y="652" fill="#8b949e" style="font-size:11px">skyscraper</text>'''
    # Blink keyframes: one per face x roof tier. Left windows start
    # #D180FF, right windows start #8A2BE2; both blink to their building's
    # roof colour and back. Exception: right windows on tier-3 buildings
    # already ARE #8A2BE2, so they blink to #D180FF instead, or nothing
    # would visibly change.
    blink_css = []
    for i, roof in enumerate(ROOFS):
        blink_css.append(f"@keyframes blinkL{i}{{0%,85%,100%{{fill:{WIN_ON}}}92%{{fill:{roof}}}}}")
        target_r = roof if roof != WIN_ON_SIDE else WIN_ON
        blink_css.append(f"@keyframes blinkR{i}{{0%,85%,100%{{fill:{WIN_ON_SIDE}}}92%{{fill:{target_r}}}}}")
    css = ("text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:15px}\n"
           "@keyframes tw{0%,100%{opacity:.9}50%{opacity:.15}}\n"
           "@keyframes blink{0%,90%,100%{opacity:0}93%{opacity:1}}\n"
           "@keyframes fly{from{transform:translate(-40px,0)}to{transform:translate(920px,-30px)}}\n"
           ".s0{animation:tw 8s infinite}\n"
           + "\n".join(blink_css) + "\n"
           ".plane{animation:fly 26s linear infinite}.bl{animation:blink 1.4s infinite}\n"
           "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    desc = (f"Contribution city: an isometric night skyline with one building per day of the last year, "
            f"taller and brighter for busier days. {total:,} contributions"
            + (f", busiest day {busiest_d:%B} {busiest_d.day} with {busiest_n}" if busiest_n else "") + ".")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Contribution city — soumaydutt</title>
<desc id="d">{e(desc)}</desc>
<style>{css}</style>
<defs><radialGradient id="moonglow"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".22"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient></defs>
<rect width="{W}" height="{H}" fill="{BG}"/>
{body}
</svg>
'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT} — {total} contributions, {sum(1 for n in counts if n)} active days, peak {peak}, busiest {busiest_d} ({busiest_n})")


if __name__ == "__main__":
    calendar, updated = load_calendar()
    build_city(calendar, updated)
