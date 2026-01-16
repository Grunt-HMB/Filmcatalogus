import streamlit as st
import pandas as pd
import sqlite3
import requests
import re

st.set_page_config(page_title="Filmcatalogus", layout="centered")

DROPBOX_DB_URL = "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/DBase-Films.db?rlkey=6bozrymb3m6vh5llej56do1nh&raw=1"
OMDB_KEY = st.secrets["OMDB_KEY"]
st.write("DEBUG OMDB_KEY:", OMDB_KEY[:4] + "..." if OMDB_KEY else "LEEG")


# ---------------- Download DB ----------------
@st.cache_data(ttl=600)
def download_db():
    r = requests.get(DROPBOX_DB_URL, timeout=20)
    r.raise_for_status()
    with open("films.db", "wb") as f:
        f.write(r.content)
    return "films.db"

# ---------------- Load data ----------------
@st.cache_data(ttl=600)
def load_data():
    db = download_db()
    conn = sqlite3.connect(db)
    df = pd.read_sql_query(
        "SELECT FILM, JAAR, BEKEKEN, IMDBLINK FROM tbl_DBase_Films",
        conn
    )
    conn.close()
    return df

# ---------------- IMDb ID helper ----------------
def extract_imdb_id(raw):
    if not raw:
        return None
    m = re.search(r"(tt\d+)", str(raw))
    return m.group(1) if m else None

# ---------------- OMDb (DEBUG) ----------------
@st.cache_data(ttl=300)
def get_poster_debug(imdb_id):
    if not imdb_id:
        return None, "geen imdb_id"

    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_KEY}"
    r = requests.get(url, timeout=10)

    try:
        data = r.json()
    except Exception:
        return None, f"JSON fout: {r.text}"

    if data.get("Response") == "False":
        return None, f"OMDb error: {data.get('Error')}"

    poster = data.get("Poster")
    if poster and poster != "N/A":
        return poster, None

    return None, "Poster = N/A (geen poster via OMDb)"

# ---------------- UI ----------------
st.markdown("## 🎬 Filmcatalogus")

mobile_mode = st.checkbox("📱 Mobiele weergave", value=False)

sort_mode = st.radio(
    "Sorteer op",
    ["Titel", "Jaar (nieuw → oud)", "Jaar (oud → nieuw)"],
    horizontal=True
)

query = st.text_input("🔍 Zoek film")

df = load_data()

if query:
    results = df[df["FILM"].str.contains(query, case=False, na=False)]
else:
    results = pd.DataFrame()

if results.empty:
    if query:
        st.info("Geen films gevonden")
    st.stop()

# ---------------- Sorting ----------------
if sort_mode == "Titel":
    results = results.sort_values("FILM", key=lambda s: s.str.lower())
elif sort_mode == "Jaar (nieuw → oud)":
    results = results.sort_values("JAAR", ascending=False)
else:
    results = results.sort_values("JAAR", ascending=True)

st.caption(f"🎞️ {len(results)} films gevonden")

# ---------------- Paging (mobile only) ----------------
if mobile_mode:
    if "page" not in st.session_state:
        st.session_state.page = 0

    page_size = 5
    start = st.session_state.page * page_size
    end = start + page_size
    view = results.iloc[start:end]
else:
    view = results

# ---------------- Render ----------------
for _, row in view.iterrows():

    imdb_id = extract_imdb_id(row["IMDBLINK"])
    poster, poster_info = get_poster_debug(imdb_id)

    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

    title = row["FILM"]
    year = row["JAAR"]
    seen = row["BEKEKEN"]

    if pd.isna(seen) or seen == "":
        seen_text = "🔴 Nooit gezien"
    else:
        seen_text = f"🟢 Laatst gezien: {seen}"

    col1, col2 = st.columns([1, 4])

    with col1:
        if poster:
            st.image(poster, width=80)
        else:
            st.caption("🖼️ geen poster")

    with col2:
        if imdb_url:
            st.markdown(f"**[{title}]({imdb_url})** ({year})")
        else:
            st.markdown(f"**{title}** ({year})")

        st.markdown(seen_text)

        # 🔎 DEBUG INFO
        if poster_info:
            st.caption(f"ℹ️ {poster_info}")

    st.divider()

# ---------------- Mobile navigation ----------------
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
