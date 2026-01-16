import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import requests
import os
import re

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Filmcatalogus", layout="centered")
st.markdown("## 🎬 Filmcatalogus")

# -------------------------------------------------
# CONFIG – Dropbox raw URLs (GEBRUIK DEZE EXACT)
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
# Download helper (met SQLite-validatie)
# -------------------------------------------------
@st.cache_data(ttl=600)
def download_db(url: str, local_name: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    with open(local_name, "wb") as f:
        f.write(r.content)

    # Snelle check: is dit echt een SQLite DB?
    with open(local_name, "rb") as f:
        header = f.read(16)

    if not header.startswith(b"SQLite format 3\x00"):
        # Vaak is dit een HTML pagina (Dropbox error / geen raw)
        preview = r.text[:200] if hasattr(r, "text") else ""
        raise ValueError(
            f"Bestand '{local_name}' is geen SQLite database. "
            f"Controleer dat je Dropbox-link '?raw=1' bevat. Preview: {preview}"
        )

    return local_name

# -------------------------------------------------
# Load databases
# -------------------------------------------------
@st.cache_data(ttl=600)
def load_films() -> pd.DataFrame:
    conn = sqlite3.connect(download_db(FILMS_DB_URL, "films.db"))
    df = pd.read_sql_query(
        "SELECT FILM, JAAR, BEKEKEN, IMDBLINK, FILMRATING FROM tbl_DBase_Films",
        conn
    )
    conn.close()

    df["IMDB_ID"] = df["IMDBLINK"].astype(str).str.extract(r"(tt\d{7,9})")
    df["FILM_LC"] = df["FILM"].fillna("").str.lower()
    df["RATING_UC"] = df["FILMRATING"].fillna("").str.upper()
    return df


@st.cache_data(ttl=600)
def load_moviemeter() -> pd.DataFrame:
    conn = sqlite3.connect(download_db(MOVIEMETER_DB_URL, "moviemeter.db"))
    df = pd.read_sql_query("SELECT IMDBTT, MOVIEMETER FROM tbl_MovieMeter", conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_mfi() -> pd.DataFrame:
    conn = sqlite3.connect(download_db(MFI_DB_URL, "mfi.db"))
    df = pd.read_sql_query("SELECT IMDBTT, UNIQUEID, MFI FROM tbl_MFI_DBase", conn)
    conn.close()
    return df

# -------------------------------------------------
# Helpers – MFI parsing
# -------------------------------------------------
def format_filesize_from_uniqueid(uniqueid: str) -> str:
    try:
        raw = str(uniqueid).split("*§*")[0].strip()
        return f"{int(raw):,}".replace(",", ".")
    except Exception:
        return "?"


def extract_video_codec_detail(tokens: list[str]) -> str:
    """
    We willen iets als:
      - 'HEVC : Main 10@L4@Main' (dus 'HEVC Main 10' is oké, maar detail is welkom)
      - 'AVC : High@L4'
      - 'AV1'
    In jouw data staat dit meestal rond token index 5, maar we scannen veilig.
    """
    for t in tokens:
        s = t.strip()
        u = s.upper()
        if "HEVC" in u or "H265" in u:
            # Probeer "HEVC : Main 10@..." te pakken
            m = re.search(r"(HEVC\s*:\s*[^:§]+)", s, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
            # fallback
            return "HEVC Main 10" if ("MAIN 10" in u or "MAIN10" in u) else "HEVC"
        if "AVC" in u or "H264" in u:
            m = re.search(r"(AVC\s*:\s*[^:§]+)", s, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
            return "AVC"
        if "AV1" in u:
            return "AV1"
    return "?"


def parse_mfi_line(mfi_text: str):
    tokens = [t.strip() for t in str(mfi_text).split("§")]

    duration = tokens[0] if len(tokens) > 0 and tokens[0] else "?"
    # jouw resolutie zit "na 3de token" => index 3 (0-based)
    resolution = tokens[3] if len(tokens) > 3 and tokens[3] else "?"
    codec = extract_video_codec_detail(tokens)
    filename = os.path.basename(tokens[-1]) if tokens else "?"
    return duration, resolution, codec, filename


def moviemeter_plot(mm_text: str) -> str | None:
    if not mm_text:
        return None
    return str(mm_text).split("*§*")[0].strip() or None

# -------------------------------------------------
# Poster (OMDb)
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_omdb_poster(imdb_id: str) -> str | None:
    if not imdb_id or not OMDB_KEY:
        return None

    r = requests.get(
        "https://www.omdbapi.com/",
        params={"i": imdb_id, "apikey": OMDB_KEY},
        timeout=15
    )
    try:
        data = r.json()
    except Exception:
        return None

    poster = data.get("Poster")
    if not poster or poster == "N/A":
        return None
    return poster

# -------------------------------------------------
# Clickable poster (zonder unsafe HTML in markdown)
# - We renderen in een iframe via components.html (werkt stabieler op Cloud)
# -------------------------------------------------
def clickable_poster(poster_url: str, imdb_url: str, width_px: int = 120):
    safe_poster = (poster_url or "").replace('"', "%22")
    safe_imdb = (imdb_url or "").replace('"', "%22")
    height_px = int(width_px * 1.5)

    html = f"""
    <div style="width:{width_px}px;">
      <a href="{safe_imdb}" target="_blank" rel="noopener noreferrer">
        <img src="{safe_poster}" style="width:{width_px}px;border-radius:6px;display:block;" />
      </a>
    </div>
    """
    components.html(html, height=height_px + 10)

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
try:
    films = load_films()
    moviemeter = load_moviemeter()
    mfi = load_mfi()
except Exception as e:
    st.error(f"Database laden mislukt: {e}")
    st.stop()

# -------------------------------------------------
# SORT STATE (klik = toggle)
# -------------------------------------------------
if "sort_field" not in st.session_state:
    st.session_state.sort_field = "FILM"   # "FILM" of "JAAR"
    st.session_state.sort_asc = True

st.markdown("### Sorteren")
s1, s2 = st.columns(2)

with s1:
    if st.button("Naam"):
        if st.session_state.sort_field == "FILM":
            st.session_state.sort_asc = not st.session_state.sort_asc
        else:
            st.session_state.sort_field = "FILM"
            st.session_state.sort_asc = True

with s2:
    if st.button("Jaar"):
        if st.session_state.sort_field == "JAAR":
            st.session_state.sort_asc = not st.session_state.sort_asc
        else:
            st.session_state.sort_field = "JAAR"
            st.session_state.sort_asc = True

# -------------------------------------------------
# RATING CHIPS (buttons met badges)
# -------------------------------------------------
RATINGS = {
    "⭐⭐⭐⭐": ["TPR"],
    "⭐⭐⭐": ["AFM", "A-FILM"],
    "⭐⭐": ["BFM", "B-FILM"],
    "⭐": ["CFM", "C-FILM"],
    "Classic": ["CLS"],
    "BOX": ["BOX"],
}

if "active_chip" not in st.session_state:
    st.session_state.active_chip = None

st.markdown("### Beoordeling")
chip_cols = st.columns(len(RATINGS) + 1)

with chip_cols[0]:
    all_count = films["IMDB_ID"].nunique()
    if st.button(f"Alles ({all_count})"):
        st.session_state.active_chip = None

for col, (label, codes) in zip(chip_cols[1:], RATINGS.items()):
    count = films[films["RATING_UC"].isin(codes)]["IMDB_ID"].nunique()
    with col:
        if st.button(f"{label} ({count})"):
            st.session_state.active_chip = label

# -------------------------------------------------
# SEARCH
# -------------------------------------------------
query = st.text_input("🔍 Zoek film (optioneel)")

if not query and not st.session_state.active_chip:
    st.info("Zoek een film of klik op een ⭐-chip")
    st.stop()

# -------------------------------------------------
# FILTER
# -------------------------------------------------
results = films.copy()

if st.session_state.active_chip:
    allowed = RATINGS[st.session_state.active_chip]
    results = results[results["RATING_UC"].isin(allowed)]

if query:
    results = results[results["FILM_LC"].str.contains(query.lower(), na=False)]

if results.empty:
    st.warning("Geen films gevonden")
    st.stop()

# -------------------------------------------------
# SORT
# -------------------------------------------------
asc = st.session_state.sort_asc
if st.session_state.sort_field == "FILM":
    results = results.sort_values("FILM_LC", ascending=asc)
else:
    # secundair sorteren op naam voor stabiliteit
    results = results.sort_values(["JAAR", "FILM_LC"], ascending=[asc, True])

# -------------------------------------------------
# RENDER (per IMDb groep)
# -------------------------------------------------
for imdb_id, group in results.groupby("IMDB_ID", sort=False):
    row = group.iloc[0]
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if isinstance(imdb_id, str) and imdb_id.startswith("tt") else None

    col_poster, col_main = st.columns([1.1, 4])

    with col_poster:
        poster_url = get_omdb_poster(imdb_id) if imdb_url else None

        if poster_url and imdb_url:
            # klik op poster opent imdb
            clickable_poster(poster_url, imdb_url, width_px=120)
        else:
            st.caption("🖼️ geen cover")
            if imdb_url:
                st.link_button("IMDB", imdb_url)

    with col_main:
        st.markdown(f"#### {row['FILM']} ({row['JAAR']})")

        mm = moviemeter[moviemeter["IMDBTT"] == imdb_id]
        if not mm.empty:
            plot = moviemeter_plot(mm.iloc[0]["MOVIEMETER"])
            if plot:
                st.markdown(f"_{plot}_")

        files = mfi[mfi["IMDBTT"] == imdb_id]
        for _, r in files.iterrows():
            dur, res, codec, name = parse_mfi_line(r["MFI"])
            size = format_filesize_from_uniqueid(r["UNIQUEID"])
            st.markdown(f"• **{name}** — ⏱ {dur} | {res} | {codec} | {size}")

    st.divider()
