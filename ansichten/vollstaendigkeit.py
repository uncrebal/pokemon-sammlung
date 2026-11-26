"""Ansicht „Vollständigkeit“: Wie viel von jedem Set du hast, und welche Karten noch fehlen."""
import html

import pandas as pd
import streamlit as st

from bausteine import cm_link_oder_suche, einfache_liste, gewaehlte_zeile, liste_mit_auswahl, mit_punkt
from bilder import bild_url
from db import NORM_NR, run
from design import zeile

# Eine Karte des Katalogs gilt als vorhanden, wenn du im selben Set eine Karte mit derselben Nummer hast
HAB_ICH = ("EXISTS (SELECT 1 FROM karten k JOIN sammlung_karten sk ON sk.karten_id = k.karten_id "
           "WHERE k.set_id = s.set_id AND " + NORM_NR.format(x="k.nummer") + " = " + NORM_NR.format(x="kk.nr") + ")")

# Deine Nummern pro Set werden einmal vorbereitet und dann in einem Rutsch mit dem Katalog verglichen (schneller als pro Karte)
SETS_SQL = f"""
WITH meine AS (SELECT DISTINCT k.set_id, {NORM_NR.format(x="k.nummer")} AS nr
               FROM karten k JOIN sammlung_karten sk ON sk.karten_id = k.karten_id)
SELECT s.tcg_id, COALESCE(s.name_de, s.name_en, s.tcg_id) AS set_name, s.erscheinung, s.serie_id,
       COUNT(kk.tcg_set) AS gesamt, COUNT(m.nr) AS besitz
FROM katalog_sets s
LEFT JOIN katalog_karten kk ON kk.tcg_set = s.tcg_id
LEFT JOIN meine m ON m.set_id = s.set_id AND m.nr = {NORM_NR.format(x="kk.nr")}
WHERE s.set_id IN (SELECT set_id FROM meine)
GROUP BY s.tcg_id, s.name_de, s.name_en, s.erscheinung, s.serie_id
ORDER BY s.erscheinung DESC NULLS LAST"""

FEHLEN_SQL = f"""
SELECT kk.nr, COALESCE(kk.name_de, kk.name_en) AS name, kk.name_en, kk.seltenheit, kk.cm_id
FROM katalog_karten kk JOIN katalog_sets s ON s.tcg_id = kk.tcg_set
WHERE kk.tcg_set = %s AND NOT {HAB_ICH}
ORDER BY kk.nr"""


def set_zeile(r):
    prozent = 0 if pd.isna(r.prozent) else float(r.prozent)
    farbe = "#2E9E5B" if prozent >= 100 else ("#F2A900" if prozent >= 50 else "#D32F2F")
    return zeile(r.set_name, f"{int(r.besitz)} von {int(r.gesamt)} Karten · {int(r.gesamt - r.besitz)} fehlen",
                 vorne=f'<div class="prozent" style="border-color:{farbe}">{prozent:.0f}%</div>',
                 hinten=f'<div class="balken"><i style="width:{min(prozent, 100):.1f}%;background:{farbe}"></i></div>')


def fehlt_zeile(r):
    return zeile(r.name, f"Nr. {r.nr}{mit_punkt(r.seltenheit)}", bild=r.bild,
                 hinten=f'<a class="cmlink" href="{html.escape(r.cm)}" target="_blank">Cardmarket ↗</a>')


def zeigen():
    voll = run(SETS_SQL)
    if voll.empty:
        st.info("Noch keine Karten in Sets, die im Katalog vorkommen.")
        return
    voll["prozent"] = (voll["besitz"] / voll["gesamt"].where(voll["gesamt"] > 0) * 100).round(1)
    z = gewaehlte_zeile(voll, "tcg_id", "voll", "← Zurück zu allen Sets")     # ein Set ist geöffnet: fehlende Karten zeigen
    if z is not None:
        fehlende_karten(z)
        return
    st.caption("Wie viele Karten eines Sets du hast, verglichen mit allen Karten des Sets im Katalog "
               "(zählt nur die Kartennummer, nicht Sprache oder Variante).")
    sortierung = st.selectbox("Sortieren", ["Neueste Sets zuerst", "Am vollständigsten zuerst", "Meiste fehlende zuerst"], key="sort_voll")
    if sortierung.startswith("Am"):
        voll = voll.sort_values("prozent", ascending=False)
    elif sortierung.startswith("Meiste"):
        voll = voll.assign(fehlt=voll["gesamt"] - voll["besitz"]).sort_values("fehlt", ascending=False)
    voll = voll.reset_index(drop=True)
    st.caption(f"{len(voll)} Sets mit mindestens einer Karte von dir. Mit „Fehlende Karten“ siehst du, was noch fehlt.")

    liste_mit_auswahl(voll, "tcg_id", set_zeile, "voll", knopf="Fehlende Karten", knopf_breite=3)


def fehlende_karten(z):
    st.subheader(f"{z['set_name']}: {int(z['besitz'])} von {int(z['gesamt'])} ({z['prozent']:.0f} %)")
    fehlen = run(FEHLEN_SQL, (z["tcg_id"],))
    if fehlen.empty:
        st.success("Dieses Set ist vollständig. 🎉")
        return
    fehlen["bild"] = [bild_url("de" if pd.isna(f.name_en) else "en", z["serie_id"], z["tcg_id"], f.nr, "low") for f in fehlen.itertuples()]
    fehlen["cm"] = [cm_link_oder_suche(f.cm_id, f.name if pd.isna(f.name_en) else f.name_en, f.nr) for f in fehlen.itertuples()]
    st.caption(f"{len(fehlen)} Karten fehlen. Der Link führt zur Karte auf Cardmarket (wenn die Nummer unbekannt ist, zur Suche).")
    einfache_liste(fehlen, fehlt_zeile, "fehlen")
