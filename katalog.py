"""Kartenkatalog (aus TCGdex): Karten finden (Name, Nummer, Link) und in die Sammlung übernehmen."""
import re
import threading
import unicodedata
import urllib.parse
from datetime import date

import pandas as pd
import streamlit as st

import preise
from bilder import bild_url
from db import NORM_NR, run_katalog, transaktion

KATALOG_SELECT = """
SELECT k.tcg_set, k.nr, k.tcg_set || '|' || k.nr AS kid, COALESCE(k.name_de, k.name_en) AS name, k.name_en,
       (k.name_de IS NOT NULL) AS hat_de, COALESCE(s.name_de, s.name_en, s.tcg_id) AS set_name,
       COALESCE(s.serie_de, s.serie_en) AS serie_name, s.serie_id, s.anzahl, s.erscheinung, s.set_id AS unser_set,
       k.seltenheit, k.varianten, k.cm_id, k.cm_unsicher
FROM katalog_karten k JOIN katalog_sets s ON s.tcg_id = k.tcg_set"""
REIHENFOLGE = " ORDER BY s.erscheinung DESC NULLS LAST, k.tcg_set, k.nr"
PRODUKT_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_6.json"

# Der ganze Katalog mit den Spalten, die die globale Suche braucht (wird einmal am Tag geladen)
SUCH_SQL = """
SELECT k.tcg_set, k.nr, k.tcg_set || '|' || k.nr AS kid, COALESCE(k.name_de, k.name_en) AS name, k.name_en,
       (k.name_de IS NOT NULL) AS hat_de, COALESCE(s.name_de, s.name_en, s.tcg_id) AS set_name, s.serie_id, s.set_id AS unser_set,
       k.seltenheit, """ + NORM_NR.format(x="k.nr") + """ AS nr_norm
FROM katalog_karten k JOIN katalog_sets s ON s.tcg_id = k.tcg_set""" + REIHENFOLGE


def katalog_bild(k, groesse="high"):
    """Bild einer Katalogkarte: deutsch, wenn es die Karte auf Deutsch gibt, sonst englisch."""
    return bild_url("de" if k["hat_de"] else "en", k["serie_id"], k["tcg_set"], k["nr"], groesse)


def variante_vorschlag(k):
    """Die Variante, die der Katalog für die Karte zuerst nennt (Normal, Holo oder Reverse Holo)."""
    arten = [a for a in str(k["varianten"]).split(",") if a in ("normal", "holo", "reverse")]
    return {"normal": "Normal", "holo": "Holo", "reverse": "Reverse Holo"}[arten[0]] if arten else "Normal"


def suchen(name="", tcg_set=None, nr="", limit=100):
    """Karten im Katalog nach Name (deutsch oder englisch), Set und Nummer."""
    bedingungen, parameter = [], []
    if name.strip():
        bedingungen.append("(k.name_de ILIKE %s OR k.name_en ILIKE %s)")
        parameter += [f"%{name.strip()}%"] * 2
    if tcg_set:
        bedingungen.append("k.tcg_set = %s")
        parameter.append(tcg_set)
    if nr.strip():
        bedingungen.append(NORM_NR.format(x="k.nr") + " = %s")
        parameter.append(nr.strip().lstrip("0") or "0")
    return run_katalog(KATALOG_SELECT + " WHERE " + " AND ".join(bedingungen or ["TRUE"]) + REIHENFOLGE + f" LIMIT {int(limit)}",
               tuple(parameter))


def im_katalog_suchen(begriff, ohne=frozenset(), limit=6):
    """Katalogkarten, deren deutscher oder englischer Name begriff enthält. ohne = {(set_id, nr_norm)}: diese weglassen.
    Fragt die Datenbank höchstens einmal am Tag; die Suche selbst läuft in den geladenen Daten."""
    alle = run_katalog(SUCH_SQL)
    passt = (alle["name"].str.contains(begriff, case=False, regex=False, na=False)
             | alle["name_en"].str.contains(begriff, case=False, regex=False, na=False))
    df = alle[passt]
    df = df.loc[[(s, n) not in ohne for s, n in zip(df["unser_set"], df["nr_norm"])]]
    return df.head(limit).reset_index(drop=True)


def _norm(text):
    """„Flabébé's“ -> „flabebes“: nur Kleinbuchstaben und Ziffern, Akzente weg."""
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _name_passt(woerter, name_en):
    """Passt der Kartenname aus dem Link (z. B. [„Basic“, „Fire“, „Energy“]) zum englischen Namen im Katalog?
    Es reicht ein Wort mit mindestens 3 Buchstaben (bei „Basic Fire Energy“ heißt die Karte im Katalog nur „Fire Energy“)."""
    ziel = _norm(name_en)
    lange = [_norm(w) for w in woerter if len(_norm(w)) >= 3]
    return any(w in ziel for w in lange) if lange else _norm("".join(woerter)) in ziel


# Für Cardmarket-Links: zusätzlich Set-Kürzel, Nummer in Großbuchstaben und Set-Name ohne Sonderzeichen
SET_SLUG = "regexp_replace(translate(lower(s.name_en), 'éèêáàâíóúüöäñ', 'eeeaaaiouuoan'), '[^a-z0-9]', '', 'g')"
LINK_SELECT = KATALOG_SELECT.replace(
    "\nFROM katalog_karten", ", upper(replace(s.kuerzel, ':', '')) AS set_kuerzel, upper(" + NORM_NR.format(x="k.nr")
    + ") AS nr_gross, " + SET_SLUG + " AS set_slug\nFROM katalog_karten", 1)


def _code_zerlegen(code):
    """Cardmarket-Code -> {Kartennummer: mögliche Set-Kürzel}. Wo das Kürzel endet, steht nicht im Link:
    „GENRC29“ kann GEN + RC29 (Radiant Collection) oder GENRC + 29 sein, „OBF125“ ist OBF + 125. Darum alle Möglichkeiten."""
    teile = re.fullmatch(r"([A-Za-z]*)(\d+)", code)
    if not teile:
        return {}
    buchstaben, ziffern = teile.group(1).upper(), teile.group(2)
    moeglich = {}
    for i in range(len(buchstaben) + 1):
        vorsatz = buchstaben[i:]
        nummern = {vorsatz + ziffern, vorsatz + (ziffern.lstrip("0") or "0")} if vorsatz else {ziffern.lstrip("0") or "0"}
        for nr in nummern:
            moeglich.setdefault(nr, set()).add(buchstaben[:i])
    return moeglich


def link_zu_karte(url):
    """Erkennt eine Karte an einem Cardmarket- oder TCGdex-Link. Gibt (Treffer oder None, Hinweis) zurück."""
    u = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    host, pfad, abfrage = u.netloc.lower(), urllib.parse.unquote(u.path), urllib.parse.parse_qs(u.query)
    if "cardmarket" in host:
        if abfrage.get("idProduct", [""])[0].isdigit():     # Link mit Produktnummer: eindeutig
            df = run_katalog(KATALOG_SELECT + " WHERE k.cm_id = %s ORDER BY s.erscheinung DESC", (int(abfrage["idProduct"][0]),))
            return (df, "") if len(df) else (None, "Diese Cardmarket-Nummer ist nicht im Katalog. Bitte über die Suche hinzufügen.")
        m = re.search(r"/Singles/([^/]+)/([^/?#]+)", pfad)
        if not m:
            return None, "Das ist kein Link zu einer Einzelkarte (er sollte „…/Singles/…“ enthalten)."
        set_slug, karte_slug = m.groups()
        teile = karte_slug.split("-")
        moeglich = _code_zerlegen(teile[-1])
        if not moeglich:
            return None, "Die Kartennummer im Link wurde nicht erkannt. Bitte über die Suche hinzufügen."
        woerter = [w for w in teile[:-1] if not re.fullmatch(r"V\d+", w)]
        slug = _norm(set_slug)
        df = run_katalog(LINK_SELECT + " WHERE upper(" + NORM_NR.format(x="k.nr") + ") = ANY(%s) AND (upper(replace(s.kuerzel, ':', '')) "
                         "= ANY(%s) OR " + SET_SLUG + " = %s) ORDER BY s.erscheinung DESC",
                         (sorted(moeglich), sorted(set().union(*moeglich.values())), slug))
        # Nur Treffer, bei denen Set und Nummer zusammenpassen: Set am Namen im Link erkannt oder Kürzel + Nummer ergeben den Code
        df = df.loc[[s == slug or k in moeglich.get(nr, ()) for s, k, nr in zip(df["set_slug"], df["set_kuerzel"], df["nr_gross"])]]
        if woerter:   # der Kartenname im Link muss passen (sonst kam z. B. Zapdos Nr. 29 statt Pikachu RC29)
            df = df[df["name_en"].map(lambda n: _name_passt(woerter, n))]
        if df.empty:
            return None, (f"Im Katalog wurde keine Karte „{' '.join(woerter)}“ mit dem Code {teile[-1]} gefunden. "
                          "Bitte über die Suche hinzufügen.")
        # Die Cardmarket-Nummer aus dem Katalog zeigt manchmal auf eine andere Version (z. B. Pikachu GEN26 statt RC29):
        # wenn möglich die Nummer nehmen, die genau zum Link gehört, und als sicher markieren
        version = next((int(w[1:]) for w in teile[:-1] if re.fullmatch(r"V\d+", w)), None)
        genau = [_cm_id_zum_link(c, _norm("".join(woerter)), version) for c in df["cm_id"]]
        df = df.assign(cm_id=[g or c for g, c in zip(genau, df["cm_id"])],
                       cm_unsicher=[False if g else u for g, u in zip(genau, df["cm_unsicher"])])
        # Bei mehreren Treffern zuerst die genauere Nummer (RC29 vor 29)
        df = df.assign(_vorsatz=df["nr_gross"].str.len() - df["nr_gross"].str.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").str.len())
        return df.sort_values("_vorsatz", ascending=False, kind="stable").drop(columns="_vorsatz").reset_index(drop=True), ""
    if "tcgdex" in host:
        m = re.search(r"/(?:cards|sets)/([^?#]+)", pfad)
        if not m:
            return None, "Der TCGdex-Link enthält keine Karte."
        teile = [t for t in m.group(1).split("/") if t]
        tcg_set, nr = (teile[0], teile[1]) if len(teile) >= 2 else (teile[0].rpartition("-")[0], teile[0].rpartition("-")[2])
        df = run_katalog(KATALOG_SELECT + " WHERE k.tcg_set = %s AND k.nr = %s", (tcg_set, nr))
        return (df, "") if len(df) else (None, f"Karte {tcg_set} {nr} nicht im Katalog.")
    return None, "Dieser Link wird nicht erkannt. Unterstützt sind Cardmarket- und TCGdex-Links."


def zeile_zu_treffern(text):
    """Eine Eingabezeile (Link oder Kartenname, optional mit Nummer am Ende, z. B. „Pikachu 025“) -> (Treffer, Hinweis)."""
    if "://" in text or "cardmarket" in text.lower() or "tcgdex" in text.lower():
        return link_zu_karte(text)
    teile, nr = text.split(), ""
    if len(teile) > 1 and re.fullmatch(r"[A-Za-z]{0,3}\d+(/\d+)?", teile[-1]):
        nr, teile = re.sub(r"^[A-Za-z]*", "", teile[-1]).split("/")[0], teile[:-1]
    df = suchen(" ".join(teile), nr=nr, limit=30)
    return (df, "") if len(df) else (None, "Nichts gefunden.")


# ---------------------------------------------------------------
# Katalogkarte in die Sammlung übernehmen
# ---------------------------------------------------------------

@st.cache_resource(ttl=24 * 3600, show_spinner=False)
def _preisliste():
    """Cardmarket-Preisliste (für den sofortigen Preis neu hinzugefügter Karten), einmal am Tag geladen."""
    daten = preise.lade_preisliste()
    return date.fromisoformat(daten["createdAt"][:10]), {p["idProduct"]: p for p in daten["priceGuides"]}


@st.cache_resource(ttl=24 * 3600, show_spinner=False)
def _produktliste():
    """Cardmarket-Produktliste aller Einzelkarten, einmal am Tag geladen. Gibt zurück:
    {idProduct: Expansion} und {(Expansion, Name): [idProduct, …] aufsteigend}. Gleichnamige Karten eines Sets
    nummeriert Cardmarket in dieser Reihenfolge als V1, V2, … (im Link z. B. „Pikachu-V2-GENRC29“)."""
    expansion, versionen = {}, {}
    for p in preise.lade_preisliste(PRODUKT_URL)["products"]:
        expansion[p["idProduct"]] = p["idExpansion"]
        versionen.setdefault((p["idExpansion"], _norm(p["name"].split(" [")[0])), []).append(p["idProduct"])
    for ids in versionen.values():
        ids.sort()
    return expansion, versionen


def _cm_id_zum_link(cm_id, name, version):
    """Die Cardmarket-Nummer, die genau zum Link gehört (Name und V-Nummer im selben Set), oder None, wenn das nicht eindeutig geht.
    Das Set kommt von der Cardmarket-Nummer aus dem Katalog: Die zeigt manchmal auf die falsche Version, aber ins richtige Set."""
    if cm_id is None or pd.isna(cm_id):
        return None
    liste = _versuche(_produktliste)
    if not liste:
        return None
    expansion, versionen = liste
    ids = versionen.get((expansion.get(int(cm_id)), name), [])
    if version is None:
        return ids[0] if len(ids) == 1 else None
    return ids[version - 1] if 0 < version <= len(ids) else None


@st.cache_resource(ttl=24 * 3600, show_spinner=False)
def vorwaermen():
    """Lädt Preis- und Produktliste im Hintergrund, sobald man „Karte hinzufügen“ öffnet. Dann ist das Hinzufügen schneller."""
    threading.Thread(target=lambda: (_versuche(_preisliste), _versuche(_produktliste)), daemon=True).start()
    return True


def _versuche(funktion):
    try:
        return funktion()
    except Exception:
        return None


def _karte_sicherstellen(cur, k):
    """Sucht die Katalogkarte bei uns oder legt sie an (samt Set und Rarität). Gibt (karten_id, cm_id) zurück."""
    set_id = k["unser_set"]
    if not set_id:   # Set gibt es bei uns noch nicht: aus dem Katalog anlegen
        set_id = k["tcg_set"]
        cur.execute("INSERT INTO sets (set_id, name, serie, erscheinungsdatum) VALUES (%s, %s, %s, %s) ON CONFLICT (set_id) DO NOTHING",
                    (set_id, k["set_name"], k["serie_name"], None if pd.isna(k["erscheinung"]) else k["erscheinung"]))
    cur.execute("SELECT karten_id, name FROM karten WHERE set_id = %s AND " + NORM_NR.format(x="nummer") + " = %s ORDER BY karten_id",
                (set_id, str(k["nr"]).lstrip("0") or "0"))
    vorhanden = cur.fetchall()
    gleich = [z for z in vorhanden if z[1].lower() in {str(k["name"]).lower(), str(k["name_en"]).lower()}]
    treffer = (gleich or vorhanden or [None])[0]
    cm_id = None if pd.isna(k["cm_id"]) else int(k["cm_id"])
    unsicher = bool(cm_id) and bool(k["cm_unsicher"] == True)      # noqa: E712 (Wert kann auch None sein)
    bild_de = bild_url("de", k["serie_id"], k["tcg_set"], k["nr"]) if k["hat_de"] else None
    if treffer:   # Karte gibt es schon: fehlende (oder unsichere, wenn jetzt eine sichere da ist) Cardmarket-Nummer und deutsches Bild ergänzen
        karten_id = treffer[0]
        besser = cm_id is not None and not unsicher
        cur.execute("""UPDATE karten SET cm_id = CASE WHEN cm_id IS NULL OR (%s AND cm_unsicher) THEN %s ELSE cm_id END,
                              cm_unsicher = CASE WHEN cm_id IS NULL OR (%s AND cm_unsicher) THEN %s ELSE cm_unsicher END,
                              bild_de = COALESCE(bild_de, %s) WHERE karten_id = %s""",
                    (besser, cm_id, besser, unsicher, bild_de, karten_id))
        return karten_id, cm_id
    raritaet_id = None
    if isinstance(k["seltenheit"], str) and k["seltenheit"]:
        cur.execute("SELECT raritaet_id FROM raritaeten WHERE lower(name) = lower(%s)", (k["seltenheit"],))
        z = cur.fetchone()
        if not z:
            cur.execute("INSERT INTO raritaeten (name) VALUES (%s) RETURNING raritaet_id", (k["seltenheit"],))
            z = cur.fetchone()
        raritaet_id = z[0]
    nummer = f"{str(k['nr']).zfill(3)}/{int(k['anzahl'])}" if str(k["nr"]).isdigit() and not pd.isna(k["anzahl"]) else str(k["nr"])
    bild_en = bild_url("en", k["serie_id"], k["tcg_set"], k["nr"]) if isinstance(k["name_en"], str) else None
    cur.execute("""INSERT INTO karten (name, nummer, set_id, raritaet_id, bild_pfad, bild_de, cm_id, cm_unsicher)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING karten_id""",
                (k["name"], nummer, set_id, raritaet_id, bild_en, bild_de, cm_id, unsicher))
    return cur.fetchone()[0], cm_id


def in_sammlung(cur, karten_id, d):
    """Trägt eine Karte in die Sammlung ein. Gibt es dieselbe Sprache/Zustand/Variante schon, wird die Anzahl erhöht."""
    cur.execute("""INSERT INTO sammlung_karten (karten_id, anzahl, sprache, zustand, variante, notiz) VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (karten_id, sprache, zustand, variante)
                   DO UPDATE SET anzahl = sammlung_karten.anzahl + EXCLUDED.anzahl, notiz = COALESCE(EXCLUDED.notiz, sammlung_karten.notiz)""",
                (karten_id, d["anzahl"], d["sprache"], d["zustand"], d["variante"], d["notiz"]))


def add_karte_katalog(k, d):
    """Katalogkarte k mit den Angaben d (Sprache, Variante, Zustand, Anzahl, Notiz) in die Sammlung eintragen.
    Gibt True zurück, wenn der aktuelle Preis gleich mit eingetragen werden konnte."""
    with transaktion() as cur:
        karten_id, cm_id = _karte_sicherstellen(cur, k)
        in_sammlung(cur, karten_id, d)
    if not cm_id:
        return False
    try:   # Preis sofort nachtragen (eigene kleine Transaktion, ein Fehler hier ist unkritisch)
        stand, liste = _preisliste()
        p = liste.get(cm_id)
        if not p:
            return False
        with transaktion() as cur:
            cur.execute("""INSERT INTO preis_karten (karten_id, datum, preis_cm, preis_ab, preis_reverse) VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (karten_id, datum) DO UPDATE
                           SET preis_cm = EXCLUDED.preis_cm, preis_ab = EXCLUDED.preis_ab, preis_reverse = EXCLUDED.preis_reverse""",
                        (karten_id, stand, p.get("trend"), p.get("low"), p.get("trend-holo")))
        return True
    except Exception:
        return False
