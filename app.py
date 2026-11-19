"""
TGV Cinema — Film Programming UI review (Streamlit edition)
-----------------------------------------------------------
Same rule as the standalone review bundle:

    sign in first -> one Creator publishes the Vista titles
                  -> Programmers and Viewers use those titles

Run:
    streamlit run app.py
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
VIEWS = ROOT / "static"
STATIC_URL = "/app/static"
FEEDBACK = ROOT / "feedback.csv"
SHARED = ROOT / "shared_titles.json"

FIELDS = ["when", "reviewer", "view", "rating", "verdict", "works", "missing"]

EXPS = [
    {"name": "Standard 2D", "code": "2D", "color": "#334155"},
    {"name": "IMAX", "code": "IMAX2D", "color": "#E4002B"},
    {"name": "Deluxe", "code": "DELUXE", "color": "#1F5FA8"},
    {"name": "Beanie", "code": "BEANIE", "color": "#7C4DBE"},
    {"name": "Junior", "code": "JUNIOR", "color": "#96600A"},
    {"name": "Indulge", "code": "INDULGE", "color": "#12734A"},
]
EXP_LABELS = [f"{e['name']} [{e['code']}]" for e in EXPS]

CONCEPTS = [
    {
        "file": "5-createfilm.html",
        "name": "Create Film",
        "tone": "Light",
        "tag": "Title request · experiences · Vista codes",
        "blurb": (
            "Sign in first. Only the Creator raises the title request: name the film, tick the "
            "experiences, and publish one Vista title per experience. Everyone else signs in and "
            "uses those titles — no second title request."
        ),
        "look": [
            "Does the role gate make sense — Creator publishes, others reuse?",
            "Does [IMAX2D] DOOMSDAY / [BEANIE] DOOMSDAY read like Vista?",
            "Is the shared slate obvious enough on the later concepts?",
        ],
    },
    {
        "file": "1-ai-console.html",
        "name": "Showtime Manager",
        "tone": "Dark",
        "tag": "Posters · overall ratings · INDEX · approval",
        "blurb": (
            "Film rating first, then the location-first showtime manager, then approval. The "
            "published Vista titles are already in the slate for every signed-in user."
        ),
        "look": [
            "Does the shared title appear in the picker without any setup?",
            "Is the consensus rating easy to find?",
            "Does approval still feel gated enough?",
        ],
    },
    {
        "file": "2-programmer.html",
        "name": "Programmer",
        "tone": "Light",
        "tag": "Closest to Screen Schedule",
        "blurb": (
            "Pick a film, read the dossier, score it, see the forecast, get the schedule. "
            "The light editorial skin mimics the Screen Schedule grid you already use."
        ),
        "look": [
            "Does the dossier give you enough before you score?",
            "Is the schedule grid faithful to the real one?",
            "Can you find the creator's title quickly?",
        ],
    },
    {
        "file": "3-simple.html",
        "name": "AI Console, simplified",
        "tone": "Light",
        "tag": "5-star score · 24h · switch sessions",
        "blurb": (
            "Your score and comparables on the left, your own rules in the middle, an editable "
            "schedule on the right. Five-star scoring and a full 24-hour day."
        ),
        "look": [
            "Is the five-star rating clearer than the INDEX?",
            "Does swapping sessions by drag / arrow feel safe?",
            "Is 24 hours too wide for a normal planning view?",
        ],
    },
    {
        "file": "4-week.html",
        "name": "Week Planner",
        "tone": "Light",
        "tag": "Vista titles · team ratings · 5-star · 24h",
        "blurb": (
            "Whole-week slate, team ratings, drag-to-swap schedule and exports. The shell sign-in "
            "is inherited here, so you do not log in twice inside the review."
        ),
        "look": [
            "Do all four programmers' scores read clearly?",
            "Is the week board readable at a glance?",
            "Any duplicate sign-in or title setup still visible?",
        ],
    },
]
CONCEPT_BY_FILE = {c["file"]: c for c in CONCEPTS}

RATINGS = {
    1: "1 — Not usable",
    2: "2 — Needs rework",
    3: "3 — Workable",
    4: "4 — Good, small fixes",
    5: "5 — Ship it",
}


# --------------------------------------------------------------------------
# shared slate (server-side so every Streamlit user sees the same titles)
# --------------------------------------------------------------------------
def load_titles() -> list[dict]:
    try:
        data = json.loads(SHARED.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        pass
    # in-memory fallback when the sandbox filesystem is read-only
    return st.session_state.get("_titles_mem", [])


def save_titles(rows: list[dict]) -> None:
    st.session_state["_titles_mem"] = rows
    try:
        SHARED.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        st.session_state["_titles_ram_only"] = True


# --------------------------------------------------------------------------
# sign-in gate — first screen, before any concept
# --------------------------------------------------------------------------
def login_gate() -> None:
    if st.session_state.get("user"):
        return

    st.markdown(
        """
        <style>
          [data-testid="stHeader"],
          [data-testid="stSidebar"],
          [data-testid="stMainMenu"] { display:none !important; }
          .block-container{padding:0 !important;max-width:100% !important}
          [data-testid="stAppViewContainer"]{background:#F2F2F7 !important}

          .lg-wrap{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",
            Roboto,Helvetica,Arial,sans-serif;color:#1C1C1E}
          .lg-hero{background:#E4002B;color:#fff;padding:42px 26px 86px;
            border-radius:0 0 30px 30px;box-shadow:0 12px 34px rgba(228,0,43,.22)}
          .lg-hero .bd{display:inline-flex;align-items:center;gap:8px;font-size:11px;
            font-weight:700;letter-spacing:1.4px;background:rgba(255,255,255,.16);
            border:1px solid rgba(255,255,255,.28);border-radius:20px;padding:5px 11px}
          .lg-hero .bd i{width:7px;height:7px;border-radius:50%;background:#fff;display:block}
          .lg-hero h1{font-size:34px;line-height:1.08;letter-spacing:-1px;
            margin:18px 0 8px;font-weight:700}
          .lg-hero p{font-size:13.5px;line-height:1.55;color:rgba(255,255,255,.88);
            margin:0;max-width:430px}

          [data-testid="stForm"]{max-width:560px;margin:-58px auto 0;background:#fff;
            border:1px solid rgba(60,60,67,.08);border-radius:20px;padding:18px 20px 20px;
            box-shadow:0 14px 40px rgba(0,0,0,.12);position:relative;z-index:2}
          [data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:0 !important}
          [data-testid="stForm"] [data-testid="stVerticalBlock"] > div{
            padding:10px 2px;border-bottom:1px solid #E5E5EA}
          [data-testid="stForm"] [data-testid="stVerticalBlock"] > div:last-child{
            border-bottom:none}
          [data-testid="stTextInput"] label,
          [data-testid="stSelectbox"] label{font-size:11px !important;font-weight:600 !important;
            color:#6E6E73 !important;letter-spacing:.2px !important;padding-bottom:2px !important}
          [data-testid="stTextInput"] input{background:transparent !important;border:none !important;
            box-shadow:none !important;color:#1C1C1E !important;font-size:15px !important;
            padding:2px 0 !important;min-height:28px !important}
          [data-testid="stTextInputRootElement"]{background:transparent !important;
            border:none !important;box-shadow:none !important}
          [data-testid="stSelectbox"] > div[data-baseweb="select"] > div{
            background:transparent !important;border:none !important;box-shadow:none !important;
            color:#1C1C1E !important;font-size:15px !important;min-height:28px !important;
            padding:0 !important}
          [data-testid="stSelectbox"] svg{color:#E4002B !important}
          [data-testid="stFormSubmitButton"],
          [data-testid="stFormSubmitButton"] > div{width:100% !important;display:block !important}
          [data-testid="stFormSubmitButton"] button,
          [data-testid="stBaseButton-primaryFormSubmit"]{width:100% !important;
            box-sizing:border-box !important;display:block !important;height:48px !important;
            background:#E4002B !important;color:#fff !important;border-radius:14px !important;
            font-size:15px !important;font-weight:600 !important;border:none !important;
            box-shadow:0 8px 20px rgba(228,0,43,.28) !important;margin-top:14px !important}
          [data-testid="stAlert"]{border-radius:14px !important;margin:14px auto 0 !important;
            max-width:560px !important}
          .lg-foot{max-width:560px;margin:16px auto 24px;text-align:center;color:#6E6E73;
            font-size:11.5px;line-height:1.6;font-family:-apple-system,BlinkMacSystemFont,
            "Segoe UI",sans-serif}
          .lg-foot b{color:#E4002B}
          @media(max-width:620px){
            .lg-hero{padding:34px 20px 78px;border-radius:0 0 24px 24px}
            .lg-hero h1{font-size:29px}
            [data-testid="stForm"]{margin:-52px 14px 0;padding:16px}
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="lg-wrap">
          <div class="lg-hero">
            <span class="bd"><i></i>TGV CINEMAS</span>
            <h1>Sign in.</h1>
            <p>One Creator raises the Vista titles. Everyone else works from the same slate —
               no duplicate requests.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("tgv_login", clear_on_submit=False):
        email = st.text_input("Work email", value="creator@tgv.com.my")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["Creator", "Programmer", "Viewer"])
        go = st.form_submit_button("Sign in →", type="primary")

    st.markdown(
        '<div class="lg-foot"><b>Creator</b> publishes · <b>Programmer</b> rates &amp; '
        "schedules · <b>Viewer</b> reads the plan</div>",
        unsafe_allow_html=True,
    )

    try:
        extra = st.secrets.get("APP_PASSWORD")
    except Exception:
        extra = None

    if go:
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email.strip()):
            st.error("Enter a valid TGV staff email address.")
        elif len(password) < 4:
            st.error("Password must be at least 4 characters.")
        elif extra and password != extra:
            st.error("Wrong password.")
        else:
            name = (
                email.split("@")[0]
                .replace(".", " ")
                .replace("_", " ")
                .replace("-", " ")
                .title()
            )
            st.session_state["user"] = {
                "name": name,
                "email": email.strip(),
                "role": role,
            }
            st.rerun()
    st.stop()


# --------------------------------------------------------------------------
# feedback helpers
# --------------------------------------------------------------------------
def _disk_ok() -> bool:
    try:
        FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
        probe = FEEDBACK.parent / ".write-probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def load_feedback() -> list[dict]:
    rows: list[dict] = []
    if FEEDBACK.exists():
        with FEEDBACK.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    seen = {(r.get("when"), r.get("reviewer"), r.get("works")) for r in rows}
    for r in st.session_state.get("notes_mem", []):
        if (r["when"], r["reviewer"], r["works"]) not in seen:
            rows.append(r)
    return rows


def save_feedback(row: dict) -> None:
    st.session_state.setdefault("notes_mem", []).append(row)
    if not _disk_ok():
        return
    new = not FEEDBACK.exists()
    with FEEDBACK.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


# --------------------------------------------------------------------------
# create film — only the Creator can publish to the shared slate
# --------------------------------------------------------------------------
def create_film_panel(user: dict, titles: list[dict]) -> None:
    if user["role"] != "Creator":
        st.info(
            f"Signed in as {user['role']}. Title requests are raised once by the Creator; "
            "you can use the shared titles below without creating anything."
        )
        return

    st.markdown("#### Native form · publish a Vista title")
    with st.form("create_film", clear_on_submit=True):
        film = st.text_input("Film name", value="Doomsday")
        c1, c2 = st.columns(2)
        dist = c1.text_input("Distributor", value="Universal Pictures")
        genre = c2.selectbox(
            "Genre",
            ["Action · Thriller", "Action · Adventure", "Horror", "Drama",
             "Comedy", "Romance", "Animation · Family"],
        )
        c3, c4 = st.columns(2)
        lang = c3.selectbox(
            "Language", ["English", "Malay", "Tamil", "Mandarin", "Punjabi"]
        )
        cert = c4.selectbox("Certification", ["P13", "13", "16", "18", "U"])
        c5, c6 = st.columns(2)
        mins = c5.number_input("Runtime (min)", min_value=40, max_value=300, value=128)
        release = c6.date_input("Release date", value=datetime(2026, 11, 12).date())
        picked = st.multiselect(
            "Experiences", EXP_LABELS,
            default=["IMAX [IMAX2D]", "Beanie [BEANIE]"],
        )
        publish = st.form_submit_button("Create Vista titles →", type="primary")

    if not publish:
        return
    if not film.strip():
        st.error("Enter a film name first.")
        return
    if not picked:
        st.error("Tick at least one experience.")
        return

    codes = [e["code"] for e in EXPS if f"{e['name']} [{e['code']}]" in picked]
    existing = {t["title"] for t in titles}
    made: list[dict] = []
    for code in codes:
        title = f"[{code}] {film.strip().upper()}"
        if title in existing:
            continue
        exp = next(e for e in EXPS if e["code"] == code)
        made.append({
            "id": f"t{int(datetime.now().timestamp())}-{code}-{len(made)}",
            "title": title,
            "code": code,
            "expName": exp["name"],
            "color": exp["color"],
            "name": film.strip(),
            "dist": dist,
            "genre": genre,
            "lang": lang,
            "mins": int(mins),
            "cert": cert,
            "release": str(release),
            "by": user["name"],
        })
        existing.add(title)

    if made:
        save_titles(titles + made)
        st.success(f"Published {len(made)} title(s). Everyone can use them now.")
        st.rerun()
    else:
        st.warning("Those titles already exist in the shared slate.")


def render_slate(titles: list[dict]) -> None:
    if not titles:
        st.info("No Vista titles yet. Sign in as Creator in Create Film to publish the first ones.")
        return
    chips = " ".join(
        f'<span style="display:inline-block;background:#fff;border:1px solid #E2DED7;'
        f'border-radius:20px;padding:3px 10px;margin:0 6px 6px 0;font-size:11.5px;'
        f'font-weight:600;color:#3B352C">{t["title"]}</span>'
        for t in titles
    )
    st.markdown(
        f'<div style="background:#FAF8F5;border:1px solid #E2DED7;border-radius:9px;'
        f'padding:10px 12px;margin-bottom:12px">'
        f'<b style="font-size:9.5px;letter-spacing:.7px;color:#E4002B">SHARED SLATE</b>'
        f'<div style="margin-top:6px">{chips}</div>'
        f'<div style="font-size:10.5px;color:#8B8377;margin-top:4px">'
        f'created by {titles[0].get("by", "Creator")} · {len(titles)} title(s) ready for everyone'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def inject_shared(html: str, user: dict, titles: list[dict]) -> str:
    """Seed the embedded prototype with the shell session and shared titles."""
    js_user = json.dumps(json.dumps(user))
    js_titles = json.dumps(json.dumps(titles))
    shim = (
        "<script>try{"
        f"localStorage.setItem('tgv.user',{js_user});"
        f"localStorage.setItem('tgv.createfilm.titles',{js_titles});"
        "}catch(e){}</script>"
    )
    return html.replace("<head>", "<head>" + shim, 1)


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="TGV Programming — UI review",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

login_gate()
user = st.session_state["user"]
titles = load_titles()

st.markdown(
    """
    <style>
      .block-container{padding-top:1.6rem;padding-bottom:2rem;max-width:100%}
      header[data-testid="stHeader"]{background:transparent}
      .tgv-hd{display:flex;align-items:baseline;gap:12px;margin-bottom:2px}
      .tgv-hd .mk{background:#E4002B;color:#fff;font-weight:800;font-size:11px;
        letter-spacing:.4px;padding:4px 7px;border-radius:5px}
      .tgv-hd h1{font-size:22px;margin:0;letter-spacing:-.2px;color:#14110E}
      .tgv-sub{color:#6E675C;font-size:12.5px;margin-bottom:14px}
      .tgv-tag{display:inline-block;font-size:10.5px;font-weight:600;padding:2px 8px;
        border-radius:20px;background:#fff;border:1px solid #E2DED7;color:#6E675C;margin-right:6px}
      .tgv-tag.red{background:#FDECEF;border-color:#F7D3D9;color:#E4002B}
      .tgv-card{background:#fff;border:1px solid #E2DED7;border-radius:10px;
        padding:14px 16px;font-size:12.5px;line-height:1.6;color:#3B352C}
      .tgv-card h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;
        letter-spacing:.7px;color:#8B8377;font-weight:700}
      .tgv-card ul{margin:6px 0 0;padding-left:16px}
      .tgv-card li{margin-bottom:3px}
    </style>
    """,
    unsafe_allow_html=True,
)

head_l, head_r = st.columns([5, 1])
with head_l:
    st.markdown(
        '<div class="tgv-hd"><span class="mk">TGV</span>'
        "<h1>Film programming — UI review</h1></div>"
        '<div class="tgv-sub">Sign in once, publish the titles once, then review the same '
        "job five ways. Notes land in <code>feedback.csv</code> next to this app.</div>",
        unsafe_allow_html=True,
    )
with head_r:
    st.markdown(
        f'<div style="text-align:right;font-size:11.5px;color:#6E675C;padding-top:5px">'
        f"Signed in as <b style='color:#14110E'>{user['name']}</b><br/>{user['role']}</div>",
        unsafe_allow_html=True,
    )
    if st.button("Sign out", key="signout"):
        st.session_state.pop("user", None)
        st.rerun()

render_slate(titles)

# --------------------------------------------------------------------------
# sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Concepts")
    key = st.radio(
        "Pick a concept",
        [c["file"] for c in CONCEPTS],
        format_func=lambda f: CONCEPT_BY_FILE[f]["name"],
        label_visibility="collapsed",
    )
    meta = CONCEPT_BY_FILE[key]
    st.caption(meta["blurb"])

    with st.expander("What to look at", expanded=True):
        for q in meta["look"]:
            st.markdown(f"- {q}")

    st.divider()
    st.markdown("### Your name")
    reviewer = st.text_input(
        "Your name", value=user["name"], placeholder="e.g. Aina",
        label_visibility="collapsed",
    )
    st.caption("Used to tag your feedback.")

    st.divider()
    rows = load_feedback()
    st.metric("Notes collected", len(rows))
    if rows:
        scores = [int(r["rating"]) for r in rows if r["rating"].isdigit()]
        if scores:
            st.metric("Average rating", f"{sum(scores)/len(scores):.1f} / 5")

    with st.expander("Diagnostics"):
        import os

        st.caption(f"Streamlit {st.__version__}")
        st.caption(f"App folder: `{ROOT}`")
        st.caption(f"Shared titles file: `{SHARED.name}` — {len(titles)} title(s)")
        for f in sorted(VIEWS.glob("*.html")):
            st.caption(f"· `{f.name}` — {f.stat().st_size // 1024} KB")
        st.caption(f"CWD: `{os.getcwd()}`")
        st.caption(f"Notes file writable: **{_disk_ok()}**")

# --------------------------------------------------------------------------
# concept panel
# --------------------------------------------------------------------------
title_l, title_r = st.columns([5, 1])
with title_l:
    st.markdown(
        f'<div style="margin-bottom:8px">'
        f'<span class="tgv-tag red">{meta["name"]}</span>'
        f'<span class="tgv-tag">{meta["tone"]}</span>'
        f'<span class="tgv-tag">{meta["tag"]}</span></div>',
        unsafe_allow_html=True,
    )
with title_r:
    st.markdown(
        f'<div style="text-align:right;padding-top:2px">'
        f'<a href="{STATIC_URL}/{key}" target="_blank" '
        f'style="font-size:12px;color:#E4002B;text-decoration:none;font-weight:600">'
        f"Open full screen ↗</a></div>",
        unsafe_allow_html=True,
    )

if not (VIEWS / key).exists():
    st.error(f"`{VIEWS / key}` is missing. The `static/` folder must sit next to `app.py`.")
elif key == "5-createfilm.html":
    st.markdown(
        '<div class="tgv-card" style="border-left:4px solid #E4002B;margin-bottom:10px">'
        "<b>Designed prototype</b> — the original Create Film layout is embedded below. "
        "The native Streamlit form after it is the fallback that writes to the shared slate."
        "</div>",
        unsafe_allow_html=True,
    )
    film_html = (VIEWS / key).read_text(encoding="utf-8")
    components.html(inject_shared(film_html, user, titles), height=960, scrolling=True)

    st.markdown("### Streamlit form fallback · shared with everyone")
    create_film_panel(user, titles)
    if not titles:
        st.markdown(
            '<div class="tgv-card">No titles published yet. As Creator, fill the form above '
            "and publish the first Vista titles. Everyone else will see them immediately.</div>",
            unsafe_allow_html=True,
        )
    else:
        for t in titles:
            st.markdown(
                f'<div class="tgv-card" style="margin-bottom:8px;border-left:4px solid '
                f'{t.get("color", "#E4002B")}"><b>{t["title"]}</b><br/>'
                f'<span style="font-size:11px;color:#6E675C">'
                f'{t.get("expName", "")} · {t.get("genre", "")} · {t.get("lang", "")} · '
                f'{t.get("mins", "")}m · {t.get("cert", "")} · created by '
                f'{t.get("by", "Creator")}</span></div>',
                unsafe_allow_html=True,
            )
else:
    html = (VIEWS / key).read_text(encoding="utf-8")
    components.html(inject_shared(html, user, titles), height=820, scrolling=True)

st.caption(
    "The full-screen view is the standalone prototype. Inside this review it is seeded with "
    "your sign-in and the shared titles published by the Creator."
)

st.divider()

# --------------------------------------------------------------------------
# feedback form
# --------------------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.markdown("#### Leave a note on this concept")
    with st.form("review", clear_on_submit=True):
        c1, c2 = st.columns([1, 1])
        with c1:
            rating = st.select_slider(
                "Rating", options=list(RATINGS), value=3,
                format_func=lambda v: RATINGS[v],
            )
        with c2:
            verdict = st.radio(
                "Would you use it next week?", ["Yes", "Maybe", "No"], horizontal=True
            )
        works = st.text_area(
            "What works", placeholder="The part you would keep…", height=80
        )
        missing = st.text_area(
            "What's missing or wrong", placeholder="The part that gets in your way…",
            height=80,
        )
        sent = st.form_submit_button("Add note", type="primary")

    if sent:
        save_feedback({
            "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "reviewer": reviewer.strip() or user["name"],
            "view": meta["name"],
            "rating": rating,
            "verdict": verdict,
            "works": works.strip().replace("\n", " "),
            "missing": missing.strip().replace("\n", " "),
        })
        st.success("Saved. Switch concept and keep going.")
        st.rerun()

with right:
    st.markdown("#### How the concepts differ")
    st.markdown(
        '<div class="tgv-card">'
        "<h4>Decision each one automates</h4>"
        "<ul>"
        "<li><b>Create Film</b> — one creator publishes the Vista titles.</li>"
        "<li><b>Showtime Manager</b> — the model proposes the whole week.</li>"
        "<li><b>Programmer</b> — the model proposes, the grid stays familiar.</li>"
        "<li><b>AI Console, simplified</b> — you set the rules, the model fills gaps.</li>"
        "<li><b>Week Planner</b> — whole-week slate and team ratings.</li>"
        "</ul>"
        "<h4 style='margin-top:12px'>Shared across all concepts</h4>"
        "<ul>"
        "<li>Sign in once; role decides who may create titles.</li>"
        "<li>Created titles appear in every slate automatically.</li>"
        "<li>Score the film yourself — INDEX or five-star, depending on concept.</li>"
        "<li>Every session editable after it is planned.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

rows = load_feedback()
if rows:
    st.divider()
    st.markdown(f"#### Collected notes — {len(rows)}")
    st.dataframe(
        list(reversed(rows)),
        use_container_width=True,
        hide_index=True,
        column_config={
            "when": st.column_config.TextColumn("When", width="small"),
            "reviewer": st.column_config.TextColumn("Who", width="small"),
            "view": st.column_config.TextColumn("Concept", width="medium"),
            "rating": st.column_config.NumberColumn("Rating", width="small"),
            "verdict": st.column_config.TextColumn("Next week?", width="small"),
            "works": st.column_config.TextColumn("Works", width="large"),
            "missing": st.column_config.TextColumn("Missing", width="large"),
        },
    )
    if FEEDBACK.exists():
        st.download_button(
            "Download feedback.csv",
            FEEDBACK.read_bytes(),
            file_name="tgv-ui-review.csv",
            mime="text/csv",
        )
