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
# CONFIG
# -------------------------------------------------
DROPBOX_DB_URL = (
    "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/"
    "DBase-Films.db?rlkey=6bozrymb3m6vh5llej56do1nh&raw=1"
)
OMDB_KEY = st.secrets.get("OMDB_KEY", os.getenv("OMDB_KEY"))

# -------------------------------------------------
# Download DB
# -------------------------------------------------
@st.cache_data(ttl=600)
def download_db():
    r = requests.get(DROPBOX_DB_URL, timeout=20)
    r.raise_for_status()
    with open("films.db", "wb") as f:
        f.write(r.content)
    return "films.db"

# -------------------------------------------------
# Load data
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    conn = sqlite3.connect(download_db())
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

# -------------------------------------------------
# Helpers
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
    r = raw.upper()
    if r == "TPR":
        return "⭐⭐⭐⭐"
    if r in ("AFM", "A-FILM"):
        return "⭐⭐⭐"
    if r in ("BFM", "B-FILM"):
        return "⭐⭐"
    if r in ("CFM", "C-FILM"):
        return "⭐"
    return ""


@st.cache_data(ttl=300)
def get_poster(imdb_id):
    if not imdb_id or not OMDB_KEY:
        return None
    r = requests.get(
        f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_KEY}",
        timeout=10
    )
    try:
        data = r.json()
    except Exception:
        return None
    poster = data.get("Poster")
    return poster if poster and poster != "N/A" else None

# -------------------------------------------------
# SORT STATE (klik = toggle)
# -------------------------------------------------
if "sort_field" not in st.session_state:
    st.session_state.sort_field = "JAAR"
    st.session_state.sort_asc = True

col1, col2 = st.columns(2)

with col1:
    if st.button("Naam"):
        if st.session_state.sort_field == "FILM":
            st.session_state.sort_asc = not st.session_state.sort_asc
        else:
            st.session_state.sort_field = "FILM"
            st.session_state.sort_asc = True

with col2:
    if st.button("Jaar"):
        if st.session_state.sort_field == "JAAR":
            st.session_state.sort_asc = not st.session_state.sort_asc
        else:
            st.session_state.sort_field = "JAAR"
            st.session_state.sort_asc = True

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film", placeholder="Typ titel en druk op Enter")

df = load_data()

if not query:
    st.stop()

results = df[df["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# SORT (ENKEL HIER SORTEREN!)
# -------------------------------------------------
if st.session_state.sort_field == "FILM":
    results = results.sort_values(
        by="FILM_LC",
        ascending=st.session_state.sort_asc
    )
else:
    results = results.sort_values(
        by=["JAAR", "FILM_LC"],
        ascending=[st.session_state.sort_asc, True]
    )

# -------------------------------------------------
# GROUP BY IMDb (NIET SORTEREN!)
# -------------------------------------------------
groups = results.groupby("IMDB_ID", sort=False)

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb_id, group in groups:

    poster = get_poster(imdb_id)

    col_poster, col_films = st.columns([1.2, 4])

    with col_poster:
        if poster:
            st.image(poster, width=140)
        else:
            st.caption("🖼️ geen poster")

    with col_films:
        cols = st.columns(len(group))

        for col, (_, row) in zip(cols, group.iterrows()):
            minutes = parse_length_to_minutes(row["LENGTE"])
            length_txt = f"{minutes} min" if minutes else "?"
            stars = rating_to_stars(row["FILMRATING"])

            seen = row["BEKEKEN"]
            seen_txt = "🔴" if not seen else "🟢"

            col.markdown(
                f"**{row['FILM']}**  \n"
                f"{row['JAAR']}  \n"
                f"⏱ {length_txt}  \n"
                f"{stars} {seen_txt}"
            )

    st.divider()
