"""Ansicht „Hinzufügen“: ein Reiter für alles Neue – eine Karte, mehrere Karten auf einmal oder ein Produkt."""
import streamlit as st

from ansichten import karte_hinzufuegen, mehrere, produkte

ARTEN = {
    "Eine Karte": karte_hinzufuegen.zeigen,
    "Mehrere Karten": mehrere.zeigen,
    "Produkt": produkte.hinzufuegen,
}


def zeigen():
    if st.session_state.get("hinzufuegen_art") not in ARTEN:      # neu geöffnet oder F5: aus der Adresse nehmen (?art=…)
        art = st.query_params.get("art")
        st.session_state["hinzufuegen_art"] = art if art in ARTEN else "Eine Karte"
    art = st.radio("Was möchtest du hinzufügen?", list(ARTEN), horizontal=True, key="hinzufuegen_art")
    st.query_params["art"] = art
    ARTEN[art]()      # nur der gewählte Teil wird berechnet
