#!/usr/bin/env python3
"""
Génère assets/neofetch.svg : un terminal animé façon neofetch, alimenté par
tes vraies données GitHub.

    python scripts/neofetch.py           # données réelles (GITHUB_TOKEN requis)
    # en local avec la CLI GitHub (PowerShell) :
    #   $env:GITHUB_TOKEN = gh auth token; $env:GH_LOGIN = "nicoco23"; python scripts/neofetch.py
    python scripts/neofetch.py --demo    # données fictives, pour tester le rendu

Variables d'environnement :
    GITHUB_TOKEN          token GitHub personnel (accès aux repos privés si INCLUDE_PRIVATE)
    GH_LOGIN              ton login GitHub (par défaut : propriétaire du repo)

Aucune dépendance : bibliothèque standard Python uniquement.
"""
import base64
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from html import escape
from pathlib import Path

# ═════════════════════════════════════════════════════════════ À PERSONNALISER
INFO_STATIC = [  # lignes fixes de la partie neofetch (label, valeur)
    ("École", "42 Paris · Archi. en Techno. du Numérique"),
    ("Rôle", "dev polyvalent · Ingé lumière"),
    ("Stack", "Java · React · Kotlin · C · Expo · VB.NET"),
]
EXCLUDED_LANGS = {"HTML", "CSS", "SCSS", "Makefile", "Shell", "Dockerfile",
                  "Batchfile", "PowerShell", "CMake", "Roff"}
TOP_LANGS = 5
INCLUDE_FORKS = True         # compter les forks (repos + langages)
INCLUDE_PRIVATE = True       # compter les repos privés (token personnel requis)
HIDE_PRIVATE_NAMES = True    # ne jamais afficher le nom d'un repo privé dans le SVG public
ACCENT = "#00babc"  # teal 42

# ═════════════════════════════════════════════════════════════ chemins / thème
ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "assets" / "neofetch.svg"

FS, CW = 14, 8.4          # taille de police, largeur d'un caractère (0,6 em)
LH_LOGO = FS * 1.32       # interligne qui fait se toucher les blocs du logo
LH = 21                   # interligne standard
X0 = 28
W = 960
HEAT = ["#161b22", "#0a4446", "#057a7c", "#00b3b5", "#5cf2f4"]
FG, DIM, MUTED, WHITE = "#c9d1d9", "#6e7681", "#8b949e", "#e6edf3"
GREEN, BLUE, RED = "#3fb950", "#58a6ff", "#ff5d5d"

LOGO = [
    "██╗   ██╗ █████╗ ██╗   ██╗██╗  ██╗ ██████╗ ",
    "██║   ██║██╔══██╗╚██╗ ██╔╝██║ ██╔╝██╔═══██╗",
    "██║   ██║███████║ ╚████╔╝ █████╔╝ ██║   ██║",
    "╚██╗ ██╔╝██╔══██║  ╚██╔╝  ██╔═██╗ ██║   ██║",
    " ╚████╔╝ ██║  ██║   ██║   ██║  ██╗╚██████╔╝",
    "  ╚═══╝  ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ",
]
LOGO_GRAD = ["#00babc", "#09b4c8", "#1aaad6", "#2f9fe2", "#4594ee", "#58a6ff"]


# ═════════════════════════════════════════════════════════════ données
def http_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


QUERY_USER = """
query($login: String!) {
  user(login: $login) {
    createdAt
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount contributionLevel date } }
      }
    }
  }
}"""
QUERY_REPOS = """
query($login: String!, $after: String, $isFork: Boolean, $privacy: RepositoryPrivacy) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: $isFork, privacy: $privacy, first: 100,
                 after: $after, orderBy: {field: PUSHED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name isFork isPrivate stargazerCount pushedAt
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
         "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def gql(token, query, variables):
    res = http_json(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "neofetch-readme"},
    )
    if "errors" in res:
        raise SystemExit(f"Erreur GraphQL : {res['errors']}")
    return res["data"]


def fetch_github(login, token):
    u = gql(token, QUERY_USER, {"login": login})["user"]

    repos, after = [], None
    while True:  # pagination (plus de 100 repos)
        page = gql(token, QUERY_REPOS, {
            "login": login, "after": after,
            "isFork": None if INCLUDE_FORKS else False,
            "privacy": None if INCLUDE_PRIVATE else "PUBLIC",
        })["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    if INCLUDE_PRIVATE and not any(r["isPrivate"] for r in repos):
        print("⚠ aucun repo privé visible : le token n'a sans doute pas accès à tes repos privés",
              file=sys.stderr)

    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            if n in EXCLUDED_LANGS:
                continue
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or MUTED
    total = sum(sizes.values()) or 1
    langs = [(n, sz / total, colors[n])
             for n, sz in sorted(sizes.items(), key=lambda kv: -kv[1])[:TOP_LANGS]]

    # dernier repo poussé, hors repo de profil (mis à jour chaque nuit par l'Action)
    last = next((r for r in repos if r["name"].lower() != login.lower()), None)
    last_name = None
    if last:
        last_name = ("un repo privé" if last["isPrivate"] and HIDE_PRIVATE_NAMES else last["name"])
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["contributionCount"], LEVEL[d["contributionLevel"]], d["date"])
              for d in w["contributionDays"]] for w in cal["weeks"]]
    return {
        "login": login,
        "since": int(u["createdAt"][:4]),
        "repos": len(repos),
        "private": sum(r["isPrivate"] for r in repos),
        "forks": sum(r["isFork"] for r in repos),
        "stars": sum(r["stargazerCount"] for r in repos),
        "total": cal["totalContributions"],
        "weeks": weeks,
        "langs": langs,
        "last": (last_name, parse_date(last["pushedAt"])) if last else None,
    }


def demo_data():
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday() + 1 + 52 * 7)
    weeks, total = [], 0
    for w in range(53):
        col = []
        for d in range(7):
            day = start + dt.timedelta(days=w * 7 + d)
            if day > today:
                break
            busy = 0.35 + 0.5 * (w / 52)
            c = 0 if rnd.random() > busy else rnd.choice([1, 1, 2, 3, 4, 6, 9, 13])
            total += c
            lvl = 0 if c == 0 else 1 if c < 3 else 2 if c < 5 else 3 if c < 9 else 4
            col.append((c, lvl, day.isoformat()))
        weeks.append(col)
    flat = [(wi, di) for wi, w in enumerate(weeks) for di in range(len(w))]
    for wi, di in flat[-6:]:  # une petite série en cours
        c = rnd.choice([2, 3, 5])
        total += c - weeks[wi][di][0]
        weeks[wi][di] = (c, 2, weeks[wi][di][2])
    return {
        "login": "nicoco23", "since": 2021, "repos": 31, "private": 8, "forks": 5, "stars": 41, "total": total,
        "weeks": weeks,
        "langs": [("TypeScript", .38, "#3178c6"), ("Java", .24, "#b07219"),
                  ("C", .17, "#555555"), ("JavaScript", .12, "#f1e05a"),
                  ("C++", .09, "#f34b7d")],
        "last": ("ChooseMyCocktail", dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)),
    }


def parse_date(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def ago(when):
    days = (dt.datetime.now(dt.timezone.utc) - when).days
    if days <= 0:
        return "aujourd'hui"
    if days == 1:
        return "hier"
    if days < 31:
        return f"il y a {days} j"
    if days < 365:
        return f"il y a {days // 30} mois"
    return f"il y a {days // 365} an{'s' if days >= 730 else ''}"


def streak(weeks):
    days = [d for w in weeks for d in w]
    if days and days[-1][0] == 0:  # aujourd'hui pas encore commencé : on part d'hier
        days = days[:-1]
    n = 0
    for c, _, _ in reversed(days):
        if c == 0:
            break
        n += 1
    return n


# ═════════════════════════════════════════════════════════════ rendu SVG
class Svg:
    def __init__(self, seed=3):
        self.els, self.rnd = [], random.Random(seed)
        self.cursor_css, self.cid = [], 0

    def add(self, s):
        self.els.append(s)

    def text(self, x, y, inner, t=None, anim="up .35s ease-out", cls="", fill=None):
        st = f' style="animation:{anim} {t:.2f}s both"' if t is not None else ""
        c = f' class="{cls}"' if cls else ""
        f = f' fill="{fill}"' if fill else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}"{c}{f}{st}>{inner}</text>')

    def prompt(self, y, t):
        self.text(X0, y, f'<tspan fill="{GREEN}" font-weight="700">nico@42paris</tspan>'
                         f'<tspan fill="{FG}">:</tspan><tspan fill="{BLUE}">~</tspan>'
                         f'<tspan fill="{FG}">$</tspan>', t, anim="in 0s")

    def typed(self, y, t, cmd, typo=None):
        """Tape `cmd` caractère par caractère à partir de t, avec une faute optionnelle :
        typo=(index, faux_texte) → tape faux_texte à l'index, l'efface, puis continue."""
        self.prompt(y, t)
        t += 0.45
        col0 = 16
        chars, events, col = [], [(t, col0)], col0

        def key(ch):
            nonlocal t, col
            chars.append([col, ch, t, None])
            col += 1
            events.append((t, col))
            t += self.rnd.uniform(0.045, 0.13) + (0.12 if ch == " " else 0)

        def back():
            nonlocal t, col
            for c in reversed(chars):
                if c[3] is None:
                    c[3] = t
                    break
            col -= 1
            events.append((t, col))
            t += 0.07

        for i, ch in enumerate(cmd):
            if typo and i == typo[0]:
                for w in typo[1]:
                    key(w)
                t += 0.35
                for _ in typo[1]:
                    back()
                t += 0.1
            key(ch)
        t_end = t + 0.35

        for col, ch, ts, th in chars:
            anim = f"in 0s {ts:.2f}s both" + (f",out 0s {th:.2f}s forwards" if th else "")
            self.add(f'<text x="{X0 + col * CW:.1f}" y="{y}" fill="{WHITE}" '
                     f'style="animation:{anim}">{escape(ch)}</text>')

        # curseur qui suit la frappe
        self.cid += 1
        name, t0, dur = f"c{self.cid}", events[0][0], t_end - events[0][0]
        frames = "".join(f"{(e - t0) / dur * 100:.2f}%{{transform:translateX({(c - col0) * CW:.1f}px)}}"
                         for e, c in events)
        self.cursor_css.append(f"@keyframes {name}{{{frames}100%{{transform:translateX({(col - col0) * CW:.1f}px)}}}}")
        self.add(f'<rect x="{X0 + col0 * CW:.1f}" y="{y - 13}" width="{CW:.1f}" height="17" fill="{ACCENT}" '
                 f'style="animation:in 0s {t0:.2f}s both,{name} {dur:.2f}s step-end {t0:.2f}s both,'
                 f'out 0s {t_end:.2f}s forwards"/>')
        return t_end

    def idle_cursor(self, y, t):
        self.prompt(y, t)
        self.add(f'<rect x="{X0 + 16 * CW:.1f}" y="{y - 13}" width="{CW:.1f}" height="17" fill="{ACCENT}" '
                 f'style="animation:in 0s {t:.2f}s both,blink 1.1s step-end {t:.2f}s infinite"/>')


def kv(label, value_svg):
    return (f'<tspan fill="{ACCENT}" font-weight="700">{escape(label):<9}</tspan>'
            f'<tspan fill="{FG}"> {value_svg}</tspan>')


def build(d, now):
    s = Svg()

    # ── 1. neofetch ────────────────────────────────────────────
    y = 72
    t = s.typed(y, 0.3, "neofetch", typo=(5, "ce"))   # « neofce » → corrigé en « neofetch »
    ytop = y + 34
    for i, row in enumerate(LOGO):
        s.text(X0, ytop + 14 + i * LH_LOGO, escape(row), t + i * 0.06,
               anim="in .25s ease-out", cls="logo", fill=LOGO_GRAD[i])
    ysub = ytop + 14 + len(LOGO) * LH_LOGO + 16
    s.text(X0, ysub, f'<tspan fill="{DIM}">&gt; sur GitHub depuis {d["since"]} · </tspan>'
                     f'<tspan fill="{MUTED}">@{escape(d["login"])}</tspan>', t + 0.45)

    xi = X0 + 47 * CW
    info = [
        f'<tspan fill="{ACCENT}" font-weight="700">nico</tspan><tspan fill="{FG}">@</tspan>'
        f'<tspan fill="{ACCENT}" font-weight="700">42paris</tspan>',
        f'<tspan fill="#30363d">{"─" * 30}</tspan>',
    ]
    info += [kv(a, escape(b)) for a, b in INFO_STATIC]
    extra = [x for x in (f'{d.get("private", 0)} privés' if d.get("private") else "",
                         f'{d.get("forks", 0)} forks' if d.get("forks") else "") if x]
    info.append(kv("Repos", f'{d["repos"]} repos'
                            + (f' <tspan fill="{MUTED}">({", ".join(extra)})</tspan>' if extra else "")
                            + f' · {d["stars"]} étoiles'))
    stk = streak(d["weeks"])
    info.append(kv("Activité", f'{d["total"]} contributions / an'
                               + (f' · série <tspan fill="{WHITE}" font-weight="700">{stk} j</tspan>' if stk >= 2 else "")))
    if d["last"]:
        info.append(kv("Dernier", f'<tspan fill="{WHITE}">{escape(d["last"][0])}</tspan>'
                                  f'<tspan fill="{MUTED}"> · {ago(d["last"][1])}</tspan>'))
    for i, line in enumerate(info):
        s.text(xi, ytop + 14 + i * LH, line, t + 0.15 + i * 0.09)
    yb = ytop + 14 + len(info) * LH - 6
    tb = t + 0.15 + len(info) * 0.09
    sw = ["#484f58", "#ff7b72", GREEN, "#d29922", BLUE, "#bc8cff", ACCENT, WHITE]
    s.add(f'<g style="animation:up .35s ease-out {tb:.2f}s both">' + "".join(
        f'<rect x="{xi + i * 26:.1f}" y="{yb}" width="24" height="12" rx="2" fill="{c}"/>'
        for i, c in enumerate(sw)) + "</g>")
    t = tb + 0.6

    # ── 2. stats : heatmap + langages ─────────────────────────
    y = max(ysub, yb + 12) + 44
    t = s.typed(y, t, "stats --year")
    cell, gap = 10, 2.5
    hx, hy = X0, y + 36
    # mois au-dessus de la heatmap
    mois = "janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.".split()
    last_m = None
    for wi, wk in enumerate(d["weeks"]):
        if not wk:
            continue
        m = int(wk[0][2][5:7])
        if m != last_m and wi < len(d["weeks"]) - 2:
            if last_m is not None:
                s.text(hx + wi * (cell + gap), hy - 8, f'<tspan fill="{DIM}">{mois[m - 1]}</tspan>',
                       t + 0.1, anim="in .3s", cls="sm")
            last_m = m
    for wi, wk in enumerate(d["weeks"]):
        rects = "".join(
            f'<rect x="{hx + wi * (cell + gap):.1f}" y="{hy + di * (cell + gap):.1f}" width="{cell}" '
            f'height="{cell}" rx="2" fill="{HEAT[lvl]}"><title>{c} le {date}</title></rect>'
            for di, (c, lvl, date) in enumerate(wk))
        s.add(f'<g style="animation:pop .3s ease-out {t + 0.1 + wi * 0.022:.2f}s both">{rects}</g>')
    yl = hy + 7 * (cell + gap) + 18
    tl = t + 0.1 + len(d["weeks"]) * 0.022
    legend = "".join(f'<rect x="{hx + 528 + i * 14}" y="{yl - 10}" width="10" height="10" rx="2" fill="{c}"/>'
                     for i, c in enumerate(HEAT))
    s.add(f'<g style="animation:in .4s {tl:.2f}s both">{legend}'
          f'<text x="{hx + 486}" y="{yl}" class="sm" fill="{DIM}">Less</text>'
          f'<text x="{hx + 602}" y="{yl}" class="sm" fill="{DIM}">More</text></g>')
    s.text(hx, yl, f'<tspan fill="{WHITE}" font-weight="700">{d["total"]}</tspan>'
                   f'<tspan fill="{MUTED}"> contributions sur les 12 derniers mois</tspan>', tl, cls="sm")

    lx = hx + 53 * (cell + gap) + 30
    s.text(lx, hy - 8, f'<tspan fill="{DIM}">langages</tspan>', t + 0.1, anim="in .3s", cls="sm")
    bar_w = W - 28 - (lx + 11 * CW) - 44
    for i, (name, pct, color) in enumerate(d["langs"]):
        yy = hy + 9 + i * 18.5
        ti = t + 0.3 + i * 0.12
        s.text(lx, yy, f'<tspan fill="{FG}">{escape(name[:10])}</tspan>', ti, cls="sm")
        bx = lx + 11 * CW
        s.add(f'<rect x="{bx:.1f}" y="{yy - 8}" width="{bar_w:.1f}" height="8" rx="2" fill="#161b22" '
              f'style="animation:in .3s {ti:.2f}s both"/>')
        s.add(f'<rect x="{bx:.1f}" y="{yy - 8}" width="{max(bar_w * pct / d["langs"][0][1], 3):.1f}" height="8" '
              f'rx="2" fill="{color}" class="bar" style="animation:grow .9s cubic-bezier(.2,.8,.2,1) {ti:.2f}s both"/>')
        s.text(bx + bar_w + 6, yy, f'<tspan fill="{MUTED}">{round(pct * 100)}%</tspan>', ti + 0.4, cls="sm")
    t = max(tl, t + 0.3 + len(d["langs"]) * 0.12) + 0.7

    # ── 3. prompt final ───────────────────────────────────────
    y = yl + 46
    s.idle_cursor(y, t)
    H = int(y + 28)

    return window(W, H, s.els, s.cursor_css, label="nico@42paris — neofetch", now=now)


def font_face_css():
    css = ""
    for w, f in ((400, "JBM-Regular.woff2"), (700, "JBM-Bold.woff2")):
        b64 = base64.b64encode((FONTS / f).read_bytes()).decode()
        css += (f"@font-face{{font-family:JBM;font-weight:{w};"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}\n")
    return css


def stamp_paris(now):
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y · %H:%M")
    except Exception:
        return now.strftime("%d/%m/%Y · %H:%M UTC")


def window(w, h, els, extra_css=(), label="", title="nico@42paris: ~ — zsh",
           now=None, bar=36, extra_style=""):
    """Habille un contenu SVG dans une fenêtre de terminal (police, CRT, barre de titre)."""
    r = 6 if bar >= 36 else 5
    cy = bar / 2 + 0.5
    right = (f'<text x="{w - 18}" y="{cy + 4.5:.1f}" text-anchor="end" class="sm" fill="{DIM}">'
             f'maj {stamp_paris(now)}</text>') if now else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
<title>{escape(label)}</title>
<defs>
  <filter id="glow" x="-5%" y="-20%" width="110%" height="140%">
    <feGaussianBlur stdDeviation="1.6" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#ffffff" opacity=".018"/>
  </pattern>
  <radialGradient id="vig" cx="50%" cy="45%" r="75%">
    <stop offset="60%" stop-color="#000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000" stop-opacity=".35"/>
  </radialGradient>
  <linearGradient id="vert" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0" stop-color="#00babc"/><stop offset="1" stop-color="#58a6ff"/>
  </linearGradient>
  <clipPath id="win"><rect width="{w}" height="{h}" rx="12"/></clipPath>
</defs>
<style>
{font_face_css()}text{{font-family:JBM,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:{FS}px;white-space:pre}}
.sm{{font-size:11.5px}}
.logo{{font-weight:700;filter:url(#glow)}}
.bar{{transform-box:fill-box;transform-origin:left center}}
@keyframes in{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes out{{from{{opacity:1}}to{{opacity:0}}}}
@keyframes up{{from{{opacity:0;transform:translateY(5px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes blink{{0%,55%{{opacity:1}}56%,100%{{opacity:0}}}}
{extra_style}
{chr(10).join(extra_css)}
</style>
<g clip-path="url(#win)" fill="{FG}">
<rect width="{w}" height="{h}" fill="#0d1117"/>
<rect width="{w}" height="{bar}" fill="#161b22"/>
<line x1="0" y1="{bar + .5}" x2="{w}" y2="{bar + .5}" stroke="#30363d"/>
<circle cx="{r + 16}" cy="{cy}" r="{r}" fill="#ff5f56"/><circle cx="{3 * r + 24}" cy="{cy}" r="{r}" fill="#ffbd2e"/><circle cx="{5 * r + 32}" cy="{cy}" r="{r}" fill="#27c93f"/>
<text x="{w / 2}" y="{cy + 4.5:.1f}" text-anchor="middle" class="sm" fill="{MUTED}">{escape(title)}</text>
{right}
{chr(10).join(els)}
<rect y="{bar + 1}" width="{w}" height="{h - bar - 1}" fill="url(#scan)" pointer-events="none"/>
<rect y="{bar + 1}" width="{w}" height="{h - bar - 1}" fill="url(#vig)" pointer-events="none"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="#30363d"/>
</svg>'''


def main():
    now = dt.datetime.now(dt.timezone.utc)
    if "--demo" in sys.argv:
        d = demo_data()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        login = os.environ.get("GH_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER")
        if not token or not login:
            raise SystemExit("GITHUB_TOKEN et GH_LOGIN requis (ou lance avec --demo)")
        d = fetch_github(login, token)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(d, now), encoding="utf-8")
    print(f"✓ {OUT.relative_to(ROOT)} généré")


if __name__ == "__main__":
    main()
