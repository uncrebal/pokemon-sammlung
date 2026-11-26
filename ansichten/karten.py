"""Ansicht „Karten“: die Sammlung als Liste, Details, Bearbeiten und Löschen."""
import pandas as pd
import psycopg2.errors
import streamlit as st

from bausteine import EURO, SPRACHEN, VARIANTEN, ZUSTAENDE, cm_link, euro, gewaehlte_zeile, handy, leer_zu_none, liste_mit_auswahl
from bilder import beste_url, fehlende_bilder_bereich, show_image, vorschau
from db import karten_der_sammlung, neu_laden, run, transaktion
from design import fakten_tabelle, zeile

SORTIERUNGEN = {   # Anzeige -> (Spalte, aufsteigend)
    "Neueste Sets zuerst": None,
    "Name A–Z": ("name", True),
    "Preis: teuerste zuerst": ("preis", False),
    "Wert (Preis × Anzahl): höchster zuerst": ("wert", False),
    "Preis: günstigste zuerst": ("preis", True),
}
TABELLE = (["name", "nummer", "set_name", "raritaet", "sprache", "variante", "zustand", "anzahl", "notiz", "preis", "wert", "preis_zuordnung"],
           {"name": "Name", "nummer": "Nummer", "set_name": "Set", "raritaet": "Rarität", "sprache": "Sprache", "variante": "Variante",
            "zustand": "Zustand", "anzahl": "Anzahl", "notiz": "Notiz", "preis": EURO, "wert": EURO, "preis_zuordnung": "Preis-Zuordnung"})


def karten_zeile(r):
    chips = [(r.sprache, "")] + ([] if r.variante == "Normal" else [(r.variante, "leise")])
    return zeile(r.name, f"{r.set_name} · {r.nummer}", bild=vorschau(r.bild_pfad), chips=chips, anzahl=r.anzahl, rechts=euro(r.preis))


def zeigen():
    z = gewaehlte_zeile(karten_der_sammlung(), "id", "karten")      # eine Karte ist geöffnet: nur die Details zeigen
    if z is not None:
        details(z)
        return
    df = karten_der_sammlung(st.text_input("Suche nach Kartenname", key="suche_k"))
    if len(df):
        with st.expander("Filter und Sortierung"):
            f1, f2, f3 = st.columns(3)
            filter_ = {"set_name": f1.multiselect("Set", sorted(df["set_name"].dropna().unique()), key="f_set"),
                       "raritaet": f2.multiselect("Rarität", sorted(df["raritaet"].dropna().unique()), key="f_rar"),
                       "sprache": f3.multiselect("Sprache", sorted(df["sprache"].dropna().unique()), key="f_spr")}
            sortierung = SORTIERUNGEN[st.selectbox("Sortieren nach", list(SORTIERUNGEN), key="sort_k")]
        for spalte, wahl in filter_.items():
            if wahl:
                df = df[df[spalte].isin(wahl)]
        if sortierung:
            spalte, aufsteigend = sortierung
            df = df.sort_values(spalte, ascending=aufsteigend, na_position="last",
                                key=(lambda s: s.str.lower()) if spalte == "name" else None)
        df = df.reset_index(drop=True)
    st.caption(f"{len(df)} Einträge, {int(df['anzahl'].sum())} Karten insgesamt, Wert ca. {euro(df['wert'].sum()) or '0,00 €'}")
    if not handy():
        fehlende_bilder_bereich()
    z = liste_mit_auswahl(df, "id", karten_zeile, "karten", tabelle=TABELLE)
    if z is not None:
        details(z)


def details(z):
    sk_id = int(z["id"])
    links, rechts = st.columns([1, 2])
    with links:
        show_image(beste_url(z["bild_de"], z["bild_pfad"]))
    with rechts:
        st.subheader(f'{z["name"]} ({z["nummer"]})')
        fakten_tabelle([("Set", z["set_name"]), ("Nummer", z["nummer"]), ("Rarität", z["raritaet"]), ("Sprache", z["sprache"]),
                        ("Variante", z["variante"]), ("Zustand", z["zustand"]), ("Anzahl", int(z["anzahl"])),
                        ("Preis pro Karte", euro(z["preis"])), ("Wert (Preis × Anzahl)", euro(z["wert"])),
                        ("Preisquelle", z["preis_zuordnung"] or "Cardmarket"), ("Notiz", z["notiz"])])
        if cm_link(z["cm_id"]):
            st.link_button("Auf Cardmarket ansehen", cm_link(z["cm_id"]))
        neue_anzahl = st.number_input("Anzahl", min_value=1, value=int(z["anzahl"]), step=1, key=f"anz_k_{sk_id}")
        if st.button("Anzahl speichern", key=f"save_k_{sk_id}"):
            run("UPDATE sammlung_karten SET anzahl = %s WHERE id = %s", (int(neue_anzahl), sk_id))
            neu_laden()
        with st.expander("Eintrag bearbeiten (Name, Nummer, Set, Rarität, Sprache, Zustand, Variante, Notiz, Preis)"):
            bearbeiten(z)
        sicher = st.checkbox("Ja, diesen Eintrag wirklich löschen", key=f"sure_k_{sk_id}")
        if st.button("Aus Sammlung löschen", disabled=not sicher, key=f"del_k_{sk_id}"):
            run("DELETE FROM sammlung_karten WHERE id = %s", (sk_id,))
            neu_laden()


def _index(liste, wert):
    return liste.index(wert) if wert in liste else 0


def bearbeiten(z):
    sets = run("SELECT set_id, name FROM sets ORDER BY erscheinungsdatum DESC NULLS LAST, name")
    rar = run("SELECT raritaet_id, name FROM raritaeten ORDER BY raritaet_id")
    set_namen = dict(zip(sets["set_id"], sets["name"]))
    rar_namen = {int(a): b for a, b in zip(rar["raritaet_id"], rar["name"])}
    rar_ids = [None] + list(rar_namen)
    varianten = VARIANTEN if z["variante"] in VARIANTEN else VARIANTEN + [z["variante"]]
    with st.form(f"form_edit_k_{int(z['id'])}"):
        st.caption("Name, Nummer, Set und Rarität gehören zur Karte selbst und ändern sich bei allen Einträgen dieser Karte.")
        f1, f2 = st.columns(2)
        name = f1.text_input("Name", value=z["name"])
        nummer = f1.text_input("Nummer", value=str(z["nummer"] or ""))
        set_id = f2.selectbox("Set", list(set_namen), format_func=set_namen.get, index=_index(list(set_namen), z["set_id"]))
        raritaet = f2.selectbox("Rarität", rar_ids, format_func=lambda x: "–" if x is None else rar_namen[x],
                                index=_index(rar_ids, None if pd.isna(z["raritaet_id"]) else int(z["raritaet_id"])))
        e1, e2 = st.columns(2)
        sprache = e1.selectbox("Sprache", SPRACHEN, index=_index(SPRACHEN, z["sprache"]))
        zustand = e1.selectbox("Zustand", ZUSTAENDE, index=_index(ZUSTAENDE, z["zustand"]))
        variante = e1.selectbox("Variante", varianten, index=varianten.index(z["variante"]))
        notiz = e2.text_input("Notiz", value="" if pd.isna(z["notiz"]) else str(z["notiz"]))
        preis = e2.number_input("Eigener Preis in € (überschreibt den Cardmarket-Preis; leer = Cardmarket-Preis nutzen)",
                                min_value=0.0, step=0.5, value=None if pd.isna(z["handpreis"]) else float(z["handpreis"]))
        e2.caption("Der Preis gilt für diese Karte in allen Sprachen/Varianten.")
        ok = st.form_submit_button("Änderungen speichern")
    if not ok:
        return
    if not name.strip() or not nummer.strip():
        st.error("Name und Nummer dürfen nicht leer sein.")
        return
    try:
        with transaktion() as cur:
            cur.execute("UPDATE karten SET name = %s, nummer = %s, set_id = %s, raritaet_id = %s, preis_manuell = %s WHERE karten_id = %s",
                        (name.strip(), nummer.strip(), set_id, raritaet, preis, int(z["karten_id"])))
            cur.execute("UPDATE sammlung_karten SET sprache = %s, zustand = %s, variante = %s, notiz = %s WHERE id = %s",
                        (sprache, zustand, variante, leer_zu_none(notiz), int(z["id"])))
        neu_laden()
    except psycopg2.errors.UniqueViolation:
        st.error("Das geht nicht, weil es diese Karte (Set/Nummer/Name) oder diese Kombination aus Sprache, Zustand und Variante "
                 "schon gibt. Ändere dort die Anzahl oder lösche den anderen Eintrag.")
