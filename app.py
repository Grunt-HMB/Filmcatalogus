import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import re

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Filmcatalogus", layout="centered")
st.markdown("## 🎬 Filmcatalogus")

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
    r = requests.get(url, timeout=30)
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
        "SELECT FILM, JAAR, BEKEKEN, IMDBLINK, FILMRATING FROM tbl_DBase_Films",
        conn
    )
    conn.close()
    df["IMDB_ID"] = df["IMDBLINK"].astype(str).str.extract(r"(tt\d{7,9})")
    df["FILM_LC"] = df["FILM"].fillna("").str.lower()
    df["RATING_UC"] = df["FILMRATING"].fillna("").str.upper()
    return df

@st.cache_data(ttl=600)
def load_moviemeter():
    conn = sqlite3.connect(download_db(MOVIEMETER_DB_URL, "moviemeter.db"))
    df = pd.read_sql_query("SELECT IMDBTT, MOVIEMETER FROM tbl_MovieMeter", conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def load_mfi():
    conn = sqlite3.connect(download_db(MFI_DB_URL, "mfi.db"))
    df = pd.read_sql_query("SELECT IMDBTT, UNIQUEID, MFI FROM tbl_MFI_DBase", conn)
    conn.close()
    return df

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def parse_filesize(uniqueid):
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
    return "?"

def parse_mfi(mfi):
    tokens = [t.strip() for t in mfi.split("§")]
    duration = tokens[0] if len(tokens) > 0 else "?"
    resolution = tokens[3] if len(tokens) > 3 else "?"
    filename = os.path.basename(tokens[-1])
    codec = extract_codec(tokens)
    return duration, resolution, codec, filename

@st.cache_data(ttl=3600)
def get_poster(imdb_id):
    if not imdb_id or not OMDB_KEY:
        return None
    r = requests.get(
        "https://www.omdbapi.com/",
        params={"i": imdb_id, "apikey": OMDB_KEY},
        timeout=10
    )
    try:
        data = r.json()
    except:
        return None
    poster = data.get("Poster")
    return poster if poster and poster != "N/A" else None

# -------------------------------------------------
# Load data
# -------------------------------------------------
films = load_films()
moviemeter = load_moviemeter()
mfi = load_mfi()

# -------------------------------------------------
# Session state
# -------------------------------------------------
if "active_chip" not in st.session_state:
    st.session_state.active_chip = None
if "query" not in st.session_state:
    st.session_state.query = ""

# -------------------------------------------------
# Rating chips
# -------------------------------------------------
RATINGS = {
    "⭐⭐⭐⭐": ["TPR"],
    "⭐⭐⭐": ["AFM", "A-FILM"],
    "⭐⭐": ["BFM", "B-FILM"],
    "⭐": ["CFM", "C-FILM"],
    "Classic": ["CLS"],
    "BOX": ["BOX"],
}

st.markdown("### Beoordeling")
cols = st.columns(len(RATINGS) + 1)

with cols[0]:
    if st.button("Alles"):
        st.session_state.active_chip = None
        st.session_state.query = ""

for col, (label, codes) in zip(cols[1:], RATINGS.items()):
    with col:
        if st.button(label):
            st.session_state.active_chip = label
            st.session_state.query = ""   # 🔑 reset zoekveld

# -------------------------------------------------
# Search
# -------------------------------------------------
st.text_input("🔍 Zoek film", key="query")

if not st.session_state.query and not st.session_state.active_chip:
    st.info("Zoek een film of klik op een ⭐-chip")
    st.stop()

results = films.copy()

if st.session_state.active_chip:
    results = results[results["RATING_UC"].isin(RATINGS[st.session_state.active_chip])]

if st.session_state.query:
    results = results[results["FILM_LC"].str.contains(st.session_state.query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# Render
# -------------------------------------------------
for imdb_id, group in results.groupby("IMDB_ID", sort=False):
    row = group.iloc[0]
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/"

    col_poster, col_main = st.columns([1.1, 4])

    with col_poster:
        poster = get_poster(imdb_id)
        if poster:
            st.image(poster, width=120)
            st.link_button("IMDB", imdb_url)
        else:
            st.link_button("IMDB", imdb_url)

    with col_main:
        st.markdown(f"### {row['FILM']} ({row['JAAR']})")

        mm = moviemeter[moviemeter["IMDBTT"] == imdb_id]
        if not mm.empty:
            plot = mm.iloc[0]["MOVIEMETER"].split("*§*")[0]
            st.markdown(f"_{plot}_")

        files = mfi[mfi["IMDBTT"] == imdb_id]
        for _, r in files.iterrows():
            dur, res, codec, name = parse_mfi(r["MFI"])
            size = parse_filesize(r["UNIQUEID"])
            st.markdown(f"- **{name}** — ⏱ {dur} | {res} | {codec} | {size}")

    st.divider()
