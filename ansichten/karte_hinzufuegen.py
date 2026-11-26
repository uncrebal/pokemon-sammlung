"""Reiter „Hinzufügen“ → „Eine Karte“: Karte per Link oder Suche im Katalog finden und eintragen, oder von Hand anlegen."""
import pandas as pd
import psycopg2.errors
import streamlit as st

from bausteine import SPRACHEN, VARIANTEN, ZUSTAENDE, leer_zu_none, liste_mit_auswahl, mit_punkt
from bilder import beste_url, bild_url, save_image, show_image
from db import run, run_katalog, transaktion
from design import zeile
from katalog import add_karte_katalog, in_sammlung, katalog_bild, link_zu_karte, suchen, variante_vorschlag, vorwaermen


def treffer_zeile(r):
    nummer = r.nr + ("" if pd.isna(r.anzahl) else f"/{int(r.anzahl)}")
    return zeile(r.name, f"{r.set_name} · Nr. {nummer}{mit_punkt(r.seltenheit)}", bild=katalog_bild(r._asdict(), "low"))


def formular(k, prefix="s"):
    """Katalogkarte mit Bild und Formular zum Hinzufügen."""
    links, rechts = st.columns([1, 2])
    with links:
        show_image(beste_url(bild_url("de", k["serie_id"], k["tcg_set"], k["nr"]) if k["hat_de"] else None,
                             bild_url("en", k["serie_id"], k["tcg_set"], k["nr"]) if isinstance(k["name_en"], str) else None))
    with rechts:
        englisch = f" ({k['name_en']})" if k["hat_de"] and isinstance(k["name_en"], str) and k["name_en"] != k["name"] else ""
        st.markdown(f"**{k['name']}**{englisch}")
        st.caption(f"{k['set_name']} · Nr. {k['nr']}" + ("" if pd.isna(k["anzahl"]) else f"/{int(k['anzahl'])}")
                   + mit_punkt(k["seltenheit"]))
        if pd.isna(k["cm_id"]):
            st.caption("Keine Cardmarket-Zuordnung bekannt: kein automatischer Preis.")
        elif k["cm_unsicher"]:
            st.caption("Cardmarket-Zuordnung ist nicht ganz sicher (wird mit „prüfen“ markiert).")
        with st.form(f"form_katalog_{prefix}"):
            f1, f2, f3, f4 = st.columns(4)
            sprache = f1.selectbox("Sprache", SPRACHEN, key=f"kat_sprache_{prefix}")
            variante = f2.selectbox("Variante", VARIANTEN, index=VARIANTEN.index(variante_vorschlag(k)),
                                    key=f"kat_variante_{prefix}_{k['kid']}")
            zustand = f3.selectbox("Zustand", ZUSTAENDE, key=f"kat_zustand_{prefix}")
            anzahl = f4.number_input("Anzahl", min_value=1, value=1, step=1, key=f"kat_anzahl_{prefix}")
            notiz = st.text_input("Notiz (optional)", key=f"kat_notiz_{prefix}")
            senden = st.form_submit_button("Zur Sammlung hinzufügen")
    if senden:
        try:
            preis_ok = add_karte_katalog(k, {"sprache": sprache, "variante": variante, "zustand": zustand,
                                             "anzahl": int(anzahl), "notiz": leer_zu_none(notiz)})
            st.success(f"„{k['name']}“ ({k['set_name']}) wurde hinzugefügt."
                       + (" Der aktuelle Preis ist eingetragen." if preis_ok else
                          " Der Preis erscheint bei der nächsten Preisaktualisierung." if not pd.isna(k["cm_id"]) else ""))
        except Exception as fehler:
            st.error("Das Hinzufügen hat nicht geklappt.")
            st.code(str(fehler))


def zeigen():
    vorwaermen()
    st.subheader("Karte suchen")
    st.caption("Link einer Karte einfügen oder den Namen eintippen (deutsch oder englisch).")
    link = st.text_input("Link einfügen (Cardmarket oder TCGdex)", key="kat_link",
                         placeholder="https://www.cardmarket.com/de/Pokemon/Products/Singles/…")
    if link.strip():
        gefunden, hinweis = link_zu_karte(link.strip())
        if gefunden is None:
            st.warning(hinweis)
        else:
            i = 0
            if len(gefunden) > 1:
                i = st.selectbox("Mehrere Karten passen. Welche ist es?", range(len(gefunden)), key="kat_link_wahl",
                                 format_func=lambda j: f"{gefunden.iloc[j]['name']} · {gefunden.iloc[j]['set_name']} · {gefunden.iloc[j]['nr']}")
            formular(gefunden.iloc[i], "link")
        st.divider()
        st.caption("Oder suche nach dem Namen:")

    katsets = run_katalog("SELECT tcg_id, COALESCE(name_de, name_en, tcg_id) AS name FROM katalog_sets ORDER BY erscheinung DESC NULLS LAST")
    set_namen = dict(zip(katsets["tcg_id"], katsets["name"]))
    s1, s2, s3 = st.columns([3, 3, 1])
    name = s1.text_input("Kartenname", key="kat_name", placeholder="z. B. Pikachu oder Glurak ex")
    tcg_set = s2.selectbox("Set (optional)", [None] + list(set_namen), format_func=lambda x: "Alle Sets" if x is None else set_namen[x],
                           key="kat_set")
    nr = s3.text_input("Nr.", key="kat_nr", placeholder="025")
    if name.strip() or tcg_set or nr.strip():
        treffer = suchen(name, tcg_set, nr)
        if treffer.empty:
            st.info("Nichts gefunden. Versuche den englischen Namen oder weniger Buchstaben.")
        else:
            st.caption(f"{len(treffer)} Treffer" + (" (nur die ersten 100, bitte genauer suchen)" if len(treffer) == 100 else "")
                       + ". Mit „Auswählen“ fügst du eine Karte hinzu.")
            k = liste_mit_auswahl(treffer, "kid", treffer_zeile, "katalog", knopf="Auswählen", zurueck="← Zurück zu den Treffern")
            if k is not None:
                formular(k)

    st.divider()
    st.subheader("Von Hand anlegen")
    st.caption("Für Karten, die im Katalog fehlen.")
    von_hand()


def von_hand():
    sets = run("SELECT set_id, name FROM sets ORDER BY erscheinungsdatum DESC NULLS LAST, name")
    rar = run("SELECT raritaet_id, name FROM raritaeten ORDER BY raritaet_id")
    set_namen = dict(zip(sets["set_id"], sets["name"]))
    rar_namen = {int(a): b for a, b in zip(rar["raritaet_id"], rar["name"])}
    with st.form("form_karte", clear_on_submit=True):
        c1, c2 = st.columns(2)
        set_id = c1.selectbox("Set", list(set_namen), format_func=set_namen.get)
        name = c1.text_input("Kartenname *")
        nummer = c1.text_input("Kartennummer * (z. B. 125/197)")
        api_id = c1.text_input("API-ID (optional, z. B. sv3-125)")
        raritaet_id = c2.selectbox("Rarität", [None] + list(rar_namen), format_func=lambda x: "–" if x is None else rar_namen[x])
        sprache = c2.selectbox("Sprache", SPRACHEN)
        variante = c2.selectbox("Variante", VARIANTEN)
        zustand = c2.selectbox("Zustand", ZUSTAENDE)
        anzahl = c2.number_input("Anzahl", min_value=1, value=1, step=1)
        notiz = c2.text_input("Notiz (optional)")
        bild = c2.file_uploader("Bild (optional)", type=["png", "jpg", "jpeg", "webp"])
        gesendet = st.form_submit_button("Hinzufügen")
    if not gesendet:
        return
    if not name.strip() or not nummer.strip():
        st.error("Kartenname und Kartennummer sind Pflicht.")
        return
    bild_pfad = save_image(bild, "karten")
    try:
        with transaktion() as cur:   # Karte suchen oder anlegen, dann in die Sammlung
            cur.execute("SELECT karten_id FROM karten WHERE set_id = %s AND nummer = %s AND name = %s", (set_id, nummer.strip(), name.strip()))
            gefunden = cur.fetchone()
            if gefunden:
                karten_id = gefunden[0]
                if bild_pfad:
                    cur.execute("UPDATE karten SET bild_pfad = %s WHERE karten_id = %s", (bild_pfad, karten_id))
            else:
                cur.execute("""INSERT INTO karten (api_id, name, nummer, set_id, raritaet_id, bild_pfad) VALUES (%s, %s, %s, %s, %s, %s)
                               RETURNING karten_id""", (leer_zu_none(api_id), name.strip(), nummer.strip(), set_id, raritaet_id, bild_pfad))
                karten_id = cur.fetchone()[0]
            in_sammlung(cur, karten_id, {"anzahl": int(anzahl), "sprache": sprache, "zustand": zustand, "variante": variante,
                                         "notiz": leer_zu_none(notiz)})
        st.success(f"„{name.strip()}“ wurde zur Sammlung hinzugefügt.")
    except psycopg2.errors.UniqueViolation:
        st.error("Diese API-ID gehört schon zu einer anderen Karte.")
