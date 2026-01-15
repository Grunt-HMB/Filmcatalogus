import streamlit as st
import pandas as pd
import sqlite3
import requests
import re

st.set_page_config(page_title="Filmcatalogus", layout="centered")

DROPBOX_DB_URL = "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/DBase-Films.db?rlkey=6bozrymb3m6vh5llej56do1nh&raw=1"

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
        "SELECT FILM, JAAR, BEKEKEN FROM tbl_DBase_Films",
        conn
    )
    conn.close()
    return df

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

st.markdown(
    """
    <style>
    .stTextInput input {
        font-size: 22px !important;
        padding: 14px !important;
    }
    .filmcard {
        padding: 14px;
        border-radius: 12px;
        margin-bottom: 12px;
        background-color: #1e1e1e;
    }
    </style>
    """,
    unsafe_allow_html=True
)

query = st.text_input("🔍 Zoek film")

df = load_data()

if query:
    results = df[df["FILM"].str.contains(query, case=False, na=False)]
else:
    results = pd.DataFrame()

if not results.empty:
    results = results.copy()
    results["__sort"] = results["FILM"].apply(normalize_title)
    results = results.sort_values("__sort")

    st.caption(f"🎞️ {len(results)} films gevonden")

    if "page" not in st.session_state:
        st.session_state.page = 0

    page_size = 5
    start = st.session_state.page * page_size
    end = start + page_size
    page = results.iloc[start:end]

    for _, row in page.iterrows():
        title = row["FILM"]
        year = row["JAAR"]
        seen = row["BEKEKEN"]

        if pd.isna(seen) or seen == "":
            seen_text = "🔴 Nooit gezien"
        else:
            seen_text = f"🟢 Laatst gezien: {seen}"

        st.markdown(
            f"""
            <div class="filmcard">
            <b>{title}</b> ({year})<br>
            {seen_text}
            </div>
            """,
            unsafe_allow_html=True
        )

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

else:
    if query:
        st.info("Geen films gevonden")
