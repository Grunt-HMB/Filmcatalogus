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
            LENGTE,
            BEKEKEN,
            IMDBLINK,
            FILMRATING
        FROM tbl_DBase_Films
        """,
        conn
    )
    conn.close()
    df["FILM_LC"] = df["FILM"].fillna("").str.lower()
    df["IMDB_ID"] = df["IMDBLINK"].str.extract(r"(tt\d{7,9})")
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
        "SELECT IMDBTT, MFI FROM tbl_MFI_DBase",
        conn
    )
    conn.close()
    return df

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def extract_resolution(text):
    m = re.search(r"(\d{3,4})\s*x\s*(\d{3,4})", text)
    return f"{m.group(1)}x{m.group(2)}" if m else "?"


def extract_video_codec(text):
    m = re.search(r"\b(HEVC|H\.?265|AVC|H\.?264|AV1|VP9)\b", text, re.I)
    if not m:
        return "?"
    c = m.group(1).upper()
    if c in ("H265", "H.265"):
        return "HEVC"
    if c in ("H264", "H.264"):
        return "AVC"
    return c


def extract_filename(text):
    return os.path.basename(text.rsplit("§", 1)[-1])


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

# -------------------------------------------------
# Load data
# -------------------------------------------------
films_df = load_films()
moviemeter_df = load_moviemeter()
mfi_df = load_mfi()

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film", placeholder="Typ titel en druk op Enter")
if not query:
    st.stop()

results = films_df[films_df["FILM_LC"].str.contains(query.lower(), na=False)]
if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

groups = results.groupby("IMDB_ID", sort=False)

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb_id, group in groups:

    title = group.iloc[0]["FILM"]
    year = group.iloc[0]["JAAR"]

    poster = get_poster_omdb(imdb_id)

    col_poster, col_main = st.columns([1.1, 4])

    with col_poster:
        if poster:
            st.image(poster, width=150)
        else:
            st.caption("🖼️ geen cover")

    with col_main:
        st.markdown(f"### {title} ({year})")

        mm_row = moviemeter_df[moviemeter_df["IMDBTT"] == imdb_id]
        if not mm_row.empty:
            plot = mm_row.iloc[0]["MOVIEMETER"].split("*§*")[0]
            st.markdown(f"_{plot}_")

        mfi_hits = mfi_df[mfi_df["IMDBTT"] == imdb_id]
        if not mfi_hits.empty:
            st.markdown("**Bestanden**")
            for _, r in mfi_hits.iterrows():
                txt = r["MFI"]
                filename = extract_filename(txt)
                res = extract_resolution(txt)
                codec = extract_video_codec(txt)

                st.markdown(f"- **{filename}**  \n  {res} – {codec}")

    st.divider()
