import streamlit as st
import pandas as pd
import sqlite3
import requests
import os

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Filmcatalogus", layout="centered")
st.markdown("## 🎬 Filmcatalogus")

# -------------------------------------------------
# CHIP CSS
# -------------------------------------------------
st.markdown("""
<style>
.chip-row { display:flex; gap:8px; flex-wrap:wrap; margin: 6px 0 12px 0; }
.chip {
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.85rem;
    border: 1px solid #444;
    color: #fff;
}
.chip.active { font-weight:700; outline:2px solid rgba(255,255,255,0.3); }
.green { background:#2ecc71; }
.yellow { background:#f1c40f; color:#000; }
.orange { background:#e67e22; }
.red { background:#e74c3c; }
.purple { background:#9b59b6; }
.gray { background:#7f8c8d; }
.dark { background:#2b2b2b; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# CONFIG – Dropbox raw URLs
# -------------------------------------------------
FILMS_DB_URL = "https://www.dropbox.com/scl/fi/29xqcb68hen6fii8qlt07/DBase-Films.db?raw=1"
MOVIEMETER_DB_URL = "https://www.dropbox.com/scl/fi/dlj5dsm3dhd5tfz1utu8w/MovieMeter_DBase.db?raw=1"
MFI_DB_URL = "https://www.dropbox.com/scl/fi/w5em79ae4t6kca7dx6ead/DBase-MFI.db?raw=1"

OMDB_KEY = st.secrets.get("OMDB_KEY", os.getenv("OMDB_KEY"))

# -------------------------------------------------
# Download helper
# -------------------------------------------------
@st.cache_data(ttl=600)
def download_db(url, name):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    with open(name, "wb") as f:
        f.write(r.content)
    return name

# -------------------------------------------------
# LOAD FILMS (CRASH-PROOF)
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_films():
    conn = sqlite3.connect(download_db(FILMS_DB_URL, "films.db"))
    df = pd.read_sql("SELECT * FROM tbl_DBase_Films", conn)
    conn.close()

    cols = {c.upper(): c for c in df.columns}

    def need(c):
        if c not in cols:
            st.error(f"❌ Kolom '{c}' ontbreekt in tbl_DBase_Films")
            st.write("Beschikbare kolommen:", list(df.columns))
            st.stop()
        return cols[c]

    def opt(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    film_col = need("FILM")
    jaar_col = need("JAAR")
    imdb_col = need("IMDBLINK")

    bekeken_col = opt("BEKEKEN", "GEZIEN", "WATCHED")
    rating_col = opt("FILMRATING", "RATING", "CLASS", "TYPE", "CAT")

    df["FILM_STD"] = df[film_col]
    df["JAAR_STD"] = df[jaar_col]
    df["IMDBLINK_STD"] = df[imdb_col]
    df["BEKEKEN_STD"] = df[bekeken_col] if bekeken_col else ""
    df["RATING_STD"] = df[rating_col] if rating_col else ""

    df["IMDB_ID"] = df["IMDBLINK_STD"].str.extract(r"(tt\\d{7,9})")
    df["FILM_LC"] = df["FILM_STD"].fillna("").str.lower()
    df["RATING_UC"] = df["RATING_STD"].fillna("").str.upper()

    return df

# -------------------------------------------------
# LOAD OTHER DBS
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_moviemeter():
    conn = sqlite3.connect(download_db(MOVIEMETER_DB_URL, "mm.db"))
    df = pd.read_sql("SELECT IMDBTT, MOVIEMETER FROM tbl_MovieMeter", conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def load_mfi():
    conn = sqlite3.connect(download_db(MFI_DB_URL, "mfi.db"))
    df = pd.read_sql("SELECT IMDBTT, UNIQUEID, MFI FROM tbl_MFI_DBase", conn)
    conn.close()
    return df

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def filesize_from_uniqueid(uid):
    try:
        return f"{int(str(uid).split('*§*')[0]):,}".replace(",", ".")
    except:
        return "?"

def parse_mfi(mfi):
    t = [x.strip() for x in str(mfi).split("§")]
    duration = t[0] if len(t) > 0 else "?"
    resolution = t[3] if len(t) > 3 else "?"
    filename = os.path.basename(t[-1])
    codec = "?"
    for x in t:
        u = x.upper()
        if "HEVC" in u or "H265" in u:
            codec = "HEVC Main 10" if "MAIN 10" in u else "HEVC"
            break
        if "AVC" in u or "H264" in u:
            codec = "AVC"
            break
    return duration, resolution, codec, filename

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
films = load_films()
moviemeter = load_moviemeter()
mfi = load_mfi()

# -------------------------------------------------
# RATING MODEL (ZONDER ⭐⭐⭐+)
# -------------------------------------------------
RATINGS = {
    "stars4": {"label":"⭐⭐⭐⭐","db":["TPR"],"class":"green"},
    "stars3": {"label":"⭐⭐⭐","db":["AFM","A-FILM"],"class":"yellow"},
    "stars2": {"label":"⭐⭐","db":["BFM","B-FILM"],"class":"orange"},
    "stars1": {"label":"⭐","db":["CFM","C-FILM"],"class":"red"},
    "classic": {"label":"Classic","db":["CLS"],"class":"purple"},
    "box": {"label":"BOX","db":["BOX"],"class":"gray"}
}

# -------------------------------------------------
# BADGES
# -------------------------------------------------
badge_counts = {
    k: films[films["RATING_UC"].isin(v["db"])]["IMDB_ID"].nunique()
    for k,v in RATINGS.items()
}

# -------------------------------------------------
# URL STATE
# -------------------------------------------------
active_rating = st.query_params.get("rating")
if active_rating not in RATINGS:
    active_rating = None

# -------------------------------------------------
# UI – CHIPS
# -------------------------------------------------
st.markdown("### ⭐ Beoordeling")

cols = st.columns(len(RATINGS)+1)
with cols[0]:
    if st.button("Alles"):
        st.query_params.clear()
        active_rating = None

for i,(k,v) in enumerate(RATINGS.items(), start=1):
    if st.button(f"{v['label']} ({badge_counts[k]})", key=f"btn_{k}"):
        st.query_params.update({"rating": k})
        active_rating = k

chip_html = "<div class='chip-row'>"
chip_html += f"<span class='chip dark {'active' if not active_rating else ''}'>Alles</span>"
for k,v in RATINGS.items():
    chip_html += f"<span class='chip {v['class']} {'active' if active_rating==k else ''}'>{v['label']} ({badge_counts[k]})</span>"
chip_html += "</div>"
st.markdown(chip_html, unsafe_allow_html=True)

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film (optioneel)")

if not active_rating and not query:
    st.info("Zoek een film of kies een beoordeling ⭐")
    st.stop()

# -------------------------------------------------
# FILTER
# -------------------------------------------------
results = films.copy()

if active_rating:
    results = results[results["RATING_UC"].isin(RATINGS[active_rating]["db"])]

if query:
    results = results[results["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

st.caption(f"{results['IMDB_ID'].nunique()} films gevonden")

# -------------------------------------------------
# RENDER
# -------------------------------------------------
for imdb_id, g in results.groupby("IMDB_ID", sort=False):
    r = g.iloc[0]

    st.markdown(f"### {r['FILM_STD']} ({r['JAAR_STD']})")

    mm = moviemeter[moviemeter["IMDBTT"] == imdb_id]
    if not mm.empty:
        st.markdown(f"_{mm.iloc[0]['MOVIEMETER'].split('*§*')[0]}_")

    mf = mfi[mfi["IMDBTT"] == imdb_id]
    for _, row in mf.iterrows():
        dur,res,codec,fname = parse_mfi(row["MFI"])
        size = filesize_from_uniqueid(row["UNIQUEID"])
        st.markdown(f"- **{fname}**  \n  ⏱ {dur} – {res} – {codec} – {size}")

    st.divider()
