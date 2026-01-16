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
            BEKEKEN,
            IMDBLINK,
            FILMRATING
        FROM tbl_DBase_Films
        """,
        conn
    )
    conn.close()

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
# Helpers – MFI parsing
# -------------------------------------------------
def parse_filesize_from_uniqueid(uniqueid):
    try:
        raw = uniqueid.split("*§*")[0]
        return f"{int(raw):,}".replace(",", ".")
    except Exception:
        return "?"


def extract_video_codec_from_tokens(tokens):
    for t in tokens:
        t_up = t.upper()
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
    tokens = [t.strip() for t in mfi_text.split("§")]
    duration = tokens[0] if len(tokens) > 0 else "?"
    resolution = tokens[3] if len(tokens) > 3 else "?"
    filename = os.path.basename(tokens[-1]) if tokens else "?"
    codec = extract_video_codec_from_tokens(tokens)
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
    except Exception:
        return None, None

    poster = data.get("Poster")
    if poster == "N/A":
        poster = None

    imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
    return poster, imdb_url

# -------------------------------------------------
# Load all data
# -------------------------------------------------
films_df = load_films()
moviemeter_df = load_moviemeter()
mfi_df = load_mfi()

# -------------------------------------------------
# FILTERS
# -------------------------------------------------
st.markdown("### 🔎 Filters")

only_unseen = st.checkbox("Toon enkel niet bekeken films", value=False)

rating_ui_to_db = {
    "Alles": None,
    "⭐⭐⭐⭐": ["TPR"],
    "⭐⭐⭐": ["AFM", "A-FILM"],
    "⭐⭐": ["BFM", "B-FILM"],
    "⭐": ["CFM", "C-FILM"],
    "Classic": ["CLS"]
}

selected_rating = st.radio(
    "Beoordeling",
    list(rating_ui_to_db.keys()),
    horizontal=True
)

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film", placeholder="Typ titel en druk op Enter")

if not query:
    st.stop()

results = films_df[films_df["FILM_LC"].str.contains(query.lower(), na=False)]

if only_unseen:
    results = results[
        results["BEKEKEN"].isna()
        | (results["BEKEKEN"].astype(str).str.strip() == "")
    ]

if selected_rating != "Alles":
    allowed = rating_ui_to_db[selected_rating]
    results = results[results["RATING_UC"].isin(allowed)]

if results.empty:
    st.warning("Geen films gevonden met deze filters")
    st.stop()

groups = results.groupby("IMDB_ID", sort=False)

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb_id, group in groups:

    title = group.iloc[0]["FILM"]
    year = group.iloc[0]["JAAR"]

    poster, imdb_url = get_poster_and_imdb(imdb_id)

    col_poster, col_main = st.columns([1.1, 4])

    with col_poster:
        if poster:
            st.markdown(
                f'<a href="{imdb_url}" target="_blank">'
                f'<img src="{poster}" width="150"></a>',
                unsafe_allow_html=True
            )
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
                duration, res, codec, fname = parse_mfi_tokens(r["MFI"])
                size = parse_filesize_from_uniqueid(r["UNIQUEID"])

                st.markdown(
                    f"- **{fname}**  \n"
                    f"  ⏱ {duration} – {res} – {codec} – {size}"
                )

    st.divider()
