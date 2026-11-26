"""Ansicht „Sets“: alle Sets mit der Zahl deiner Karten, neues Set anlegen."""
import pandas as pd
import psycopg2.errors
import streamlit as st

from bausteine import einfache_liste, leer_zu_none
from db import run
from design import POKEBALL, zeile


def set_zeile(r):
    datum = "" if pd.isna(r.erscheinungsdatum) else pd.Timestamp(r.erscheinungsdatum).strftime("%d.%m.%Y")
    unter = " · ".join(x for x in (None if pd.isna(r.serie) else str(r.serie), datum) if x)
    return zeile(r.name, unter, vorne=POKEBALL.format(n=40), chips=[(r.kuerzel, "leise")], anzahl=r.karten)


def zeigen():
    sets = run("""SELECT s.set_id AS kuerzel, s.name, s.serie, s.erscheinungsdatum, COALESCE(SUM(sk.anzahl), 0) AS karten
                  FROM sets s LEFT JOIN karten k ON k.set_id = s.set_id LEFT JOIN sammlung_karten sk ON sk.karten_id = k.karten_id
                  GROUP BY s.set_id, s.name, s.serie, s.erscheinungsdatum
                  ORDER BY s.erscheinungsdatum DESC NULLS LAST, s.name""")
    suche = st.text_input("Suche nach Setname", key="suche_sets")
    sets = sets[sets["name"].str.contains(suche.strip(), case=False, na=False, regex=False)]
    st.caption(f"{len(sets)} Sets. Die Zahl rechts sind deine Karten aus diesem Set.")
    einfache_liste(sets, set_zeile, "sets")

    st.subheader("Neues Set anlegen")
    with st.form("form_set", clear_on_submit=True):
        kuerzel = st.text_input("Kürzel * (z. B. sv3 oder sv3pt5)")
        name = st.text_input("Name *")
        serie = st.text_input("Serie (z. B. Karmesin & Purpur)")
        datum = st.date_input("Erscheinungsdatum (optional)", value=None)
        gesendet = st.form_submit_button("Set anlegen")
    if gesendet and (not kuerzel.strip() or not name.strip()):
        st.error("Kürzel und Name sind Pflicht.")
    elif gesendet:
        try:
            run("INSERT INTO sets (set_id, name, serie, erscheinungsdatum) VALUES (%s, %s, %s, %s)",
                (kuerzel.strip(), name.strip(), leer_zu_none(serie), datum))
            st.success(f"Set „{name.strip()}“ wurde angelegt.")
        except psycopg2.errors.UniqueViolation:
            st.error("Dieses Kürzel gibt es schon.")
