import streamlit as st
import pandas as pd
import sqlite3
import requests
import io

st.set_page_config(page_title="Filmcatalogus", layout="centered")

# 🔗 VERVANG DIT door jouw Dropbox raw-link
DROPBOX_DB_URL = "https://www.dropbox.com/s/XXXXXXXX/DBase-Films.db?raw=1"

# ---------------- Download DB ----------------
@st.cache_data(ttl=600)
def download_db():
    try:
        r = requests.get(DROPBOX_DB_URL, timeout=20)
        r.raise_for_status()

        with open("films.db", "wb") as f:
            f.write(r.content)

        return "films.db"

    except Exception as e:
        st.error("❌ Kan database niet downloaden")
        st.code(str(e))
        st.stop()


# ---------------- Load data ----------------
@st.cache_data(ttl=600)
def load_data():
    try:
        db = download_db()
        conn = sqlite3.connect(db)
        df = pd.read_sql_query(
            "SELECT FILM, JAAR, BEKEKEN FROM tbl_DBase_Films",
            conn
        )
        conn.close()
        return df
    except Exception as e:
        st.error("❌ Kan database niet lezen")
        st.code(str(e))
        st.stop()


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
    for _, row in results.sort_values("FILM").head(50).iterrows():
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
else:
    if query:
        st.info("Geen films gevonden")
