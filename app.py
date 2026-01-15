import streamlit as st
import pandas as pd
import sqlite3
import requests
import re

st.set_page_config(page_title="Filmcatalogus", layout="centered")

DROPBOX_DB_URL = "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/DBase-Films.db?rlkey=6bozrymb3m6vh5llej56do1nh&raw=1"
OMDB_KEY = st.secrets["OMDB_KEY"]

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

# ---------------- OMDb ----------------
@st.cache_data(ttl=86400)
def get_poster(imdb_link):
    if not imdb_link:
        return None
    @st.cache_data(ttl=86400)
    def get_poster(imdb_id):
    if not imdb_id:
        return None
    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_KEY}"
    r = requests.get(url)
    data = r.json()
    if "Poster" in data and data["Poster"] != "N/A":
        return data["Poster"]
    return None

    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_KEY}"
    r = requests.get(url)
    data = r.json()
    if "Poster" in data and data["Poster"] != "N/A":
        return data["Poster"]
    return None

# ---------------- Sorting ----------------
def normalize_title(t):
    t = t.lower()
    t = t.replace("꞉", ":")
    if t.startswith("the "):
        t = t[4:]
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return t

# ---------------- UI ----------------
st.markdown("## 🎬 Filmcatalogus")

mobile_mode = st.checkbox("📱 Mobiele weergave", value=True)

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

results = results.copy()
results["__sort"] = results["FILM"].apply(normalize_title)
results = results.sort_values("__sort")

st.caption(f"🎞️ {len(results)} films gevonden")

# Paging only when mobile_mode
if mobile_mode:
    if "page" not in st.session_state:
        st.session_state.page = 0
    page_size = 5
    start = st.session_state.page * page_size
    end = start + page_size
    view = results.iloc[start:end]
else:
    view = results

# Render films
for _, row in view.iterrows():
    poster = get_poster(row["IMDBLINK"])
    imdb_id = row["IMDBLINK"]
    imdb = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else ""


    title = row["FILM"]
    year = row["JAAR"]
    seen = row["BEKEKEN"]

    if pd.isna(seen) or seen == "":
        seen_text = "🔴 Nooit gezien"
    else:
        seen_text = f"🟢 Laatst gezien: {seen}"

    st.markdown(
        f"""
        <div style="display:flex;gap:12px;padding:10px;background:#1e1e1e;border-radius:12px;margin-bottom:12px;">
            {"<img src='"+poster+"' style='width:70px'>" if poster else ""}
            <div>
                <a href="{imdb}" target="_blank"><b>{title}</b></a> ({year})<br>
                {seen_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Mobile navigation
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
