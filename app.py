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
# CHIP CSS
# -------------------------------------------------
st.markdown("""
<style>
.chip-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
.chip {
    padding:6px 14px;
    border-radius:999px;
    border:1px solid #555;
    cursor:pointer;
    font-size:0.9rem;
}
.chip.active { font-weight:700; }
.star4 { background:#2ecc71; color:black; }
.star3 { background:#f1c40f; color:black; }
.star2 { background:#e67e22; color:black; }
.star1 { background:#e74c3c; color:white; }
.classic { background:#9b59b6; color:white; }
.box { background:#7f8c8d; color:white; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# CONFIG – Dropbox raw URLs (ONGEWIJZIGD)
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
# Load databases (STABIEL)
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_films():
    conn = sqlite3.connect(download_db(FILMS_DB_URL, "films.db"))
    df = pd.read_sql_query(
        "SELECT FILM, JAAR, BEKEKEN, IMDBLINK, FILMRATING FROM tbl_DBase_Films",
        conn
    )
    conn.close()

    # 🔑 CRUCIAAL: JUISTE REGEX
    df["IMDB_ID"] = df["IMDBLINK"].str.extract(r"(tt\d{7,9})")

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
# Helpers
# -------------------------------------------------
def parse_filesize_from_uniqueid(uniqueid):
    try:
        raw = uniqueid.split("*§*")[0]
        return f"{int(raw):,}".replace(",", ".")
    except:
        return "?"


def extract_codec(tokens):
    for t in tokens:
        u = t.upper()
        if "HEVC" in u or "H265" in u:
            return "HEVC Main 10" if "MAIN 10" in u else "HEVC"
        if "AVC" in u or "H264" in u:
            return "AVC"
        if "AV1" in u:
            return "AV1"
    return "?"


def parse_mfi(mfi):
    tokens = [t.strip() for t in mfi.split("§")]
    duration = tokens[0] if len(tokens) > 0 else "?"
    resolution = tokens[3] if len(tokens) > 3 else "?"
    filename = os.path.basename(tokens[-1])
    codec = extract_codec(tokens)
    return duration, resolution, codec, filename


@st.cache_data(ttl=3600)
def get_poster_and_imdb(imdb_id):
    if not imdb_id or not OMDB_KEY:
        return None, None

    r = requests.get(
        "https://www.omdbapi.com/",
        params={"i": imdb_id, "apikey": OMDB_KEY},
        timeout=10
    )
    try:
        data = r.json()
    except:
        return None, None

    poster = data.get("Poster")
    if poster == "N/A":
        poster = None
    return poster, f"https://www.imdb.com/title/{imdb_id}/"

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
films = load_films()
moviemeter = load_moviemeter()
mfi = load_mfi()

# -------------------------------------------------
# RATING CHIPS
# -------------------------------------------------
RATINGS = {
    "⭐⭐⭐⭐": (["TPR"], "star4"),
    "⭐⭐⭐":  (["AFM","A-FILM"], "star3"),
    "⭐⭐":   (["BFM","B-FILM"], "star2"),
    "⭐":    (["CFM","C-FILM"], "star1"),
    "Classic": (["CLS"], "classic"),
    "BOX": (["BOX"], "box")
}

if "active_chip" not in st.session_state:
    st.session_state.active_chip = None

st.markdown("### Beoordeling")
cols = st.columns(len(RATINGS) + 1)

with cols[0]:
    if st.button(f"Alles ({films['IMDB_ID'].nunique()})"):
        st.session_state.active_chip = None

for col, (label, (codes, _)) in zip(cols[1:], RATINGS.items()):
    count = films[films["RATING_UC"].isin(codes)]["IMDB_ID"].nunique()
    with col:
        if st.button(f"{label} ({count})"):
            st.session_state.active_chip = label

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film (optioneel)")

if not query and not st.session_state.active_chip:
    st.info("Zoek een film of klik op een ⭐-chip")
    st.stop()

results = films.copy()

if st.session_state.active_chip:
    codes = RATINGS[st.session_state.active_chip][0]
    results = results[results["RATING_UC"].isin(codes)]

if query:
    results = results[results["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb_id, group in results.groupby("IMDB_ID", sort=False):
    row = group.iloc[0]
    poster, imdb_url = get_poster_and_imdb(imdb_id)

    col_poster, col_main = st.columns([1.1, 4])

    with col_poster:
        if poster:
            st.markdown(
                f'<a href="{imdb_url}" target="_blank">'
                f'<img src="{poster}" width="150"></a>',
                unsafe_allow_html=True
            )

    with col_main:
        st.markdown(f"### {row['FILM']} ({row['JAAR']})")

        mm = moviemeter[moviemeter["IMDBTT"] == imdb_id]
        if not mm.empty:
            st.markdown(f"_{mm.iloc[0]['MOVIEMETER'].split('*§*')[0]}_")

        files = mfi[mfi["IMDBTT"] == imdb_id]
        for _, r in files.iterrows():
            dur, res, codec, name = parse_mfi(r["MFI"])
            size = parse_filesize_from_uniqueid(r["UNIQUEID"])
            st.markdown(f"- **{name}**  \n  ⏱ {dur} – {res} – {codec} – {size}")

    st.divider()
