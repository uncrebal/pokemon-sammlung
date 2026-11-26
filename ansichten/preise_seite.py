"""Ansicht „Preise“: Stand der Preise, größte Preisänderungen, Preise von Hand holen oder hochladen."""
import json

import pandas as pd
import streamlit as st

import preise
from bausteine import euro, einfache_liste
from bilder import vorschau
from db import auto_preise, preise_eintragen, preisstand, run
from design import zeile

# Pro Karte der neueste und der vorletzte Preis; nur Karten der Sammlung, deren Preis sich geändert hat
AENDERUNGEN_SQL = """
WITH r AS (SELECT karten_id, datum, preis_cm, ROW_NUMBER() OVER (PARTITION BY karten_id ORDER BY datum DESC) AS rn
           FROM preis_karten WHERE preis_cm IS NOT NULL),
     m AS (SELECT karten_id, SUM(anzahl) AS anzahl FROM sammlung_karten GROUP BY karten_id)
SELECT k.name, s.name AS set_name, k.nummer, k.bild_pfad, a.preis_cm AS neu, b.preis_cm AS alt, m.anzahl,
       a.datum AS datum_neu, b.datum AS datum_alt, (a.preis_cm - b.preis_cm) * m.anzahl AS wert_diff
FROM r a JOIN r b ON b.karten_id = a.karten_id AND a.rn = 1 AND b.rn = 2
JOIN m ON m.karten_id = a.karten_id
JOIN karten k ON k.karten_id = a.karten_id JOIN sets s ON s.set_id = k.set_id
WHERE a.preis_cm <> b.preis_cm AND b.preis_cm > 0"""


def aenderung_zeile(r):
    alt, neu = float(r.alt), float(r.neu)
    pfeil = "▲" if neu > alt else "▼"
    return zeile(r.name, f"{r.set_name} · {r.nummer} · {euro(alt)} → {euro(neu)}", bild=vorschau(r.bild_pfad),
                 anzahl=r.anzahl if r.anzahl > 1 else 0, rechts_klasse="hoch" if neu > alt else "",
                 rechts=f"{pfeil} {euro(abs(neu - alt))}<br><small>{(neu - alt) / alt * 100:+.0f} %</small>")


def zeigen():
    stand = preisstand()
    st.metric("Stand der Preise", stand.strftime("%d.%m.%Y") if stand else "noch keine Preise")
    st.caption("Quelle: Cardmarket-Preisliste, Trendpreis in Euro (Reverse-Holo-Karten mit dem Reverse-Holo-Preis). "
               "Die App holt die Liste automatisch, wenn der Stand älter als heute ist.")
    ergebnis = auto_preise()
    if ergebnis.startswith("Fehler"):
        st.warning("Automatischer Abruf hat nicht geklappt. Lade die Datei unten von Hand hoch.")
        st.code(ergebnis)

    st.subheader("Preisänderungen")
    bew = run(AENDERUNGEN_SQL)
    if bew.empty:
        st.caption("Noch keine Änderungen zum vorigen Stand.")
    else:
        bew["wert_diff"] = pd.to_numeric(bew["wert_diff"])
        st.caption(f"Deine Karten mit der größten Änderung des Gesamtwerts (Preis × Anzahl), Vergleich "
                   f"{pd.Timestamp(bew['datum_alt'].max()):%d.%m.} → {pd.Timestamp(bew['datum_neu'].max()):%d.%m.%Y}. "
                   f"Insgesamt {len(bew)} Karten haben sich geändert.")
        for titel, teil in (("Gestiegen", bew[bew["wert_diff"] > 0].nlargest(8, "wert_diff")),
                            ("Gefallen", bew[bew["wert_diff"] < 0].nsmallest(8, "wert_diff"))):
            if len(teil):
                st.markdown(f"**{titel}**")
                einfache_liste(teil, aenderung_zeile, f"preis_{titel}")
    st.divider()

    if st.button("Preise jetzt von Cardmarket holen"):
        _einlesen(preise.lade_preisliste, "Abruf fehlgeschlagen. Lade die Datei stattdessen unten hoch.")
    st.divider()
    st.write("**Von Hand:** Lade `price_guide_6.json` von cardmarket.com herunter und wähle sie hier aus.")
    datei = st.file_uploader("Preisliste (price_guide_6.json)", type="json")
    if datei is not None and st.button("Hochgeladene Datei einlesen"):
        _einlesen(lambda: json.loads(datei.getvalue().decode("utf-8")), "Die Datei konnte nicht eingelesen werden.")

    zahlen = run("""SELECT
        (SELECT COUNT(*) FROM sammlung_karten sk JOIN karten k USING (karten_id) WHERE k.cm_id IS NULL AND k.preis_manuell IS NULL) AS ohne_k,
        (SELECT COUNT(*) FROM sammlung_produkte sp JOIN produkte p USING (produkt_id) WHERE p.cm_id IS NULL AND p.preis_manuell IS NULL) AS ohne_p,
        (SELECT COUNT(*) FROM sammlung_karten sk JOIN karten k USING (karten_id) WHERE k.cm_id IS NULL AND k.preis_manuell IS NOT NULL) AS hand_k,
        (SELECT COUNT(*) FROM sammlung_produkte sp JOIN produkte p USING (produkt_id) WHERE p.cm_id IS NULL AND p.preis_manuell IS NOT NULL) AS hand_p
        """).iloc[0]
    st.caption(f"Ganz ohne Preis: {zahlen.ohne_k} Karten-Einträge, {zahlen.ohne_p} Produkte.")
    st.caption(f"Mit Handpreis (Cardmarket führt sie nicht, Preis aus Collectr bzw. Excel, Stand 26.10.2026): {zahlen.hand_k} "
               f"Karten-Einträge, {zahlen.hand_p} Produkte. Ändern geht bei der Karte bzw. dem Produkt unter „bearbeiten“.")


def _einlesen(laden, fehlermeldung):
    try:
        stand, n_k, n_p = preise_eintragen(laden())
        st.success(f"Stand {stand:%d.%m.%Y}: {n_k} Karten und {n_p} Produkte aktualisiert.")
    except Exception as fehler:
        st.error(fehlermeldung)
        st.code(str(fehler))
