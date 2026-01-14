import streamlit as st
import pandas as pd
import sqlite3
import dropbox
import re
import os

# ============ CONFIG ============
DROPBOX_PATH = "/DBase-Films.db"

# Streamlit secrets:
# DROPBOX_TOKEN = "..."
# ================================

st.set_page_config(page_title="My Film Catalog", layout="wide")


# ---------- Dropbox download ----------
@st.cache_data(ttl=600)
def download_db():
    dbx = dropbox.Dropbox(st.secrets["DROPBOX_TOKEN"])
    md, res = dbx.files_download(DROPBOX_PATH)
    with open("films.db", "wb") as f:
        f.write(res.content)
    return "films.db"


# ---------- Length parsing ----------
def parse_length(val):
    if val is None:
        return None

    s = str(val).strip().lower()

    # Format: 01:43:49
    if ":" in s:
        try:
            parts = s.split(":")
            h = int(parts[0])
            m = int(parts[1])
            return h * 60 + m
        except:
            return None

    # Format: 1 h 47 min
    m = re.search(r"(\d+)\s*h", s)
    mins = re.search(r"(\d+)\s*min", s)

    hours = int(m.group(1)) if m else 0
    minutes = int(mins.group(1)) if mins else 0

    if hours == 0 and minutes == 0:
        return None

    return hours * 60 + minutes


# ---------- Load database ----------
@st.cache_data(ttl=600)
def load_data():
    db_file = download_db()
    conn = sqlite3.connect(db_file)

    df = pd.read_sql_query("SELECT * FROM tbl_DBase_Films", conn)
    conn.close()

    # Normalize
    df["minutes"] = df["LENGTE"].apply(parse_length)
    df["seen"] = df["BEKEKEN"].notna()

    return df


# ---------- UI ----------
st.title("🎬 My Film Catalog")

df = load_data()

# Sidebar filters
with st.sidebar:
    st.header("Filters")

    search = st.text_input("Search title")

    min_len, max_len = st.slider(
        "Length (minutes)",
        0, 300, (60, 180)
    )

    seen_only = st.checkbox("Seen only")
    unseen_only = st.checkbox("Unseen only")

    if st.button("🔄 Refresh database"):
        st.cache_data.clear()
        st.rerun()

# ---------- Filtering ----------
filtered = df.copy()

if search:
    filtered = filtered[filtered["FILM"].str.contains(search, case=False, na=False)]

filtered = filtered[
    (filtered["minutes"].isna()) |
    ((filtered["minutes"] >= min_len) & (filtered["minutes"] <= max_len))
]

if seen_only:
    filtered = filtered[filtered["seen"] == True]

if unseen_only:
    filtered = filtered[filtered["seen"] == False]

filtered = filtered.sort_values("FILM")

# ---------- Display ----------
st.subheader(f"Results: {len(filtered)}")

for _, row in filtered.iterrows():
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"### {row['FILM']} ({row['JAAR']})")

        st.write(f"Length: {row['minutes']} min" if pd.notna(row["minutes"]) else "Length: ?")

        if row["seen"]:
            st.success(f"Last seen: {row['BEKEKEN']}")
        else:
            st.error("Never seen")

        if pd.notna(row["GENRE"]):
            st.caption(row["GENRE"])

    with col2:
        if pd.notna(row["FILMRATING"]):
            st.metric("Rating", row["FILMRATING"])

    st.divider()
