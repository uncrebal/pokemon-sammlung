"""Pokémon-Sammlung – die Startdatei.
Baut Kopfzeile, Handy-Schalter, Suche und Menü auf und zeigt dann die gewählte Ansicht.

Aufbau der App (alle Dateien liegen neben app.py):
  db.py        Datenbank: Verbindung, Lesen/Schreiben, Sammlung mit Preisen, automatischer Preisabruf
  katalog.py   Kartenkatalog: Karten suchen, Links erkennen, Katalogkarten in die Sammlung übernehmen
  bilder.py    Bildadressen, Vorschaubilder, eigene Fotos, Suche nach fehlenden Bildern
  design.py    Aussehen (Farben, Kopfzeile) und die HTML-Bausteine für Listen
  bausteine.py Gemeinsames: Auswahllisten, Euro-Format, Cardmarket-Links, Liste mit Details
  suche.py     Globale Suche oben
  preise.py    Cardmarket-Preisliste laden und eintragen (auch für den täglichen GitHub-Job)
  ansichten/   eine Datei pro Menüpunkt
"""
import time

import streamlit as st

T0 = time.perf_counter()   # Zeitmessung: Start des Seitenaufbaus
st.set_page_config(page_title="Pokémon-Sammlung", page_icon="🎴", layout="wide")

import db  # noqa: E402  (erst nach set_page_config importieren)
import design  # noqa: E402
import suche  # noqa: E402
from ansichten import hinzufuegen, karten, preise_seite, produkte, sets, uebersicht, vollstaendigkeit  # noqa: E402

ANSICHTEN = {
    "Übersicht": uebersicht.zeigen,
    "Karten": karten.zeigen,
    "Produkte": produkte.zeigen,
    "Hinzufügen": hinzufuegen.zeigen,
    "Vollständigkeit": vollstaendigkeit.zeigen,
    "Sets": sets.zeigen,
    "Preise": preise_seite.zeigen,
}

try:
    db.run("SELECT 1")
except Exception as fehler:
    st.error("Keine Verbindung zur Datenbank. Stimmen die Daten in den Secrets (secrets.toml)?")
    st.code(str(fehler))
    st.stop()
db.auto_preise()      # neue Cardmarket-Preise holen, wenn der Stand älter als heute ist (höchstens alle 6 Stunden)

# Handy-Ansicht: ein Link mit ?m=1 am Ende öffnet sie direkt (gut als Lesezeichen)
if "mobil" not in st.session_state:
    st.session_state["mobil"] = st.query_params.get("m") == "1"
design.anwenden(handy=st.session_state["mobil"])
with st.sidebar:      # Seitenleiste (am Handy über » oben links)
    handy = st.toggle("📱 Handy-Ansicht", key="mobil",
                      help="Größere Knöpfe, Menü als Auswahlliste. Tipp: Den Link mit ?m=1 am Ende als Lesezeichen speichern.")
    if st.button("🔄 Daten neu laden"):
        db.cache_leeren(alles=True)
        st.rerun()
    st.caption("Änderungen in der App sind sofort sichtbar. Änderungen direkt in der Datenbank (DBeaver) erscheinen nach "
               "spätestens 1 Stunde oder mit diesem Knopf.")
if handy:
    st.query_params["m"] = "1"
elif "m" in st.query_params:
    del st.query_params["m"]

st.text_input("Globale Suche", key="global_suche", label_visibility="collapsed",
              placeholder="🔍 Suche: Karte oder Produkt, z. B. Glurak")
such_platz = st.container()       # hier erscheinen die Treffer, über der gewählten Ansicht
if st.session_state.get("ansicht") not in ANSICHTEN:      # neu geöffnet oder F5: die Seite aus der Adresse nehmen (?seite=…)
    seite = st.query_params.get("seite")
    st.session_state["ansicht"] = seite if seite in ANSICHTEN else "Übersicht"
if handy:
    aktiv = st.selectbox("Ansicht", list(ANSICHTEN), key="ansicht", label_visibility="collapsed")
else:
    aktiv = st.radio("Ansicht", list(ANSICHTEN), horizontal=True, key="ansicht", label_visibility="collapsed")
st.query_params["seite"] = aktiv
if aktiv != "Hinzufügen" and "art" in st.query_params:
    del st.query_params["art"]
suche.treffer_zeigen(such_platz)

ANSICHTEN[aktiv]()      # nur die gewählte Ansicht wird berechnet, das hält die App schnell
st.caption(f"Seite in {time.perf_counter() - T0:.2f} s berechnet")
