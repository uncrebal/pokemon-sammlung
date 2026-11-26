"""Bilder: Adressen der Kartenbilder, Vorschaubilder, eigene Fotos und die Suche nach fehlenden Bildern."""
import base64
import io
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

from db import neu_laden, run
from design import zeile

BASIS_DIR = Path(__file__).resolve().parent      # Ordner, in dem app.py liegt
PRODUKT_ORDNER = BASIS_DIR / "Bilder" / "Produkte"


def bild_url(sprache, serie_id, tcg_set, nr, groesse="high"):
    """Bildadresse einer Karte bei TCGdex."""
    return f"https://assets.tcgdex.net/{sprache}/{serie_id}/{tcg_set}/{nr}/{groesse}.webp"


def klein(url):
    """Kleinere Variante desselben Bildes (lädt viel schneller)."""
    if "assets.tcgdex.net" in url:
        return url.replace("/high.", "/low.")
    if "images.pokemontcg.io" in url and url.endswith("_hires.png"):
        return url[: -len("_hires.png")] + ".png"
    return url


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def url_erreichbar(url):
    """Prüft (höchstens einmal pro Woche), ob unter der Adresse wirklich ein Bild liegt."""
    try:
        anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
        with urllib.request.urlopen(anfrage, timeout=8) as antwort:
            return antwort.status in (200, 206)
    except Exception:
        return False


def beste_url(deutsch, englisch):
    """Deutsches Bild, wenn vorhanden und erreichbar, sonst das englische. Bevorzugt die kleine Variante."""
    for url, pruefen in ((deutsch, True), (englisch, False)):
        if not isinstance(url, str) or not url:
            continue
        k = klein(url)
        if k != url and url_erreichbar(k):
            return k
        if not pruefen or url_erreichbar(url):
            return url
    return englisch


@st.cache_data(show_spinner=False, ttl=7 * 24 * 3600)
def _daten_uri(pfad):
    """Kleine Vorschau einer Bilddatei im Repo als eingebettetes Bild."""
    try:
        from PIL import Image

        with Image.open(BASIS_DIR / str(pfad)) as bild:
            bild = bild.convert("RGB")
            bild.thumbnail((140, 140))
            puffer = io.BytesIO()
            bild.save(puffer, "JPEG", quality=75)
        return "data:image/jpeg;base64," + base64.b64encode(puffer.getvalue()).decode()
    except Exception:
        return ""


def vorschau(pfad):
    """Bild für eine Listenzeile: Internet-Bilder in klein, Dateien im Repo als eingebettete Vorschau."""
    if not isinstance(pfad, str) or not pfad:
        return ""
    return klein(pfad) if pfad.startswith(("http://", "https://")) else _daten_uri(pfad)


def show_image(pfad):
    """Großes Bild in der Detailansicht (am Handy etwas kleiner)."""
    breite = 170 if st.session_state.get("mobil") else 250
    if isinstance(pfad, str) and pfad.startswith(("http://", "https://")):
        st.image(pfad, width=breite)
    elif isinstance(pfad, str) and pfad and (BASIS_DIR / pfad).exists():
        st.image(str(BASIS_DIR / pfad), width=breite)
    elif isinstance(pfad, str) and pfad:
        st.caption(f"Bilddatei nicht gefunden: {pfad}")
    else:
        st.caption("Kein Bild vorhanden")


def save_image(upload, ordner):
    """Speichert ein hochgeladenes Foto im Ordner bilder/<ordner> und gibt den Pfad zurück.
    Achtung: Bei Streamlit Cloud gehen solche Dateien beim Neustart verloren (Kapitel 12 der Doku)."""
    if upload is None:
        return None
    ziel = BASIS_DIR / "bilder" / ordner / f"{uuid.uuid4().hex}{Path(upload.name).suffix.lower() or '.jpg'}"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(upload.getbuffer())
    return ziel.relative_to(BASIS_DIR).as_posix()


# ---------------------------------------------------------------
# Fehlende Bilder suchen (Karten) und zuordnen (Produkte)
# ---------------------------------------------------------------

# Japanische Sets: unser Set-Kürzel -> (Serie, Set-Code bei TCGdex/Scrydex). Hier kannst du weitere Sets ergänzen.
JP_SETS = {
    "x-stellar-miracle": ("SV", "SV7"), "x-terastal-festival-ex": ("SV", "SV8a"), "x-battle-partners": ("SV", "SV9"),
    "x-mask-of-change": ("SV", "SV6"), "x-paradise-dragona": ("SV", "SV7a"), "x-cyber-judge": ("SV", "SV5M"),
    "x-raging-surf": ("SV", "SV3a"), "x-ruler-of-the-black-flame": ("SV", "SV3"), "x-ancient-roar": ("SV", "SV4K"),
    "x-wild-force": ("SV", "SV5K"), "x-snow-hazard": ("SV", "SV2P"), "x-night-wanderer": ("SV", "SV6a"),
    "x-vstar-universe": ("S", "s12a"), "x-mega-dream-ex": ("M", "M2a"), "x-mega-symphonia": ("M", "M1S"),
}

OHNE_BILD_SQL = """
SELECT DISTINCT ON (k.karten_id) k.karten_id, k.name, k.nummer, k.set_id, s.name AS set_name,
       ks.tcg_id AS tcg_set, ks.serie_id, kk.nr AS kat_nr
FROM karten k JOIN sets s ON s.set_id = k.set_id
LEFT JOIN katalog_sets ks ON ks.set_id = k.set_id
LEFT JOIN katalog_karten kk ON kk.tcg_set = ks.tcg_id
     AND COALESCE(NULLIF(regexp_replace(split_part(kk.nr, '/', 1), '^0+', ''), ''), '0')
       = COALESCE(NULLIF(regexp_replace(split_part(k.nummer, '/', 1), '^0+', ''), ''), '0')
WHERE (k.bild_pfad IS NULL OR k.bild_pfad = '')
  AND EXISTS (SELECT 1 FROM sammlung_karten sk WHERE sk.karten_id = k.karten_id)
ORDER BY k.karten_id"""


def bild_kandidaten(r):
    """Mögliche Bildadressen für eine Karte ohne Bild, in der Reihenfolge, in der sie probiert werden."""
    roh = str(r["nummer"]).split("/")[0].strip().lstrip("0") or "0"
    padded = roh.zfill(3)
    urls = []
    if isinstance(r["tcg_set"], str) and isinstance(r["serie_id"], str):      # Set ist im Katalog
        nr = r["kat_nr"] if isinstance(r["kat_nr"], str) else padded
        urls += [bild_url(sprache, r["serie_id"], r["tcg_set"], nr) for sprache in ("de", "en", "fr", "ja")]
    sid = str(r["set_id"])
    if not sid.startswith("x-"):
        urls += [f"https://images.pokemontcg.io/{sid}/{roh}_hires.png", f"https://images.scrydex.com/pokemon/{sid}-{roh}/large"]
    if sid in JP_SETS:
        serie, code = JP_SETS[sid]
        urls += [f"https://assets.tcgdex.net/ja/{serie}/{code}/{n}/high.webp" for n in (padded, roh)]
        urls.append(f"https://images.scrydex.com/pokemon/{code.lower()}_ja-{roh}/large")
    return list(dict.fromkeys(urls))      # doppelte entfernen, Reihenfolge behalten


def bilder_suchen(df):
    """Probiert pro Karte die Kandidaten durch (12 gleichzeitig) und gibt {karten_id: url oder None} zurück."""
    def eine(r):
        return int(r["karten_id"]), next((u for u in bild_kandidaten(r) if url_erreichbar(u)), None)

    with ThreadPoolExecutor(max_workers=12) as pool:
        return dict(pool.map(eine, [r for _, r in df.iterrows()]))


def fehlende_bilder_bereich():
    """Aufklappbereich in der Ansicht Karten: Karten-Bilder suchen, Produktbilder aus dem Ordner zuordnen."""
    ohne = run(OHNE_BILD_SQL).sort_values(["set_name", "nummer"]).reset_index(drop=True)
    prod = run("""SELECT p.produkt_id, p.name, t.name AS art, p.sprache FROM produkte p JOIN produkt_typen t ON t.typ_id = p.typ_id
                  WHERE p.bild_pfad IS NULL OR p.bild_pfad = '' ORDER BY t.typ_id, p.name""")
    with st.expander(f"🖼 Fehlende Bilder ({len(ohne)} Karten, {len(prod)} Produkte)"):
        st.markdown("**Karten**")
        if ohne.empty:
            st.success("Alle Karten in deiner Sammlung haben ein Bild.")
        else:
            _karten_bilder(ohne)
        st.divider()
        st.markdown("**Produkte**")
        if prod.empty:
            st.success("Alle Produkte haben ein Bild.")
        else:
            _produkt_bilder(prod)


def _karten_bilder(ohne):
    st.caption("Die App probiert mehrere Bildquellen durch und zeigt dir, was sie gefunden hat. Erst nach deinem Klick auf "
               "„Speichern“ wird etwas übernommen. Bitte kurz prüfen, ob es die richtige Karte ist.")
    if st.button("Bilder suchen", key="bild_suchen"):
        with st.spinner("Suche läuft, das kann eine Minute dauern …"):
            st.session_state["bild_funde"] = bilder_suchen(ohne)
    funde = st.session_state.get("bild_funde")
    if funde is None:
        return
    treffer = ohne[ohne["karten_id"].map(lambda k: bool(funde.get(int(k))))]
    rest = ohne.drop(treffer.index)
    st.caption(f"Gefunden: {len(treffer)} von {len(ohne)}.")
    with st.container(key="liste_bildfunde"):
        for z in treffer.itertuples():
            c1, c2 = st.columns([14, 2], vertical_alignment="center")
            c1.markdown(zeile(z.name, f"{z.set_name} · {z.nummer}", bild=klein(funde[int(z.karten_id)])), unsafe_allow_html=True)
            c2.checkbox("Übernehmen", value=True, key=f"bild_ok_{int(z.karten_id)}")
    if len(treffer) and st.button("Ausgewählte speichern", key="bild_speichern", type="primary"):
        for z in treffer.itertuples():
            if st.session_state.get(f"bild_ok_{int(z.karten_id)}", True):
                run("UPDATE karten SET bild_pfad = %s WHERE karten_id = %s AND (bild_pfad IS NULL OR bild_pfad = '')",
                    (funde[int(z.karten_id)], int(z.karten_id)))
        st.session_state.pop("bild_funde", None)
        neu_laden()
    if len(rest):
        st.markdown("**Nichts gefunden:**")
        st.dataframe(rest[["set_name", "nummer", "name"]], hide_index=True, width="stretch",
                     column_config={"set_name": "Set", "nummer": "Nummer", "name": "Name"})


def _produkt_bilder(prod):
    st.caption("Lege die Bilder in den Ordner Bilder/Produkte im Repo. Nenne jede Datei nach der Nummer des Produkts, "
               "zum Beispiel 152.jpg oder 152.png. Die Nummer steht in der Tabelle. Danach „Bilder zuordnen“.")
    st.dataframe(prod, hide_index=True, width="stretch",
                 column_config={"produkt_id": "Nummer", "name": "Name", "art": "Art", "sprache": "Sprache"})
    if st.button("Bilder zuordnen", key="bild_zuordnen"):
        dateien = {int(d.stem): d.name for d in (PRODUKT_ORDNER.iterdir() if PRODUKT_ORDNER.exists() else [])
                   if d.stem.isdigit() and d.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")}
        passend = [int(p) for p in prod["produkt_id"] if int(p) in dateien]
        for pid in passend:
            run("UPDATE produkte SET bild_pfad = %s WHERE produkt_id = %s", (f"Bilder/Produkte/{dateien[pid]}", pid))
        if passend:
            neu_laden()
        st.warning("Es wurde keine passende Datei gefunden (Ordner Bilder/Produkte, Dateiname = Nummer, zum Beispiel 152.jpg).")
