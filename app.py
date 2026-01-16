import streamlit as st
import pandas as pd
import sqlite3
import requests
import re
import os

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Filmcatalogus",
    layout="centered"
)

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
# Load data + index
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    db_path = download_db()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT
            FILM,
            JAAR,
            LENGTE,
            BEKEKEN,
            IMDBLINK
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
    if raw is None:
        return None

    s = str(raw).strip().lower()
    if not s:
        return None

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

    return total if total > 0 else None


@st.cache_data(ttl=300)
def get_poster(imdb_id):
    if not imdb_id or not OMDB_KEY:
        return None

    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_KEY}"
    r = requests.get(url, timeout=10)

    try:
        data = r.json()
    except Exception:
        return None

    poster = data.get("Poster")
    if poster and poster != "N/A":
        return poster

    return None

# -------------------------------------------------
# UI CONTROLS
# -------------------------------------------------
query = st.text_input(
    "🔍 Zoek film",
    placeholder="Typ titel en druk op Enter"
)

sort_field = st.segmented_control(
    "Sorteren op",
    options=["Jaar", "Naam"],
    default="Jaar"
)

reverse_order = st.toggle(
    "Omgekeerde volgorde",
    value=False
)

# -------------------------------------------------
# DATA
# -------------------------------------------------
df = load_data()

if not query:
    st.info("Begin te typen en druk op Enter")
    st.stop()

q = query.lower()
results = df[df["FILM_LC"].str.contains(q, na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# SORTERING
# -------------------------------------------------
ascending = not reverse_order

if sort_field == "Naam":
    results = results.sort_values(
        by="FILM_LC",
        ascending=ascending
    )
else:
    results = results.sort_values(
        by=["JAAR", "FILM_LC"],
        ascending=[ascending, True]
    )

# Extra: IMDb groepering bij elkaar houden
results = results.sort_values(
    by=["IMDB_ID", "JAAR"],
    kind="stable"
)

st.caption(f"🎞️ {len(results)} films gevonden")

# -------------------------------------------------
# RENDER (met IMDb-groepen)
# -------------------------------------------------
current_imdb = None

for _, row in results.iterrows():

    imdb_id = row["IMDB_ID"]

    # 🔗 NIEUWE GROEP
    if imdb_id != current_imdb:
        current_imdb = imdb_id
        st.markdown("---")
        if imdb_id:
            st.markdown(f"### IMDb-groep: `{imdb_id}`")

    poster = get_poster(imdb_id)

    minutes = parse_length_to_minutes(row["LENGTE"])
    length_text = f"⏱ {minutes} min" if minutes else "⏱ ? min"

    seen = row["BEKEKEN"]
    seen_text = "🔴 Nooit gezien" if not seen else f"🟢 Laatst gezien: {seen}"

    col1, col2 = st.columns([1.2, 4])

    with col1:
        if poster:
            st.image(poster, width=140)
        else:
            st.caption("🖼️ geen poster")

    with col2:
        st.markdown(f"**{row['FILM']}** ({row['JAAR']})")
        st.markdown(f"{length_text}  \n{seen_text}")

# -------------------------------------------------
# END
# -------------------------------------------------
