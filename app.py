import streamlit as st
import pandas as pd
import sqlite3
import requests
import os

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Filmcatalogus", layout="centered")
st.markdown("## 🎬 Filmcatalogus")

# -------------------------------------------------
# CHIP CSS
# -------------------------------------------------
st.markdown("""
<style>
.chip {
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 0.85rem;
    cursor: pointer;
    border: 1px solid #444;
    background-color: #2b2b2b;
    color: #eee;
}
.chip.active { font-weight: 700; }
.green { background:#2ecc71; }
.yellow { background:#f1c40f; color:#000; }
.orange { background:#e67e22; }
.red { background:#e74c3c; }
.blue { background:#3498db; }
.purple { background:#9b59b6; }
.gray { background:#7f8c8d; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
FILMS_DB_URL = "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/DBase-Films.db?raw=1"
MOVIEMETER_DB_URL = "https://www.dropbox.com/scl/fi/dlj5dsm3dhd5tfz1utu8w/MovieMeter_DBase.db?raw=1"
MFI_DB_URL = "https://www.dropbox.com/scl/fi/w5em79ae4t6kca7dx6ead/DBase-MFI.db?raw=1"

OMDB_KEY = st.secrets.get("OMDB_KEY", os.getenv("OMDB_KEY"))

# -------------------------------------------------
# DB helpers
# -------------------------------------------------
@st.cache_data(ttl=600)
def download_db(url, name):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    with open(name, "wb") as f:
        f.write(r.content)
    return name

@st.cache_data(ttl=600)
def load_films():
    conn = sqlite3.connect(download_db(FILMS_DB_URL, "films.db"))
    df = pd.read_sql(
        "SELECT FILM, JAAR, BEKEKEN, IMDBLINK, FILMRATING FROM tbl_DBase_Films",
        conn
    )
    conn.close()
    df["IMDB_ID"] = df["IMDBLINK"].str.extract(r"(tt\\d+)")
    df["FILM_LC"] = df["FILM"].fillna("").str.lower()
    df["RATING"] = df["FILMRATING"].fillna("").str.upper()
    return df

@st.cache_data(ttl=600)
def load_moviemeter():
    conn = sqlite3.connect(download_db(MOVIEMETER_DB_URL, "mm.db"))
    df = pd.read_sql("SELECT IMDBTT, MOVIEMETER FROM tbl_MovieMeter", conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def load_mfi():
    conn = sqlite3.connect(download_db(MFI_DB_URL, "mfi.db"))
    df = pd.read_sql("SELECT IMDBTT, UNIQUEID, MFI FROM tbl_MFI_DBase", conn)
    conn.close()
    return df

films = load_films()
moviemeter = load_moviemeter()
mfi = load_mfi()

# -------------------------------------------------
# Rating model (definitief)
# -------------------------------------------------
RATINGS = {
    "stars4":  {"label":"⭐⭐⭐⭐",  "db":["TPR"],                 "class":"green"},
    "stars3":  {"label":"⭐⭐⭐",   "db":["AFM","A-FILM"],        "class":"yellow"},
    "stars2":  {"label":"⭐⭐",    "db":["BFM","B-FILM"],        "class":"orange"},
    "stars1":  {"label":"⭐",     "db":["CFM","C-FILM"],        "class":"red"},
    "stars3p": {"label":"⭐⭐⭐+",  "db":["TPR","AFM","A-FILM"],  "class":"blue"},
    "classic": {"label":"Classic","db":["CLS"],               "class":"purple"},
    "box":     {"label":"BOX",   "db":["BOX"],               "class":"gray"}
}

# -------------------------------------------------
# URL state
# -------------------------------------------------
active_rating = st.query_params.get("rating")

# -------------------------------------------------
# Badge counts (volledige DB)
# -------------------------------------------------
badge_counts = {
    k: films[films["RATING"].isin(v["db"])]["IMDB_ID"].nunique()
    for k,v in RATINGS.items()
}

# -------------------------------------------------
# UI – chips
# -------------------------------------------------
st.markdown("### Beoordeling")
cols = st.columns(len(RATINGS))

for col, key in zip(cols, RATINGS):
    meta = RATINGS[key]
    label = f"{meta['label']} ({badge_counts[key]})"
    active = (active_rating == key)

    with col:
        if st.button(label, key=f"chip_{key}"):
            st.query_params.update({"rating": key})

        st.markdown(
            f"<div class='chip {meta['class']} {'active' if active else ''}'>{label}</div>",
            unsafe_allow_html=True
        )

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film (optioneel)")

# -------------------------------------------------
# FILTER LOGIC
# -------------------------------------------------
if not active_rating and not query:
    st.info("Zoek een film of kies een beoordeling ⭐")
    st.stop()

results = films.copy()

if active_rating:
    results = results[results["RATING"].isin(RATINGS[active_rating]["db"])]

if query:
    results = results[results["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# RENDER (volledig, per IMDb)
# -------------------------------------------------
for imdb_id, group in results.groupby("IMDB_ID", sort=False):
    row = group.iloc[0]

    st.markdown(f"### {row['FILM']} ({row['JAAR']})")

    mm = moviemeter[moviemeter["IMDBTT"] == imdb_id]
    if not mm.empty:
        st.markdown(f"_{mm.iloc[0]['MOVIEMETER'].split('*§*')[0]}_")

    mf = mfi[mfi["IMDBTT"] == imdb_id]
    for _, r in mf.iterrows():
        st.markdown(f"- {r['MFI']}")

    st.divider()
import streamlit as st
import pandas as pd
import sqlite3
import requests
import re
import os

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Filmcatalogus", layout="centered")
st.markdown("## 🎬 Filmcatalogus")

# -------------------------------------------------
# CHIP CSS (kleur + badge look)
# -------------------------------------------------
st.markdown("""
<style>
.chip-row { display:flex; gap:8px; flex-wrap:wrap; margin: 6px 0 12px 0; }
.chip {
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.85rem;
    border: 1px solid #444;
    color: #fff;
    user-select: none;
    display:inline-block;
}
.chip.active { font-weight: 700; outline: 2px solid rgba(255,255,255,0.25); }
.green { background:#2ecc71; }
.yellow { background:#f1c40f; color:#000; }
.orange { background:#e67e22; }
.red { background:#e74c3c; }
.purple { background:#9b59b6; }
.gray { background:#7f8c8d; }
.dark { background:#2b2b2b; color:#ddd; }
.smallnote { color:#9aa0a6; font-size:0.85rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# CONFIG – Dropbox raw URLs
# -------------------------------------------------
FILMS_DB_URL = (
    "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/"
    "DBase-Films.db?rlkey=6bozrymb3m6vh5llej56do1nh&raw=1"
)

MOVIEMETER_DB_URL = (
    "https://www.dropbox.com/scl/fi/dlj5dsm3dhd5tfz1utu8w/"
    "MovieMeter_DBase.db?rlkey=znjvfim8me6kzk6jbo6fqf8pl&raw=1"
)

MFI_DB_URL = (
    "https://www.dropbox.com/scl/fi/w5em79ae4t6kca7dx6ead/"
    "DBase-MFI.db?rlkey=ysfnez59g18zqhwavr7bj6tr4&raw=1"
)

OMDB_KEY = st.secrets.get("OMDB_KEY", os.getenv("OMDB_KEY"))

# -------------------------------------------------
# Download helper
# -------------------------------------------------
@st.cache_data(ttl=600)
def download_db(url, local_name):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    with open(local_name, "wb") as f:
        f.write(r.content)
    return local_name

# -------------------------------------------------
# Load databases
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_films():
    conn = sqlite3.connect(download_db(FILMS_DB_URL, "films.db"))
    df = pd.read_sql_query(
        """
        SELECT
            FILM,
            JAAR,
            BEKEKEN,
            IMDBLINK,
            FILMRATING
        FROM tbl_DBase_Films
        """,
        conn
    )
    conn.close()

    df["IMDB_ID"] = df["IMDBLINK"].str.extract(r"(tt\\d{7,9})")
    df["FILM_LC"] = df["FILM"].fillna("").str.lower()
    df["RATING_UC"] = df["FILMRATING"].fillna("").str.upper()

    return df


@st.cache_data(ttl=600)
def load_moviemeter():
    conn = sqlite3.connect(download_db(MOVIEMETER_DB_URL, "moviemeter.db"))
    df = pd.read_sql_query(
        "SELECT IMDBTT, MOVIEMETER FROM tbl_MovieMeter",
        conn
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_mfi():
    conn = sqlite3.connect(download_db(MFI_DB_URL, "mfi.db"))
    df = pd.read_sql_query(
        "SELECT IMDBTT, UNIQUEID, MFI FROM tbl_MFI_DBase",
        conn
    )
    conn.close()
    return df

# -------------------------------------------------
# Helpers – MFI parsing
# -------------------------------------------------
def parse_filesize_from_uniqueid(uniqueid):
    """
    UNIQUEID voorbeeld: '31001977235*§*tt0032138'
    -> pak getal voor '*§*' en formatteer als 31.001.977.235
    """
    if not uniqueid:
        return "?"
    try:
        raw = str(uniqueid).split("*§*")[0]
        size = int(raw)
        return f"{size:,}".replace(",", ".")
    except Exception:
        return "?"


def extract_video_codec_from_tokens(tokens):
    """
    Zoek codec semantisch (positie is niet betrouwbaar door lege tokens).
    Toon 'HEVC Main 10' als dat erin zit, anders 'HEVC', 'AVC', 'AV1'.
    """
    for t in tokens:
        t_up = str(t).upper()
        if "HEVC" in t_up or "H265" in t_up:
            if "MAIN 10" in t_up or "MAIN10" in t_up:
                return "HEVC Main 10"
            return "HEVC"
        if "AVC" in t_up or "H264" in t_up:
            return "AVC"
        if "AV1" in t_up:
            return "AV1"
    return "?"


def parse_mfi_tokens(mfi_text):
    """
    Regels die jij wil:
    - lengte = token 0 (voor eerste §)
    - resolutie = token 3 (na 3de token)
    - codec: semantisch zoeken (kan verschuiven)
    - bestandsnaam = laatste token (pad)
    """
    tokens = [t.strip() for t in str(mfi_text).split("§")]
    duration = tokens[0] if len(tokens) > 0 and tokens[0] else "?"
    resolution = tokens[3] if len(tokens) > 3 and tokens[3] else "?"
    filename = os.path.basename(tokens[-1]) if tokens else "?"
    codec = extract_video_codec_from_tokens(tokens)
    return duration, resolution, codec, filename

# -------------------------------------------------
# OMDb – poster
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_poster_omdb(imdb_id):
    if not imdb_id or not OMDB_KEY:
        return None
    r = requests.get(
        "https://www.omdbapi.com/",
        params={"i": imdb_id, "apikey": OMDB_KEY},
        timeout=10
    )
    try:
        data = r.json()
    except Exception:
        return None

    poster = data.get("Poster")
    return poster if poster and poster != "N/A" else None


def imdb_url(imdb_id):
    return f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

# -------------------------------------------------
# Rating chips model (zonder ⭐⭐⭐+)
# -------------------------------------------------
RATINGS = {
    "stars4": {"label": "⭐⭐⭐⭐", "db": ["TPR"], "class": "green"},
    "stars3": {"label": "⭐⭐⭐", "db": ["AFM", "A-FILM"], "class": "yellow"},
    "stars2": {"label": "⭐⭐", "db": ["BFM", "B-FILM"], "class": "orange"},
    "stars1": {"label": "⭐", "db": ["CFM", "C-FILM"], "class": "red"},
    "classic": {"label": "Classic", "db": ["CLS"], "class": "purple"},
    "box": {"label": "BOX", "db": ["BOX"], "class": "gray"},
}

# -------------------------------------------------
# Load all data
# -------------------------------------------------
films_df = load_films()
moviemeter_df = load_moviemeter()
mfi_df = load_mfi()

# -------------------------------------------------
# Badge counts (altijd op volledige DB, unieke films = unieke IMDB_ID)
# -------------------------------------------------
badge_counts = {}
for key, meta in RATINGS.items():
    badge_counts[key] = films_df[films_df["RATING_UC"].isin(meta["db"])]["IMDB_ID"].nunique()

# -------------------------------------------------
# URL-state
# -------------------------------------------------
active_rating = st.query_params.get("rating")
if active_rating and active_rating not in RATINGS:
    active_rating = None

# -------------------------------------------------
# UI – chips + acties
# -------------------------------------------------
st.markdown("### ⭐ Beoordeling")

# Buttons om te klikken (functioneel)
btn_cols = st.columns(len(RATINGS) + 1)
with btn_cols[0]:
    if st.button("Alles", use_container_width=True):
        st.query_params.clear()
        active_rating = None

for i, key in enumerate(RATINGS.keys(), start=1):
    meta = RATINGS[key]
    label = f"{meta['label']} ({badge_counts[key]})"
    with btn_cols[i]:
        if st.button(label, key=f"btn_{key}", use_container_width=True):
            st.query_params.update({"rating": key})
            active_rating = key

# Visuele chips (kleur)
chip_html = "<div class='chip-row'>"
if not active_rating:
    chip_html += "<span class='chip dark active'>Alles</span>"
else:
    chip_html += "<span class='chip dark'>Alles</span>"

for key, meta in RATINGS.items():
    label = f"{meta['label']} ({badge_counts[key]})"
    active = "active" if active_rating == key else ""
    chip_html += f"<span class='chip {meta['class']} {active}'>{label}</span>"
chip_html += "</div>"
st.markdown(chip_html, unsafe_allow_html=True)

# Extra filters
only_unseen = st.checkbox("Toon enkel niet bekeken films", value=False)
query = st.text_input("🔍 Zoek film (optioneel)", placeholder="Typ titel...")

# -------------------------------------------------
# START-GEDRAG: niets tonen tenzij zoek of chip gekozen
# -------------------------------------------------
if not query and not active_rating:
    st.info("Zoek een film of kies een rating ⭐ (bij openen wordt niets geladen).")
    st.stop()

# -------------------------------------------------
# APPLY FILTERS
# -------------------------------------------------
results = films_df.copy()

if active_rating:
    results = results[results["RATING_UC"].isin(RATINGS[active_rating]["db"])]

if only_unseen:
    results = results[
        results["BEKEKEN"].isna()
        | (results["BEKEKEN"].astype(str).str.strip() == "")
    ]

if query:
    results = results[results["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden met deze filters")
    st.stop()

st.caption(f"{results['IMDB_ID'].nunique()} films gevonden")

# -------------------------------------------------
# RENDER – per IMDb (1 titel + 1 poster + bestanden)
# -------------------------------------------------
groups = results.groupby("IMDB_ID", sort=False)

for imdb_id, group in groups:
    if not imdb_id or str(imdb_id).strip() == "":
        # films zonder imdb_id: toon toch iets (maar zonder poster/plot)
        title = group.iloc[0]["FILM"]
        year = group.iloc[0]["JAAR"]
        st.markdown(f"### {title} ({year})")
        st.caption("Geen IMDb-id gevonden")
        st.divider()
        continue

    title = group.iloc[0]["FILM"]
    year = group.iloc[0]["JAAR"]

    poster = get_poster_omdb(imdb_id)
    url = imdb_url(imdb_id)

    # Plot uit MovieMeter
    mm_row = moviemeter_df[moviemeter_df["IMDBTT"] == imdb_id]
    plot = None
    if not mm_row.empty:
        plot = str(mm_row.iloc[0]["MOVIEMETER"]).split("*§*")[0].strip()

    # Layout
    col_poster, col_content = st.columns([1.2, 4])

    with col_poster:
        if poster and url:
            # klikbare poster
            st.markdown(
                f'<a href="{url}" target="_blank"><img src="{poster}" width="150"></a>',
                unsafe_allow_html=True
            )
        elif poster:
            st.image(poster, width=150)
        else:
            st.caption("🖼️ geen cover")

    with col_content:
        if url:
            st.markdown(f"### [{title}]({url}) ({year})")
        else:
            st.markdown(f"### {title} ({year})")

        if plot:
            st.markdown(f"_{plot}_")

        # Bestanden uit MFI DB
        mfi_hits = mfi_df[mfi_df["IMDBTT"] == imdb_id]
        if not mfi_hits.empty:
            # Per bestand: Bestandsnaam + "duur – resolutie – codec – size"
            for _, r in mfi_hits.iterrows():
                duration, res, codec, fname = parse_mfi_tokens(r["MFI"])
                size = parse_filesize_from_uniqueid(r["UNIQUEID"])
                st.markdown(
                    f"- **{fname}**  \n"
                    f"  ⏱ {duration} – {res} – {codec} – {size}"
                )
        else:
            st.caption("Geen MFI-info gevonden")

    st.divider()
