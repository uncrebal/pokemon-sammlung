"""Die globale Suche oben: Treffer in Karten, Produkten und im Katalog, mit Sprung zur passenden Ansicht."""
import streamlit as st

from bausteine import euro, knopf_zeile, mit_punkt
from bilder import vorschau
from db import karten_der_sammlung, norm_nr, produkte_der_sammlung
from design import zeile
from katalog import im_katalog_suchen, katalog_bild

ANZAHL = 5      # so viele Treffer je Bereich, der Rest über „Alle … ansehen“


def _springen(ansicht, **werte):
    """Wechselt die Ansicht, setzt Suchfelder/Auswahl und schließt die Trefferliste."""
    st.session_state.update(ansicht=ansicht, global_suche="", **werte)
    for schluessel in ["f_set", "f_rar", "f_spr", "filter_typen"] + [k for k, w in werte.items() if w is None]:
        st.session_state.pop(schluessel, None)


def _schliessen():
    st.session_state["global_suche"] = ""


def treffer_zeigen(platz):
    """Zeigt die Treffer im Bereich platz (über der gewählten Ansicht), sobald mindestens zwei Buchstaben eingegeben sind."""
    begriff = (st.session_state.get("global_suche") or "").strip()
    if len(begriff) < 2:
        return
    karten = karten_der_sammlung(begriff)
    produkte = produkte_der_sammlung()
    produkte = produkte[produkte["name"].str.contains(begriff, case=False, regex=False)]
    meine = karten_der_sammlung()         # Katalogkarten, die du schon hast (gleiches Set, gleiche Nummer), nicht zeigen
    katalog = im_katalog_suchen(begriff, set(zip(meine["set_id"], meine["nummer"].map(norm_nr))), ANZAHL + 1)

    with platz, st.container(key="liste_suche", border=True):
        kopf, zu = st.columns([10, 1], vertical_alignment="center")
        kopf.markdown(f"**Treffer für „{begriff}“**")
        zu.button("✕", key="gs_zu", on_click=_schliessen, help="Trefferliste schließen", width="stretch")
        if karten.empty and produkte.empty and katalog.empty:
            st.caption("Nichts gefunden. Versuche weniger Buchstaben oder den englischen Namen.")

        if len(karten):
            st.caption(f"In deiner Sammlung: {len(karten)} Karten")
            for z in karten.iloc[:ANZAHL].itertuples():
                chips = [(z.sprache, "")] + ([] if z.variante == "Normal" else [(z.variante, "leise")])
                knopf_zeile(zeile(z.name, f"{z.set_name} · {z.nummer}", bild=vorschau(z.bild_pfad), chips=chips, anzahl=z.anzahl,
                                  rechts=euro(z.preis)),
                            "Öffnen", f"gs_k_{z.id}", _springen, ("Karten",), {"sel_karten": int(z.id), "suche_k": z.name})
            if len(karten) > ANZAHL:
                st.button(f"Alle {len(karten)} Karten ansehen", key="gs_k_alle", on_click=_springen, args=("Karten",),
                          kwargs={"suche_k": begriff, "sel_karten": None}, width="stretch")

        if len(produkte):
            st.caption(f"In deiner Sammlung: {len(produkte)} Produkte")
            for z in produkte.iloc[:ANZAHL].itertuples():
                knopf_zeile(zeile(z.name, z.typ, bild=vorschau(z.bild_pfad), chips=[(z.sprache, "")], anzahl=z.anzahl, rechts=euro(z.preis)),
                            "Öffnen", f"gs_p_{z.produkt_id}", _springen, ("Produkte",),
                            {"sel_produkte": int(z.produkt_id), "suche_p": z.name})
            if len(produkte) > ANZAHL:
                st.button(f"Alle {len(produkte)} Produkte ansehen", key="gs_p_alle", on_click=_springen, args=("Produkte",),
                          kwargs={"suche_p": begriff, "sel_produkte": None}, width="stretch")

        if len(katalog):
            st.caption("Im Katalog, noch nicht in deiner Sammlung")
            for z in katalog.iloc[:ANZAHL].itertuples():
                knopf_zeile(zeile(z.name, f"{z.set_name} · Nr. {z.nr}{mit_punkt(z.seltenheit)}", bild=katalog_bild(z._asdict(), "low"),
                                  chips=[("fehlt", "leise")]),
                            "Hinzufügen", f"gs_c_{z.kid}", _springen, ("Hinzufügen",),
                            {"hinzufuegen_art": "Eine Karte", "kat_name": z.name, "kat_set": z.tcg_set, "kat_nr": z.nr, "kat_link": "", "sel_katalog": z.kid})
            if len(katalog) > ANZAHL:
                st.button("Mehr im Katalog suchen", key="gs_c_alle", on_click=_springen, args=("Hinzufügen",),
                          kwargs={"hinzufuegen_art": "Eine Karte", "kat_name": begriff, "kat_set": None, "kat_nr": "", "kat_link": "", "sel_katalog": None}, width="stretch")
