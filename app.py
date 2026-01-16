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
