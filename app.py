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
# Parsing helpers
# -------------------------------------------------
def parse_length_to_minutes(raw):
    if not raw:
        return None
    s = str(raw).lower().strip()

    if re.match(r"^\d{1,2}:\d{2}:\d{2}$", s):
        h, m, _ = s.split(":")
        return int(h) * 60 + int(m)

    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*min", s)

    total = 0
    if h:
        total += int(h.group(1)) * 60
    if m:
        total += int(m.group(1))
    return total if total else None


def rating_to_stars(raw):
    if not raw:
        return ""
    return {
        "TPR": "⭐⭐⭐⭐",
        "AFM": "⭐⭐⭐", "A-FILM": "⭐⭐⭐",
        "BFM": "⭐⭐", "B-FILM": "⭐⭐",
        "CFM": "⭐", "C-FILM": "⭐"
    }.get(raw.upper(), "")


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


def extract_audio(text):
    m = re.search(r"\b(AAC|AC-3|DTS|TRUEHD|EAC-3)\b", text, re.I)
    codec = m.group(1).upper() if m else "?"
    ch = re.search(r"Channels\s*(\d+)", text, re.I)
    channels = ch.group(1) if ch else "?"
    return f"{codec} ({channels} ch)"


def extract_filename(text):
    return text.rsplit("§", 1)[-1]

# -------------------------------------------------
# Load all data
# -------------------------------------------------
films_df = load_films()
moviemeter_df = load_moviemeter()
mfi_df = load_mfi()

# -------------------------------------------------
# SORT STATE
# -------------------------------------------------
if "sort_field" not in st.session_state:
    st.session_state.sort_field = "JAAR"
    st.session_state.sort_asc = True

c1, c2 = st.columns(2)
with c1:
    if st.button("Naam"):
        st.session_state.sort_field = "FILM"
        st.session_state.sort_asc = not st.session_state.sort_asc
with c2:
    if st.button("Jaar"):
        st.session_state.sort_field = "JAAR"
        st.session_state.sort_asc = not st.session_state.sort_asc

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

# -------------------------------------------------
# SORT
# -------------------------------------------------
if st.session_state.sort_field == "FILM":
    results = results.sort_values("FILM_LC", ascending=st.session_state.sort_asc)
else:
    results = results.sort_values(
        ["JAAR", "FILM_LC"],
        ascending=[st.session_state.sort_asc, True]
    )

groups = results.groupby("IMDB_ID", sort=False)

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb_id, group in groups:

    st.markdown(f"### IMDb: `{imdb_id}`")

    # -------- MovieMeter plot --------
    mm_row = moviemeter_df[moviemeter_df["IMDBTT"] == imdb_id]
    if not mm_row.empty:
        plot = mm_row.iloc[0]["MOVIEMETER"].split("*§*")[0]
        st.markdown(f"_{plot}_")

    # -------- Filmversies --------
    cols = st.columns(len(group))
    for col, (_, row) in zip(cols, group.iterrows()):
        minutes = parse_length_to_minutes(row["LENGTE"])
        stars = rating_to_stars(row["FILMRATING"])
        seen = row["BEKEKEN"]
        seen_txt = "🔴 Nooit" if not seen else f"🟢 {seen}"

        col.markdown(
            f"**{row['FILM']}** ({row['JAAR']})  \n"
            f"⏱ {minutes if minutes else '?'} min  \n"
            f"{stars}  \n"
            f"{seen_txt}"
        )

    # -------- MFI bestanden --------
    mfi_hits = mfi_df[mfi_df["IMDBTT"] == imdb_id]
    if not mfi_hits.empty:
        st.markdown("##### 📀 Bestanden")
        for _, r in mfi_hits.iterrows():
            txt = r["MFI"]
            st.markdown(
                f"""
- **{extract_filename(txt)}**  
  📐 `{extract_resolution(txt)}`  
  🎞 `{extract_video_codec(txt)}`  
  🔊 `{extract_audio(txt)}`
"""
            )

    st.divider()
