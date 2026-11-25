#!/usr/bin/env python3
"""
Génère les sections sous le neofetch :
  - assets/projects/<repo>.svg  une fenêtre terminal par projet (cliquable dans le README)
  - assets/gitlog.svg           `git log` de tes derniers commits
  - assets/cava.svg             visualiseur audio façon cava (pied de page)
et met à jour le bloc de cartes du README (entre les marqueurs PROJECTS).

    python scripts/sections.py          # données réelles (GITHUB_TOKEN + GH_LOGIN)
    python scripts/sections.py --demo   # données fictives

Même configuration que neofetch.py (forks, repos privés, noms masqués).
"""
import datetime as dt
import os
import random
import re
import sys
from html import escape

from neofetch import (ACCENT, BLUE, DIM, FG, HIDE_PRIVATE_NAMES, INCLUDE_FORKS,
                      INCLUDE_PRIVATE, MUTED, ROOT, WHITE, X0, Svg, ago, gql,
                      parse_date, window)

# ═════════════════════════════════════════════════════════════ À PERSONNALISER
# (nom du repo, description à afficher ou None pour reprendre celle de GitHub)
PROJECTS = [
    ("ChooseMyCocktail", "App web d'accords mets & boissons : Next.js, Express et SQLite."),
    ("qlcplus", "Fork de QLC+ restylé façon console ChamSys MagicQ, piloté à l'Akai APC mini."),
    # ("Altiora", "App mobile de productivité gamifiée, 100 % hors ligne (React Native / Expo)."),
    # ("ft_transcendence", "Projet final du tronc commun 42 : partie authentification."),
]
GITLOG_COUNT = 6
YELLOW = "#d29922"

ASSETS = ROOT / "assets"
README = ROOT / "README.md"


# ═════════════════════════════════════════════════════════════ données
Q_REPO = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    name description url isPrivate isFork stargazerCount forkCount pushedAt
    languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
      totalSize edges { size node { name color } }
    }
  }
}"""

Q_COMMITS = """
query($login: String!, $isFork: Boolean, $privacy: RepositoryPrivacy) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: $isFork, privacy: $privacy, first: 10,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name isPrivate
        defaultBranchRef { target { ... on Commit {
          history(first: 10) { nodes {
            abbreviatedOid messageHeadline committedDate author { user { login } }
          } }
        } } }
      }
    }
  }
}"""


def fetch_projects(login, token):
    out = []
    for name, desc in PROJECTS:
        try:
            r = gql(token, Q_REPO, {"owner": login, "name": name})["repository"]
        except SystemExit as e:
            print(f"⚠ projet {name} ignoré : {e}", file=sys.stderr)
            continue
        if not r:
            print(f"⚠ projet {name} introuvable", file=sys.stderr)
            continue
        out.append(project_from_api(r, desc))
    return out


def project_from_api(r, desc):
    total = r["languages"]["totalSize"] or 1
    langs = [(e["node"]["name"], e["size"] / total, e["node"]["color"] or MUTED)
             for e in r["languages"]["edges"]]
    return {"name": r["name"], "desc": desc or r["description"] or "", "url": r["url"],
            "private": r["isPrivate"], "fork": r["isFork"], "stars": r["stargazerCount"],
            "forks": r["forkCount"], "pushed": parse_date(r["pushedAt"]), "langs": langs}


def fetch_commits(login, token):
    repos = gql(token, Q_COMMITS, {
        "login": login,
        "isFork": None if INCLUDE_FORKS else False,
        "privacy": None if INCLUDE_PRIVATE else "PUBLIC",
    })["user"]["repositories"]["nodes"]
    commits = []
    for r in repos:
        if r["name"].lower() == login.lower() or not r["defaultBranchRef"]:
            continue
        for c in r["defaultBranchRef"]["target"]["history"]["nodes"]:
            u = (c["author"] or {}).get("user") or {}
            if (u.get("login") or "").lower() != login.lower():
                continue
            hide = r["isPrivate"] and HIDE_PRIVATE_NAMES
            commits.append({
                "hash": "•••••••" if hide else c["abbreviatedOid"][:7],
                "repo": "privé" if hide else r["name"],
                "msg": "commit sur un repo privé" if hide else c["messageHeadline"],
                "date": parse_date(c["committedDate"]),
                "private": hide,
            })
    commits.sort(key=lambda c: c["date"], reverse=True)
    return commits[:GITLOG_COUNT]


def demo():
    now = dt.datetime.now(dt.timezone.utc)
    h = dt.timedelta(hours=1)
    projects = [
        {"name": "ChooseMyCocktail", "desc": PROJECTS[0][1], "url": "#", "private": False,
         "fork": False, "stars": 12, "forks": 2, "pushed": now - 20 * h,
         "langs": [("TypeScript", .62, "#3178c6"), ("JavaScript", .18, "#f1e05a"),
                   ("CSS", .14, "#563d7c"), ("HTML", .06, "#e34c26")]},
        {"name": "qlcplus", "desc": PROJECTS[1][1], "url": "#", "private": False, "fork": True,
         "stars": 3, "forks": 0, "pushed": now - 200 * h,
         "langs": [("C++", .71, "#f34b7d"), ("QML", .14, "#44a51c"), ("JavaScript", .08, "#f1e05a"),
                   ("CMake", .07, "#DA3434")]},
        {"name": "Altiora", "desc": "App mobile de productivité gamifiée, 100 % hors ligne "
                                    "(React Native / Expo).", "url": "#", "private": True,
         "fork": False, "stars": 0, "forks": 0, "pushed": now - 3 * h,
         "langs": [("TypeScript", .91, "#3178c6"), ("JavaScript", .06, "#f1e05a"), ("Kotlin", .03, "#A97BFF")]},
        {"name": "ft_transcendence", "desc": "Projet final du tronc commun 42 : partie "
                                             "authentification.", "url": "#", "private": False,
         "fork": False, "stars": 1, "forks": 0, "pushed": now - 60 * h,
         "langs": [("TypeScript", .78, "#3178c6"), ("Dockerfile", .12, "#384d54"), ("Shell", .10, "#89e051")]},
    ]
    commits = [
        {"hash": "•••••••", "repo": "privé", "msg": "commit sur un repo privé",
         "date": now - 3 * h, "private": True},
        {"hash": "a3f9c21", "repo": "ChooseMyCocktail", "msg": "feat: suggestions selon la saison",
         "date": now - 20 * h, "private": False},
        {"hash": "7be0d4e", "repo": "ChooseMyCocktail", "msg": "fix: tri des accords par score",
         "date": now - 26 * h, "private": False},
        {"hash": "e12c8aa", "repo": "ft_transcendence", "msg": "feat(auth): OAuth 42 + 2FA TOTP",
         "date": now - 60 * h, "private": False},
        {"hash": "5d0b3f7", "repo": "qlcplus", "msg": "style: palette MagicQ pour les playbacks",
         "date": now - 200 * h, "private": False},
        {"hash": "c4419e0", "repo": "qlcplus", "msg": "feat: mapping Akai APC mini mk2",
         "date": now - 230 * h, "private": False},
    ]
    wanted = [n for n, _ in PROJECTS]
    projects = [dict(p, url=f"https://github.com/nicoco23/{p['name']}")
                for p in projects if p["name"] in wanted]
    return projects, commits


def ago_fine(when):
    sec = (dt.datetime.now(dt.timezone.utc) - when).total_seconds()
    if sec < 3600:
        return f"il y a {max(int(sec // 60), 1)} min"
    if sec < 86400:
        return f"il y a {int(sec // 3600)} h"
    return ago(when)


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines


# ═════════════════════════════════════════════════════════════ carte projet
CARD_W, CARD_FS = 470, 13
CARD_CW = CARD_FS * 0.6


def card_svg(p, seed):
    rnd = random.Random(seed)
    els, x = [], 20
    t = 0.25
    # nom + étiquettes
    tags = ""
    tx = x + (len(p["name"]) * 16 * 0.6) + 10
    for label, col in (("fork", MUTED), ("privé", YELLOW)):
        if (label == "fork" and p["fork"]) or (label == "privé" and p["private"]):
            w = len(label) * 6.6 + 12
            tags += (f'<rect x="{tx:.1f}" y="47" width="{w:.1f}" height="17" rx="8.5" fill="none" '
                     f'stroke="{col}" opacity=".7"/><text x="{tx + w / 2:.1f}" y="59.5" class="xs" '
                     f'text-anchor="middle" fill="{col}">{label}</text>')
            tx += w + 6
    els.append(f'<g style="animation:up .35s ease-out {t:.2f}s both">'
               f'<text x="{x}" y="61" class="name">{escape(p["name"])}</text>{tags}</g>')
    t += 0.3

    # description tapée (2 lignes max)
    width = int((CARD_W - 2 * x) / CARD_CW)
    lines = wrap(p["desc"], width)[:2]
    if len(wrap(p["desc"], width)) > 2:
        lines[1] = lines[1][: width - 1].rstrip() + "…"
    for li, line in enumerate(lines):
        y = 86 + li * 19
        for ci, ch in enumerate(line):
            if ch != " ":
                els.append(f'<text x="{x + ci * CARD_CW:.1f}" y="{y}" class="desc" '
                           f'style="animation:in 0s {t:.3f}s both">{escape(ch)}</text>')
            t += rnd.uniform(0.008, 0.02)
    t += 0.15

    # barre de langages empilée
    by, bw = 124, CARD_W - 2 * x
    langs = p["langs"][:4]
    rest = 1 - sum(l[1] for l in langs)
    if rest > 0.01:
        langs = langs + [("autres", rest, "#30363d")]
    els.append(f'<rect x="{x}" y="{by}" width="{bw}" height="8" rx="4" fill="#161b22"/>')
    segs, cx = "", x
    for name, pct, col in langs:
        w = bw * pct
        segs += f'<rect x="{cx:.1f}" y="{by}" width="{w:.1f}" height="8" fill="{col}"/>'
        cx += w
    els.append(f'<clipPath id="bar"><rect x="{x}" y="{by}" width="{bw}" height="8" rx="4"/></clipPath>'
               f'<g clip-path="url(#bar)"><g class="bar" style="animation:grow .9s '
               f'cubic-bezier(.2,.8,.2,1) {t:.2f}s both">{segs}</g></g>')
    # légende
    lx, legend = x, ""
    for name, pct, col in langs[:4]:
        label = f"{name} {round(pct * 100)}%"
        legend += (f'<text x="{lx}" y="{by + 26}" class="xs"><tspan fill="{col}">●</tspan>'
                   f'<tspan fill="{FG}"> {escape(label)}</tspan></text>')
        lx += (len(label) + 4) * 6.6
        if lx > CARD_W - 60:
            break
    els.append(f'<g style="animation:in .4s {t + 0.3:.2f}s both">{legend}</g>')

    # pied
    foot = f'{p["stars"]} étoile{"s" if p["stars"] > 1 else ""}'
    if p["forks"]:
        foot += f' · {p["forks"]} fork{"s" if p["forks"] > 1 else ""}'
    foot += f' · maj {ago(p["pushed"])}'
    els.append(f'<text x="{x}" y="{by + 50}" class="xs" fill="{DIM}" '
               f'style="animation:in .4s {t + 0.5:.2f}s both">{escape(foot)}</text>')
    if not p["private"]:
        els.append(f'<text x="{CARD_W - x}" y="{by + 50}" class="xs" text-anchor="end" fill="{ACCENT}" '
                   f'style="animation:in .4s {t + 0.6:.2f}s both">ouvrir →</text>')

    h = by + 68
    style = (f".name{{font-size:16px;font-weight:700;fill:{ACCENT}}}"
             f".desc{{font-size:{CARD_FS}px;fill:{WHITE}}}.xs{{font-size:11px}}")
    return window(CARD_W, h, els, label=f'{p["name"]} — {p["desc"]}',
                  title=f'~/projets/{p["name"]}', bar=30, extra_style=style)


# ═════════════════════════════════════════════════════════════ git log
def gitlog_svg(commits):
    W = 960
    s = Svg(seed=11)
    y = 72
    t = s.typed(y, 0.3, f"git log --oneline -{GITLOG_COUNT}")
    max_msg = 58
    for i, c in enumerate(commits):
        yy = y + 32 + i * 24
        msg = c["msg"] if len(c["msg"]) <= max_msg else c["msg"][: max_msg - 1] + "…"
        repo = c["repo"] if len(c["repo"]) <= 18 else c["repo"][:17] + "…"
        mcol = DIM if c["private"] else WHITE
        s.text(X0, yy,
               f'<tspan fill="{ACCENT}">* </tspan><tspan fill="{YELLOW}">{escape(c["hash"])}</tspan>'
               f'<tspan fill="{BLUE}"> ({escape(repo)})</tspan>'
               f'<tspan fill="{mcol}"> {escape(msg)}</tspan>', t + i * 0.14)
        s.text(W - 28, yy, f'<tspan fill="{DIM}">{escape(ago_fine(c["date"]))}</tspan>',
               t + i * 0.14 + 0.1, cls="sm")
        s.els[-1] = s.els[-1].replace("<text ", '<text text-anchor="end" ', 1)
    if not commits:
        s.text(X0, y + 32, f'<tspan fill="{DIM}">(aucun commit récent)</tspan>', t)
    n = max(len(commits), 1)
    t += n * 0.14 + 0.5
    yf = y + 32 + n * 24 + 22
    s.idle_cursor(yf, t)
    return window(W, int(yf + 26), s.els, s.cursor_css, label="git log — derniers commits")


# ═════════════════════════════════════════════════════════════ cava
def cava_svg():
    W, rnd = 960, random.Random(5)
    s = Svg(seed=9)
    y = 72
    t = s.typed(y, 0.3, "cava")
    n, gap = 80, 3
    bw = (W - 2 * X0 - (n - 1) * gap) / n
    base, hmax = y + 86, 64
    css = []
    for i in range(n):
        x = X0 + i * (bw + gap)
        # enveloppe : plus d'énergie dans les basses, comme un vrai spectre
        env = 0.35 + 0.65 * (1 - i / n) ** 0.8
        pts = [max(0.08, min(1, env * rnd.uniform(0.25, 1.1))) for _ in range(4)]
        frames = "".join(f"{p}%{{transform:scaleY({v:.2f})}}"
                         for p, v in zip((0, 33, 66, 100), pts[:3] + [pts[0]]))
        css.append(f"@keyframes v{i}{{{frames}}}")
        s.add(f'<rect x="{x:.1f}" y="{base - hmax}" width="{bw:.1f}" height="{hmax}" fill="url(#cv)" '
              f'class="cv" style="animation:in .3s {t:.2f}s both,v{i} {rnd.uniform(.9, 1.8):.2f}s '
              f'steps(4) {t - rnd.uniform(0, 2):.2f}s infinite"/>')
    s.add(f'<text x="{X0}" y="{base + 22}" class="sm" fill="{DIM}" '
          f'style="animation:in .4s {t + .3:.2f}s both">&gt; ingé lumière · 42 paris</text>')
    css.append(".cv{transform-box:fill-box;transform-origin:50% 100%}")
    defs = (f'<linearGradient id="cv" gradientUnits="userSpaceOnUse" x1="0" y1="{base}" x2="0" '
            f'y2="{base - hmax}"><stop offset="0" stop-color="{ACCENT}"/>'
            f'<stop offset=".6" stop-color="{BLUE}"/><stop offset="1" stop-color="#bc8cff"/></linearGradient>')
    s.els.insert(0, f"<defs>{defs}</defs>")
    return window(W, int(base + 40), s.els, s.cursor_css + css, label="cava")


# ═════════════════════════════════════════════════════════════ README
def readme_block(projects):
    cells = []
    for p in projects:
        img = (f'<img src="assets/projects/{p["name"]}.svg" width="49%" '
               f'alt="{escape(p["name"])} — {escape(p["desc"])}">')
        cells.append(img if p["private"] else f'<a href="{p["url"]}">{img}</a>')
    rows = [" ".join(cells[i:i + 2]) for i in range(0, len(cells), 2)]
    return "\n".join(f'<p align="center">\n  {r}\n</p>' for r in rows)


def update_readme(projects):
    if not README.exists():
        return
    txt = README.read_text(encoding="utf-8")
    new = re.sub(r"(<!-- PROJECTS:START -->).*?(<!-- PROJECTS:END -->)",
                 lambda m: f"{m.group(1)}\n{readme_block(projects)}\n{m.group(2)}", txt, flags=re.S)
    if new != txt:
        README.write_text(new, encoding="utf-8")
        print("✓ README.md : cartes projets mises à jour")


def main():
    if "--demo" in sys.argv:
        projects, commits = demo()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        login = os.environ.get("GH_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER")
        if not token or not login:
            raise SystemExit("GITHUB_TOKEN et GH_LOGIN requis (ou lance avec --demo)")
        projects, commits = fetch_projects(login, token), fetch_commits(login, token)

    pdir = ASSETS / "projects"
    pdir.mkdir(parents=True, exist_ok=True)
    keep = set()
    for i, p in enumerate(projects):
        f = pdir / f'{p["name"]}.svg'
        f.write_text(card_svg(p, i), encoding="utf-8")
        keep.add(f.name)
    for old in pdir.glob("*.svg"):  # projets retirés de la liste
        if old.name not in keep:
            old.unlink()
    (ASSETS / "gitlog.svg").write_text(gitlog_svg(commits), encoding="utf-8")
    (ASSETS / "cava.svg").write_text(cava_svg(), encoding="utf-8")
    update_readme(projects)
    print(f"✓ {len(projects)} carte(s) projet, gitlog.svg et cava.svg générés")


if __name__ == "__main__":
    main()
