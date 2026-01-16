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

    # 🔎 index voor sneller zoeken
    df["FILM_LC"] = df["FILM"].fillna("").str.lower()

    return df

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def extract_imdb_id(raw):
    if not raw:
        return None
    m = re.search(r"(tt\d{7,9})", str(raw))
    return m.group(1) if m else None


def parse_length_to_minutes(raw):
    """
    Ondersteunt:
    - '1 h 30 min'
    - '2 h 5 min'
    - '01:43:49'
    - None / leeg
    Retourneert: int minuten of None
    """
    if raw is None:
        return None

    s = str(raw).strip().lower()
    if not s:
        return None

    # HH:MM:SS
    if re.match(r"^\d{1,2}:\d{2}:\d{2}$", s):
        h, m, _ = s.split(":")
        return int(h) * 60 + int(m)

    # X h Y min
    hours = re.search(r"(\d+)\s*h", s)
    minutes = re.search(r"(\d+)\s*min", s)

    total = 0
    if hours:
        total += int(hours.group(1)) * 60
    if minutes:
        total += int(minutes.group(1))

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

    if data.get("Response") == "False":
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

sort_choice = st.radio(
    "Sorteer op",
    ["Jaar (oud → nieuw)", "Naam (A → Z)"],
    horizontal=True
)

mobile_mode = st.checkbox("📱 Mobiele weergave", value=False)

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
if sort_choice == "Naam (A → Z)":
    results = results.sort_values(
        by="FILM",
        key=lambda s: s.str.lower(),
        na_position="last"
    )
else:
    results = results.sort_values(
        by=["JAAR", "FILM"],
        ascending=[True, True],
        na_position="last"
    )

st.caption(f"🎞️ {len(results)} films gevonden")

# -------------------------------------------------
# PAGING (mobile)
# -------------------------------------------------
if mobile_mode:
    if "page" not in st.session_state:
        st.session_state.page = 0

    page_size = 5
    start = st.session_state.page * page_size
    end = start + page_size
    view = results.iloc[start:end]
else:
    view = results

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for _, row in view.iterrows():

    imdb_id = extract_imdb_id(row["IMDBLINK"])
    poster = get_poster(imdb_id)

    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

    title = row["FILM"]
    year = row["JAAR"]
    raw_length = row["LENGTE"]
    seen = row["BEKEKEN"]

    minutes = parse_length_to_minutes(raw_length)

    if minutes is None:
        length_text = "⏱ ? min"
    else:
        length_text = f"⏱ {minutes} min"

    if pd.isna(seen) or seen == "":
        seen_text = "🔴 Nooit gezien"
    else:
        seen_text = f"🟢 Laatst gezien: {seen}"

    col1, col2 = st.columns([1.2, 4])

    with col1:
        if poster:
            st.image(poster, width=110)
        else:
            st.caption("🖼️ geen poster")

    with col2:
        if imdb_url:
            st.markdown(f"**[{title}]({imdb_url})** ({year})")
        else:
            st.markdown(f"**{title}** ({year})")

        st.markdown(f"{length_text}  \n{seen_text}")

    st.divider()

# -------------------------------------------------
# MOBILE NAV
# -------------------------------------------------
if mobile_mode:
    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.page > 0:
            if st.button("⬅ Vorige"):
                st.session_state.page -= 1
                st.rerun()

    with col2:
        if end < len(results):
            if st.button("➡ Volgende"):
                st.session_state.page += 1
                st.rerun()
