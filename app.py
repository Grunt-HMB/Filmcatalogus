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
FILMS_DB_URL = "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/DBase-Films.db?raw=1"
MOVIEMETER_DB_URL = "https://www.dropbox.com/scl/fi/dlj5dsm3dhd5tfz1utu8w/MovieMeter_DBase.db?raw=1"
MFI_DB_URL = "https://www.dropbox.com/scl/fi/w5em79ae4t6kca7dx6ead/DBase-MFI.db?raw=1"

OMDB_KEY = st.secrets.get("OMDB_KEY")

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
    conn = sqlite3.connect(download_db(MOVIEMETER_DB_URL, "mm.db"))
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
        return f"{int(uniqueid.split('*§*')[0]):,}".replace(",", ".")
    except:
        return "?"

def parse_mfi(mfi):
    t = [x.strip() for x in mfi.split("§")]
    return (
        t[0] if len(t) > 0 else "?",
        t[3] if len(t) > 3 else "?",
        os.path.basename(t[-1])
    )

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
        d = r.json()
    except:
        return None
    return d.get("Poster") if d.get("Poster") not in (None, "N/A") else None

# -------------------------------------------------
# Load data
# -------------------------------------------------
films = load_films()
moviemeter = load_moviemeter()
mfi = load_mfi()

# -------------------------------------------------
# Session state
# -------------------------------------------------
if "query" not in st.session_state:
    st.session_state.query = ""
if "active_chip" not in st.session_state:
    st.session_state.active_chip = None

# -------------------------------------------------
# Chips
# -------------------------------------------------
RATINGS = {
    "⭐⭐⭐⭐": ["TPR"],
    "⭐⭐⭐": ["AFM", "A-FILM"],
    "⭐⭐": ["BFM", "B-FILM"],
    "⭐": ["CFM", "C-FILM"],
    "Classic": ["CLS"],
    "BOX": ["BOX"]
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
            st.session_state.query = ""

# -------------------------------------------------
# Search
# -------------------------------------------------
st.text_input("🔍 Zoek film", key="query")

# 🔑 zoek reset chip
if st.session_state.query:
    st.session_state.active_chip = None

# -------------------------------------------------
# Filter
# -------------------------------------------------
results = films.copy()

if st.session_state.active_chip:
    results = results[results["RATING_UC"].isin(RATINGS[st.session_state.active_chip])]

if st.session_state.query:
    results = results[results["FILM_LC"].str.contains(st.session_state.query.lower(), na=False)]

if not st.session_state.query and not st.session_state.active_chip:
    st.info("Zoek een film of kies een ⭐-categorie")
    st.stop()

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# Render
# -------------------------------------------------
for imdb_id, g in results.groupby("IMDB_ID", sort=False):
    r = g.iloc[0]
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/"

    c1, c2 = st.columns([1.1, 4])

    with c1:
        poster = get_poster(imdb_id)
        if poster:
            st.image(poster, width=120)
        st.link_button("IMDB", imdb_url)

    with c2:
        st.markdown(f"### {r['FILM']} ({r['JAAR']})")
        mm = moviemeter[moviemeter["IMDBTT"] == imdb_id]
        if not mm.empty:
            st.markdown(f"_{mm.iloc[0]['MOVIEMETER'].split('*§*')[0]}_")
        for _, row in mfi[mfi["IMDBTT"] == imdb_id].iterrows():
            dur, res, name = parse_mfi(row["MFI"])
            size = parse_filesize(row["UNIQUEID"])
            st.markdown(f"- **{name}** — ⏱ {dur} | {res} | {size}")

    st.divider()
