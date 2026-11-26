"""Datenbank: Verbindung, Lesen und Schreiben, die Sammlung mit Preisen, automatischer Preisabruf."""
from contextlib import contextmanager
from datetime import date

import pandas as pd
import psycopg2
import psycopg2.pool
import streamlit as st

import preise

# Kartennummer ohne führende Nullen und ohne „/Setgröße“, damit „025/198“ und „25“ gleich sind (für SQL)
NORM_NR = "COALESCE(NULLIF(regexp_replace(split_part({x}, '/', 1), '^0+', ''), ''), '0')"


def norm_nr(nummer):
    """Dasselbe wie NORM_NR, aber in Python: „025/198“ -> „25“."""
    return str(nummer).split("/")[0].lstrip("0") or "0"


# ---------------------------------------------------------------
# Verbindung
# ---------------------------------------------------------------

@st.cache_resource
def _pool():
    """Ein kleiner Vorrat offener Verbindungen. Eine neue Verbindung nach Irland dauert lange, eine vorhandene nicht."""
    return psycopg2.pool.ThreadedConnectionPool(
        1, 4, keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3, **st.secrets["db"]
    )


def connect(pruefen=True):
    """Eine offene Verbindung aus dem Vorrat. Nach Gebrauch mit zurueck(conn) zurückgeben.
    pruefen=False spart den Probe-Aufruf nach Irland (beim Lesen wird stattdessen bei einem Fehler neu versucht)."""
    pool = _pool()
    for _ in range(3):
        conn = pool.getconn()
        try:
            if not conn.closed:
                if not pruefen:
                    return conn
                with conn.cursor() as cur:   # Verbindung noch lebendig?
                    cur.execute("SELECT 1")
                conn.rollback()
                return conn
        except Exception:
            pass
        pool.putconn(conn, close=True)     # kaputte Verbindung wegwerfen, neue holen
    raise psycopg2.OperationalError("Keine Verbindung zur Datenbank möglich.")


def zurueck(conn):
    try:
        if not conn.closed:
            conn.rollback()
    finally:
        _pool().putconn(conn, close=conn.closed)


# ---------------------------------------------------------------
# Lesen und Schreiben
# ---------------------------------------------------------------

def _abfrage(sql, params):
    for versuch in range(2):
        conn = connect(pruefen=False)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(sql, params)
                return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            conn.close()          # Verbindung war abgerissen: wegwerfen und einmal mit einer neuen versuchen
            if versuch:
                raise
        finally:
            zurueck(conn)


@st.cache_data(ttl=3600, show_spinner=False)
def _lesen(sql, params):
    return _abfrage(sql, params)


@st.cache_data(ttl=24 * 3600, max_entries=500, show_spinner=False)
def _lesen_katalog(sql, params):
    return _abfrage(sql, params)


def cache_leeren(alles=False):
    """Nach jeder Änderung aufrufen, damit die Anzeige die neuen Daten zeigt.
    Der Katalog bleibt gespeichert (die App ändert ihn nie); alles=True leert auch ihn (Knopf „Daten neu laden“)."""
    _lesen.clear()
    if alles:
        _lesen_katalog.clear()


def run(sql, params=None):
    """SELECT: gibt eine Tabelle zurück (bis 1 Stunde zwischengespeichert, jede Änderung leert den Speicher).
    Änderungen (INSERT, UPDATE, DELETE) werden sofort gespeichert."""
    if sql.lstrip().upper().startswith(("SELECT", "WITH")):
        return _lesen(sql, tuple(params) if params is not None else None)
    with transaktion() as cur:
        cur.execute(sql, params)


def run_katalog(sql, params=None):
    """SELECT nur auf den Katalog (katalog_karten, katalog_sets): 1 Tag zwischengespeichert, bleibt beim Speichern erhalten."""
    return _lesen_katalog(sql, tuple(params) if params is not None else None)


@contextmanager
def transaktion():
    """Mehrere Änderungen am Stück: Entweder wird alles gespeichert oder (bei einem Fehler) nichts.
    Benutzung:  with transaktion() as cur:  cur.execute(...)"""
    conn = connect()
    try:
        with conn, conn.cursor() as cur:   # 'with conn' = Commit, bei Fehler Rollback
            yield cur
    finally:
        zurueck(conn)
    cache_leeren()


def neu_laden():
    """Seite neu aufbauen. Der neue Zähler setzt angeklickte Tabellenzeilen zurück."""
    st.session_state["v"] = st.session_state.get("v", 0) + 1
    st.rerun()


# ---------------------------------------------------------------
# Die Sammlung mit Preisen
# Preis: eigener Preis (Handpreis) vor Cardmarket; Reverse-Varianten mit dem Reverse-Preis
# ---------------------------------------------------------------

KARTEN_SQL = """
SELECT sk.id, k.name, k.nummer, s.name AS set_name, r.name AS raritaet, sk.sprache, sk.variante, sk.zustand, sk.anzahl, sk.notiz,
       k.bild_pfad, k.bild_de, k.karten_id, k.set_id, k.raritaet_id, k.cm_id, k.preis_manuell AS handpreis,
       COALESCE(k.preis_manuell, CASE WHEN sk.variante LIKE '%%Reverse%%' THEN COALESCE(pr.preis_reverse, pr.preis_cm)
                                      ELSE pr.preis_cm END) AS preis,
       CASE WHEN k.preis_manuell IS NOT NULL THEN 'Handpreis' WHEN k.cm_unsicher THEN 'prüfen' ELSE '' END AS preis_zuordnung
FROM sammlung_karten sk
JOIN karten k ON k.karten_id = sk.karten_id
JOIN sets s ON s.set_id = k.set_id
LEFT JOIN raritaeten r ON r.raritaet_id = k.raritaet_id
LEFT JOIN LATERAL (SELECT preis_cm, preis_reverse FROM preis_karten x
                   WHERE x.karten_id = k.karten_id ORDER BY datum DESC LIMIT 1) pr ON TRUE
ORDER BY s.erscheinungsdatum DESC NULLS LAST, k.nummer"""

PRODUKTE_SQL = """
SELECT p.produkt_id, p.name, t.typ_id, t.name AS typ, p.sprache, sp.anzahl, sp.kaufpreis, t.uvp, p.bild_pfad, p.cm_id,
       p.preis_manuell AS handpreis, COALESCE(p.preis_manuell, pr.preis_cm) AS preis,
       CASE WHEN p.preis_manuell IS NOT NULL THEN 'Handpreis' WHEN p.cm_unsicher THEN 'prüfen' ELSE '' END AS preis_zuordnung
FROM sammlung_produkte sp
JOIN produkte p ON p.produkt_id = sp.produkt_id
JOIN produkt_typen t ON t.typ_id = p.typ_id
LEFT JOIN LATERAL (SELECT preis_cm FROM preis_produkte x
                   WHERE x.produkt_id = p.produkt_id ORDER BY datum DESC LIMIT 1) pr ON TRUE
ORDER BY t.typ_id, p.name"""


def karten_der_sammlung(suche=""):
    """Alle Karten der Sammlung (optional nur Namen, die den Suchtext enthalten), mit Preis und Wert.
    Die Datenbank wird nur einmal gefragt; die Suche läuft danach in den geladenen Daten (geht viel schneller)."""
    df = run(KARTEN_SQL)
    if suche and suche.strip():
        df = df[df["name"].str.contains(suche.strip(), case=False, regex=False, na=False)].reset_index(drop=True)
    df["preis"] = pd.to_numeric(df["preis"])
    df["wert"] = df["preis"] * df["anzahl"]
    return df


def produkte_der_sammlung():
    """Alle Produkte der Sammlung mit Preis, Kaufpreis, UVP der Art und Wert."""
    df = run(PRODUKTE_SQL)
    for spalte in ("preis", "kaufpreis", "uvp"):
        df[spalte] = pd.to_numeric(df[spalte])
    df["wert"] = df["preis"] * df["anzahl"]
    return df


# ---------------------------------------------------------------
# Preise von Cardmarket
# ---------------------------------------------------------------

def preisstand():
    """Datum der neuesten gespeicherten Preise (oder None)."""
    d = run("SELECT MAX(datum) AS d FROM preis_karten")["d"][0]
    return None if pd.isna(d) else d


def preise_eintragen(daten):
    """Schreibt eine Cardmarket-Preisliste in die Datenbank. Gibt (Stand, Anzahl Karten, Anzahl Produkte) zurück."""
    conn = connect()
    try:
        return preise.aktualisiere_preise(conn, daten)
    finally:
        zurueck(conn)
        cache_leeren()


@st.cache_resource(ttl=6 * 3600, show_spinner="Preise werden aktualisiert …")
def auto_preise():
    """Holt höchstens alle 6 Stunden neue Preise: wenn der Stand älter als heute ist
    oder Karten eine Cardmarket-Nummer, aber noch keinen Preis haben (z. B. nach einem SQL-Update)."""
    stand = preisstand()
    fehlt = not run("""SELECT 1 FROM karten k WHERE k.cm_id IS NOT NULL
                       AND NOT EXISTS (SELECT 1 FROM preis_karten p WHERE p.karten_id = k.karten_id) LIMIT 1""").empty
    if stand is not None and stand >= date.today() and not fehlt:
        return "aktuell"
    try:
        preise_eintragen(preise.lade_preisliste())
        return "aktualisiert"
    except Exception as fehler:  # z. B. Download gesperrt: Die App läuft trotzdem weiter
        return f"Fehler: {fehler}"
