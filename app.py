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
.chip-container {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.chip {
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 0.9rem;
    cursor: pointer;
    user-select: none;
    background-color: #2b2b2b;
    color: #ddd;
    border: 1px solid #444;
}
.chip.active {
    background-color: #ff4b4b;
    color: white;
    border-color: #ff4b4b;
    font-weight: 600;
}
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
# Helpers
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
    df = pd.read_sql_query(
        "SELECT FILM, JAAR, BEKEKEN, IMDBLINK, FILMRATING FROM tbl_DBase_Films",
        conn
    )
    conn.close()
    df["IMDB_ID"] = df["IMDBLINK"].str.extract(r"(tt\d{7,9})")
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


def filesize_from_uniqueid(uid):
    try:
        return f"{int(uid.split('*§*')[0]):,}".replace(",", ".")
    except:
        return "?"


def parse_mfi(mfi):
    t = [x.strip() for x in mfi.split("§")]
    duration = t[0] if len(t) > 0 else "?"
    resolution = t[3] if len(t) > 3 else "?"
    filename = os.path.basename(t[-1])
    codec = "?"
    for x in t:
        u = x.upper()
        if "HEVC" in u or "H265" in u:
            codec = "HEVC Main 10" if "MAIN 10" in u else "HEVC"
            break
        if "AVC" in u or "H264" in u:
            codec = "AVC"
            break
    return duration, resolution, codec, filename


@st.cache_data(ttl=3600)
def poster_and_imdb(imdb):
    if not imdb or not OMDB_KEY:
        return None, None
    r = requests.get("https://www.omdbapi.com/", params={"i": imdb, "apikey": OMDB_KEY})
    d = r.json()
    p = d.get("Poster")
    if p == "N/A":
        p = None
    return p, f"https://www.imdb.com/title/{imdb}/"

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
films = load_films()
moviemeter = load_moviemeter()
mfi = load_mfi()

# -------------------------------------------------
# FILTER STATE
# -------------------------------------------------
if "active_rating" not in st.session_state:
    st.session_state.active_rating = "Alles"

rating_map = {
    "Alles": None,
    "⭐⭐⭐⭐": ["TPR"],
    "⭐⭐⭐": ["AFM", "A-FILM"],
    "⭐⭐": ["BFM", "B-FILM"],
    "⭐": ["CFM", "C-FILM"],
    "Classic": ["CLS"]
}

# -------------------------------------------------
# FILTER UI
# -------------------------------------------------
st.markdown("### Beoordeling")

cols = st.columns(len(rating_map))
for col, label in zip(cols, rating_map.keys()):
    with col:
        if st.button(label, key=f"chip_{label}"):
            st.session_state.active_rating = label

chip_html = '<div class="chip-container">'
for label in rating_map:
    active = "active" if st.session_state.active_rating == label else ""
    chip_html += f'<div class="chip {active}">{label}</div>'
chip_html += "</div>"
st.markdown(chip_html, unsafe_allow_html=True)

only_unseen = st.checkbox("Toon enkel niet bekeken films")

query = st.text_input("🔍 Zoek film (optioneel)")

# -------------------------------------------------
# APPLY FILTERS
# -------------------------------------------------
results = films.copy()

# ⭐ rating filter (altijd toepasbaar)
if st.session_state.active_rating != "Alles":
    allowed = rating_map[st.session_state.active_rating]
    results = results[results["RATING_UC"].isin(allowed)]

# 👁️ niet bekeken
if only_unseen:
    results = results[
        results["BEKEKEN"].isna()
        | (results["BEKEKEN"].astype(str).str.strip() == "")
    ]

# 🔍 zoek (optioneel!)
if query:
    results = results[results["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden met deze filters")
    st.stop()

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb, group in results.groupby("IMDB_ID", sort=False):

    title = group.iloc[0]["FILM"]
    year = group.iloc[0]["JAAR"]

    poster, imdb_url = poster_and_imdb(imdb)

    c1, c2 = st.columns([1.1, 4])
    with c1:
        if poster:
            st.markdown(
                f'<a href="{imdb_url}" target="_blank"><img src="{poster}" width="150"></a>',
                unsafe_allow_html=True
            )
    with c2:
        st.markdown(f"### {title} ({year})")

        mm = moviemeter[moviemeter["IMDBTT"] == imdb]
        if not mm.empty:
            st.markdown(f"_{mm.iloc[0]['MOVIEMETER'].split('*§*')[0]}_")

        mf = mfi[mfi["IMDBTT"] == imdb]
        for _, r in mf.iterrows():
            dur, res, codec, fn = parse_mfi(r["MFI"])
            size = filesize_from_uniqueid(r["UNIQUEID"])
            st.markdown(f"- **{fn}**  \n  ⏱ {dur} – {res} – {codec} – {size}")

    st.divider()
