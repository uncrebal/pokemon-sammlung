"""Ansicht „Übersicht“ (Startseite): Gesamtwert, Gewinn bei Produkten, Wertverlauf, wertvollste Karten, Excel-Export.
Beim Öffnen sind alle Euro-Beträge ausgeblendet (Augen-Knopf)."""
import io
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from bausteine import euro, einfache_liste
from bilder import vorschau
from db import karten_der_sammlung, produkte_der_sammlung, run
from design import zeile

VERDECKT = "•••••"

# Die heutige Sammlung, bewertet mit den Preisen jedes gespeicherten Tages (eigene Preise zählen an allen Tagen gleich)
VERLAUF_SQL = """
WITH tage AS (SELECT DISTINCT datum FROM preis_karten UNION SELECT DISTINCT datum FROM preis_produkte)
SELECT t.datum,
  COALESCE((SELECT SUM(sk.anzahl * COALESCE(k.preis_manuell, CASE WHEN sk.variante LIKE '%%Reverse%%'
                                                    THEN COALESCE(p.preis_reverse, p.preis_cm) ELSE p.preis_cm END))
            FROM sammlung_karten sk JOIN karten k ON k.karten_id = sk.karten_id
            LEFT JOIN preis_karten p ON p.karten_id = k.karten_id AND p.datum = t.datum), 0) AS "Karten",
  COALESCE((SELECT SUM(sp.anzahl * COALESCE(pr.preis_manuell, pp.preis_cm))
            FROM sammlung_produkte sp JOIN produkte pr ON pr.produkt_id = sp.produkt_id
            LEFT JOIN preis_produkte pp ON pp.produkt_id = pr.produkt_id AND pp.datum = t.datum), 0) AS "Produkte"
FROM tage t ORDER BY t.datum"""


def _umschalten():
    st.session_state["werte_sichtbar"] = not st.session_state.get("werte_sichtbar", False)


def top_zeile(r):
    return zeile(r.name, f"{r.set_name} · {r.sprache} · {r.variante} · {euro(r.preis)} × {int(r.anzahl)}",
                 bild=vorschau(r.bild_pfad), rechts=euro(r.wert))


def zeigen():
    zeigen_ = st.session_state.get("werte_sichtbar", False)      # beim Öffnen der App immer ausgeblendet
    dk, dp = karten_der_sammlung(), produkte_der_sammlung()
    st.button("🙈 Werte ausblenden" if zeigen_ else "👁 Werte anzeigen", on_click=_umschalten, key="werte_knopf",
              help="Blendet alle Euro-Beträge auf dieser Seite aus oder ein. Beim Neuladen der App sind sie wieder ausgeblendet.")

    def betrag(x):
        return euro(x) if zeigen_ else VERDECKT

    wert_k, wert_p = float(dk["wert"].sum()), float(dp["wert"].sum())
    m1, m2, m3 = st.columns(3)
    m1.metric("Gesamtwert", betrag(wert_k + wert_p))
    m2.metric(f"Karten ({int(dk['anzahl'].sum())})", betrag(wert_k))
    m3.metric(f"Produkte ({int(dp['anzahl'].sum())})", betrag(wert_p))
    gewinn(dp, zeigen_)
    ohne = int(dk["preis"].isna().sum() + dp["preis"].isna().sum())
    if ohne:
        st.caption(f"{ohne} Einträge haben noch keinen Preis und zählen nicht mit.")
    if not zeigen_:
        st.caption("Die Werte sind ausgeblendet: Summen, Verlauf, wertvollste Karten und Wert pro Set. "
                   "Mit „👁 Werte anzeigen“ oben blendest du sie ein.")
        return

    st.subheader("Wertverlauf")
    wertverlauf()
    st.subheader("Die 10 wertvollsten Einträge (Preis × Anzahl)")
    einfache_liste(dk.dropna(subset=["wert"]).nlargest(10, "wert"), top_zeile, "top")
    st.subheader("Wert nach Set (Top 10)")
    nach_set = dk.groupby("set_name")["wert"].sum().nlargest(10)
    if len(nach_set):
        st.bar_chart(nach_set)
    excel_export(dk, dp)


def gewinn(dp, zeigen_):
    """Gewinn/Verlust bei Produkten. Einkaufspreis: dein Kaufpreis, sonst die UVP der Produktart (Schätzung)."""
    dp = dp.assign(ek=dp["kaufpreis"].fillna(dp["uvp"]))
    mit_ek = dp[dp["ek"].notna() & dp["preis"].notna()]
    if mit_ek.empty:
        st.caption("Für den Gewinn bei Produkten fehlen Einkaufspreise: Trage im Bereich Produkte die UVP je Produktart ein.")
        return
    eingekauft, jetzt = float((mit_ek["ek"] * mit_ek["anzahl"]).sum()), float(mit_ek["wert"].sum())
    st.metric(f"Produkte: Gewinn / Verlust ({len(mit_ek)} von {len(dp)} Produkten gerechnet)",
              euro(jetzt - eingekauft) if zeigen_ else VERDECKT,
              delta=f"{(jetzt / eingekauft - 1) * 100:+.1f} % gegenüber {euro(eingekauft)} Einkauf" if (eingekauft and zeigen_) else None)
    if zeigen_:
        n_kauf = int(mit_ek["kaufpreis"].notna().sum())
        st.caption(f"Einkaufspreis: bei {n_kauf} Produkten dein Kaufpreis, bei {len(mit_ek) - n_kauf} die UVP der Produktart "
                   "als Schätzung. Die UVP stellst du im Bereich Produkte ein.")


def wertverlauf():
    verlauf = run(VERLAUF_SQL)
    if len(verlauf) < 2:
        st.info("Der Verlauf entsteht mit der Zeit: Pro Tag mit Preisaktualisierung kommt ein Punkt dazu.")
        return
    zeitraum = st.radio("Ein Wert pro", ["Tag", "Woche", "Monat"], horizontal=True, key="verlauf_zeitraum")
    werte = verlauf.assign(datum=pd.to_datetime(verlauf["datum"])).set_index("datum").astype(float)
    werte["Gesamt"] = werte["Karten"] + werte["Produkte"]
    werte = werte[["Gesamt", "Karten", "Produkte"]]
    if zeitraum == "Tag":
        beschriftung = [d.strftime("%d.%m.%y") for d in werte.index]
    else:   # letzter gespeicherter Stand der Woche bzw. des Monats
        werte = werte.groupby(werte.index.to_period("W" if zeitraum == "Woche" else "M")).last()
        beschriftung = [f"KW {p.start_time.isocalendar()[1]:02d}/{p.start_time:%y}" if zeitraum == "Woche" else f"{p:%m/%Y}"
                        for p in werte.index]
    lang = werte.assign(Zeitpunkt=beschriftung).melt(id_vars="Zeitpunkt", var_name="Linie", value_name="Wert")
    st.altair_chart(alt.Chart(lang).mark_line(point=True).encode(
        x=alt.X("Zeitpunkt:O", sort=None, title=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("Wert:Q", title="Wert in €", scale=alt.Scale(zero=False)),
        color=alt.Color("Linie:N", title=None, sort=["Gesamt", "Karten", "Produkte"]),
        tooltip=["Zeitpunkt", "Linie", alt.Tooltip("Wert:Q", format=",.2f", title="Wert (€)")],
    ).properties(height=320), width="stretch")
    st.caption("Die heutige Sammlung, bewertet mit den Preisen des jeweiligen Tages. Bei Woche und Monat zählt der letzte "
               "gespeicherte Stand. Eigene Preise zählen an allen Tagen gleich.")


def excel_export(dk, dp):
    with st.expander("Export als Excel"):
        st.caption("Alle Karten und Produkte mit Preisen als Tabelle, zum Beispiel für die Versicherung.")
        if st.button("Excel-Datei vorbereiten", key="excel_vorbereiten"):
            st.session_state["excel_daten"] = excel_datei(dk, dp)
            st.session_state["excel_stand"] = date.today().isoformat()
        if "excel_daten" in st.session_state:
            stand = st.session_state["excel_stand"]
            st.download_button(f"Excel herunterladen (Stand {stand})", st.session_state["excel_daten"],
                               file_name=f"pokemon_sammlung_{stand}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def excel_datei(dk, dp):
    """Sammlung als Excel-Datei mit den Blättern Karten und Produkte."""
    karten = dk.rename(columns={"name": "Name", "nummer": "Nummer", "set_name": "Set", "raritaet": "Rarität", "sprache": "Sprache",
                                "variante": "Variante", "zustand": "Zustand", "anzahl": "Anzahl", "notiz": "Notiz",
                                "preis": "Preis (€)", "wert": "Wert (€)", "preis_zuordnung": "Preis-Zuordnung"})
    produkte = dp.assign(einkauf=dp["kaufpreis"].fillna(dp["uvp"])).rename(columns={
        "name": "Name", "typ": "Art", "sprache": "Sprache", "anzahl": "Anzahl", "kaufpreis": "Kaufpreis (€)", "uvp": "UVP der Art (€)",
        "einkauf": "Einkauf, Kaufpreis sonst UVP (€)", "preis": "Preis (€)", "wert": "Wert (€)", "preis_zuordnung": "Preis-Zuordnung"})
    puffer = io.BytesIO()
    with pd.ExcelWriter(puffer, engine="openpyxl") as w:
        karten[["Name", "Nummer", "Set", "Rarität", "Sprache", "Variante", "Zustand", "Anzahl", "Notiz", "Preis (€)", "Wert (€)",
                "Preis-Zuordnung"]].to_excel(w, sheet_name="Karten", index=False)
        produkte[["Name", "Art", "Sprache", "Anzahl", "Kaufpreis (€)", "UVP der Art (€)", "Einkauf, Kaufpreis sonst UVP (€)",
                  "Preis (€)", "Wert (€)", "Preis-Zuordnung"]].to_excel(w, sheet_name="Produkte", index=False)
        for blatt in w.book.worksheets:
            for spalte in blatt.columns:
                breite = max(len(str(z.value)) if z.value is not None else 0 for z in spalte)
                blatt.column_dimensions[spalte[0].column_letter].width = min(max(breite + 2, 8), 45)
            blatt.freeze_panes = "A2"
    return puffer.getvalue()
