"""Ansicht „Produkte“: Sealed-Produkte als Liste, Details, Bearbeiten, UVP je Art.
Neue Produkte (hinzufuegen: Suche im Cardmarket-Produktkatalog oder von Hand) werden im Reiter „Hinzufügen“ gezeigt."""
import pandas as pd
import streamlit as st

import katalog
import produktkatalog
from bausteine import EURO, SPRACHEN, cm_link, euro, gewaehlte_zeile, knopf_zeile, liste_mit_auswahl
from bilder import save_image, show_image, vorschau
from db import neu_laden, produkte_der_sammlung, run, transaktion
from design import fakten_tabelle, zeile

TABELLE = (["name", "typ", "sprache", "anzahl", "kaufpreis", "preis", "wert", "preis_zuordnung"],
           {"name": "Name", "typ": "Art", "sprache": "Sprache", "anzahl": "Anzahl", "kaufpreis": EURO, "preis": EURO, "wert": EURO,
            "preis_zuordnung": "Preis-Zuordnung"})


def produkt_zeile(r):
    return zeile(r.name, r.typ, bild=vorschau(r.bild_pfad), chips=[(r.sprache, "")], anzahl=r.anzahl, rechts=euro(r.preis))


def zeigen():
    z = gewaehlte_zeile(produkte_der_sammlung(), "produkt_id", "produkte")    # ein Produkt ist geöffnet: nur die Details
    if z is not None:
        details(z)
        return
    if st.session_state.get("p_zuordnung"):     # das Werkzeug „Cardmarket-Zuordnung“ ist offen
        zuordnung()
        return
    typen = run("""SELECT t.typ_id, t.name, COALESCE(SUM(sp.anzahl), 0) AS stueck FROM produkt_typen t
                   LEFT JOIN produkte p ON p.typ_id = t.typ_id LEFT JOIN sammlung_produkte sp ON sp.produkt_id = p.produkt_id
                   GROUP BY t.typ_id, t.name ORDER BY t.typ_id""")
    typ_namen = {int(a): b for a, b in zip(typen["typ_id"], typen["name"])}
    suche = st.text_input("Suche nach Produktname", key="suche_p")
    filter_typen = st.pills("Art des Produkts (nichts ausgewählt = alle)", options=list(typ_namen), selection_mode="multi",
                            format_func=lambda t: f"{typ_namen[t]} ({int(typen.set_index('typ_id').loc[t, 'stueck'])})", key="filter_typen")
    df = produkte_der_sammlung()
    df = df[df["name"].str.contains(suche.strip(), case=False, regex=False)]
    if filter_typen:
        df = df[df["typ_id"].isin(filter_typen)]
    df = df.reset_index(drop=True)
    st.caption(f"{len(df)} Produkte, {int(df['anzahl'].sum())} Stück insgesamt, Wert ca. {euro(df['wert'].sum()) or '0,00 €'}")
    z = liste_mit_auswahl(df, "produkt_id", produkt_zeile, "produkte", tabelle=TABELLE)
    if z is not None:
        details(z)
    uvp_bereich()
    st.button("➕ Neues Produkt hinzufügen", key="zu_hinzufuegen_p", on_click=st.session_state.update,
              kwargs={"ansicht": "Hinzufügen", "hinzufuegen_art": "Produkt"})
    ohne = int(produkte_der_sammlung()["cm_id"].isna().sum())
    if ohne:
        st.button(f"🔗 Cardmarket-Zuordnung: {ohne} {'Produkt' if ohne == 1 else 'Produkte'} ohne Nummer", key="zu_zuordnung", on_click=st.session_state.update,
                  kwargs={"p_zuordnung": True}, help="Ordnet deinen Produkten das passende Cardmarket-Produkt zu, damit sie automatisch einen Preis bekommen.")


def details(z):
    pid = int(z["produkt_id"])
    links, rechts = st.columns([1, 2])
    with links:
        show_image(z["bild_pfad"])
    with rechts:
        st.subheader(z["name"])
        fakten_tabelle([("Art", z["typ"]), ("Sprache", z["sprache"]), ("Anzahl", int(z["anzahl"])),
                        ("Kaufpreis pro Stück", euro(z["kaufpreis"])), ("Preis pro Stück", euro(z["preis"])),
                        ("Wert (Preis × Anzahl)", euro(z["wert"])), ("Preisquelle", z["preis_zuordnung"] or "Cardmarket")])
        if cm_link(z["cm_id"]):
            st.link_button("Auf Cardmarket ansehen", cm_link(z["cm_id"]))
        neue_anzahl = st.number_input("Anzahl", min_value=1, value=int(z["anzahl"]), step=1, key=f"anz_p_{pid}")
        if st.button("Anzahl speichern", key=f"save_p_{pid}"):
            run("UPDATE sammlung_produkte SET anzahl = %s WHERE produkt_id = %s", (int(neue_anzahl), pid))
            neu_laden()
        with st.expander("Produkt bearbeiten (Kaufpreis, Preis)"):
            with st.form(f"form_edit_p_{pid}"):
                kauf = st.number_input("Kaufpreis pro Stück in €", min_value=0.0, step=0.5,
                                       value=None if pd.isna(z["kaufpreis"]) else float(z["kaufpreis"]))
                preis = st.number_input("Eigener Preis in € (überschreibt den Cardmarket-Preis; leer = Cardmarket-Preis nutzen)",
                                        min_value=0.0, step=0.5, value=None if pd.isna(z["handpreis"]) else float(z["handpreis"]))
                if st.form_submit_button("Änderungen speichern"):
                    with transaktion() as cur:
                        cur.execute("UPDATE sammlung_produkte SET kaufpreis = %s WHERE produkt_id = %s", (kauf, pid))
                        cur.execute("UPDATE produkte SET preis_manuell = %s WHERE produkt_id = %s", (preis, pid))
                    neu_laden()
        sicher = st.checkbox("Ja, dieses Produkt wirklich löschen", key=f"sure_p_{pid}")
        if st.button("Aus Sammlung löschen", disabled=not sicher, key=f"del_p_{pid}"):
            run("DELETE FROM sammlung_produkte WHERE produkt_id = %s", (pid,))
            neu_laden()


def uvp_bereich():
    with st.expander("UVP je Produktart (Einkaufspreis-Schätzung für den Gewinn)"):
        st.caption("Für Produkte ohne eigenen Kaufpreis rechnet die Übersicht mit dieser UVP als Einkaufspreis. Trage pro Art den "
                   "üblichen Ladenpreis ein, zu dem du die meisten Produkte gekauft hast. Leer = nicht gerechnet. Einen eigenen "
                   "Kaufpreis kannst du bei jedem Produkt unter „Produkt bearbeiten“ eintragen, er hat Vorrang.")
        uvp = run("""SELECT t.typ_id, t.name AS art, (SELECT COUNT(*) FROM produkte p WHERE p.typ_id = t.typ_id) AS produkte, t.uvp
                     FROM produkt_typen t ORDER BY t.typ_id""")
        uvp["uvp"] = pd.to_numeric(uvp["uvp"])
        neu = st.data_editor(uvp[["art", "produkte", "uvp"]], hide_index=True, width="stretch", disabled=["art", "produkte"],
                             column_config={"art": "Art", "produkte": "Anzahl Produkte",
                                            "uvp": st.column_config.NumberColumn("UVP in €", min_value=0.0, step=0.5, format="%.2f")},
                             key=f"uvp_editor_{st.session_state.get('v', 0)}")
        if st.button("UVP speichern", key="uvp_speichern"):
            with transaktion() as cur:
                for typ_id, wert in zip(uvp["typ_id"], neu["uvp"]):
                    cur.execute("UPDATE produkt_typen SET uvp = %s WHERE typ_id = %s", (None if pd.isna(wert) else float(wert), int(typ_id)))
            neu_laden()


def zuordnung_zeile(r):
    chips = [(r.sprache, "")] + ([("Handpreis", "leise")] if not pd.isna(r.handpreis) else [])
    return zeile(r.name, r.typ, bild=vorschau(r.bild_pfad), chips=chips, anzahl=r.anzahl)


def zuordnung():
    """Werkzeug: Produkte ohne Cardmarket-Nummer der Reihe nach einem Cardmarket-Produkt zuordnen."""
    if st.session_state.get("sel_zuordnung") is None and st.button("← Zurück zu den Produkten", key="zuordnung_zurueck"):
        st.session_state.pop("p_zuordnung", None)
        st.rerun()
    st.subheader("Cardmarket-Zuordnung")
    if st.session_state.get("zuordnung_meldung"):
        st.success(st.session_state.pop("zuordnung_meldung"))
    df = produkte_der_sammlung()
    df = df[df["cm_id"].isna()].copy()
    df["hat_hand"] = df["handpreis"].notna()
    df = df.sort_values("hat_hand", kind="stable").reset_index(drop=True)       # Produkte ganz ohne Preis zuerst
    if df.empty:
        st.info("Alle deine Produkte haben eine Cardmarket-Nummer.")
        return
    st.caption(f"Ohne Cardmarket-Nummer: {len(df)}. Mit einer Zuordnung bekommt das Produkt automatisch den täglichen Preis.")
    z = liste_mit_auswahl(df, "produkt_id", zuordnung_zeile, "zuordnung", knopf="Zuordnen", zurueck="← Zurück zur Liste")
    if z is not None:
        zuordnung_treffer(z, df)


def zuordnung_treffer(z, df):
    pid = int(z["produkt_id"])
    st.markdown(f"**{z['name']}** · {z['typ']} · {z['sprache']}")
    if not pd.isna(z["handpreis"]):
        st.caption("Dieses Produkt hat einen Handpreis. Er gilt weiter, bis du ihn unter „Produkt bearbeiten“ leerst.")
    begriff = st.text_input("Suchbegriff (kannst du ändern, auch ein Cardmarket-Link geht)", value=z["name"], key=f"zu_such_{pid}")
    try:
        treffer = produktkatalog.vorschlaege(begriff)
    except Exception as fehler:
        st.warning("Die Produktliste von Cardmarket konnte nicht geladen werden.")
        st.code(str(fehler))
        return
    if treffer.empty:
        st.info("Nichts gefunden. Ändere den Suchbegriff, oder gehe zurück, wenn Cardmarket das Produkt nicht führt.")
        return
    st.caption("Wähle das passende Produkt. Passt keins, ändere den Suchbegriff oder gehe zurück.")
    for t in mit_preis(treffer).itertuples():
        if knopf_zeile(zeile(t.name, t.art, rechts=euro(t.preis)), "Das ist es", f"zu_{pid}_{t.cm_id}"):
            zuordnung_speichern(z, int(t.cm_id), df)


def zuordnung_speichern(z, cm_id, df):
    """Merkt sich die Cardmarket-Nummer, trägt den Preis ein und öffnet gleich das nächste Produkt."""
    pid = int(z["produkt_id"])
    try:
        with transaktion() as cur:
            cur.execute("UPDATE produkte SET cm_id = %s, cm_unsicher = FALSE WHERE produkt_id = %s", (cm_id, pid))
    except Exception as fehler:
        st.error("Das Speichern hat nicht geklappt.")
        st.code(str(fehler))
        return
    preis_ok = preis_eintragen(pid, cm_id)
    st.session_state["zuordnung_meldung"] = f"„{z['name']}“ ist zugeordnet." + (" Der aktuelle Preis ist eingetragen." if preis_ok else
                                                                               " Der Preis erscheint bei der nächsten Preisaktualisierung.")
    rest = df[df["produkt_id"] != pid]
    if rest.empty:
        st.session_state.pop("sel_zuordnung", None)
    else:
        st.session_state["sel_zuordnung"] = int(rest.iloc[0]["produkt_id"])
    neu_laden()


def mit_preis(treffer):
    """Ergänzt Treffer aus dem Produktkatalog um den aktuellen Cardmarket-Trendpreis (Spalte preis, leer wenn unbekannt)."""
    preisliste = katalog._versuche(katalog._preisliste)
    return treffer.assign(preis=[(preisliste[1].get(c) or {}).get("trend") if preisliste else None for c in treffer["cm_id"]])


def katalog_zeile(r):
    chips = [("schon in der Sammlung", "")] if r.in_sammlung else []
    return zeile(r.name, r.art, chips=chips, rechts=euro(r.preis))


def hinzufuegen():
    typen = run("SELECT typ_id, name FROM produkt_typen ORDER BY typ_id")
    typ_namen = {int(a): b for a, b in zip(typen["typ_id"], typen["name"])}
    sets = run("SELECT set_id, name FROM sets ORDER BY erscheinungsdatum DESC NULLS LAST, name")
    set_namen = {None: "–", **dict(zip(sets["set_id"], sets["name"]))}

    st.subheader("Produkt suchen")
    st.caption("Namen eintippen (deutsch oder englisch, z. B. „Stürmische Funken Top-Trainer-Box“) oder einen Cardmarket-Link einfügen. "
               "Gefundene Produkte bekommen automatisch den Cardmarket-Preis.")
    begriff = st.text_input("Produktname oder Cardmarket-Link", key="pk_suche", placeholder="z. B. Glurak Kollektion")
    if len(begriff.strip()) >= 2:
        try:
            treffer = produktkatalog.suchen(begriff)
        except Exception as fehler:
            st.warning("Die Produktliste von Cardmarket konnte nicht geladen werden. Lege das Produkt unten von Hand an.")
            st.code(str(fehler))
            treffer = None
        if treffer is not None and treffer.empty:
            st.info("Nichts gefunden. Versuche weniger Wörter oder den englischen Namen.")
        elif treffer is not None:
            treffer = mit_preis(treffer)
            treffer["in_sammlung"] = treffer["cm_id"].isin(produkte_der_sammlung()["cm_id"].dropna().astype(int))
            st.caption(f"{len(treffer)} Treffer" + (" (nur die ersten 100, bitte genauer suchen)" if len(treffer) == 100 else "")
                       + ". Mit „Auswählen“ fügst du ein Produkt hinzu.")
            p = liste_mit_auswahl(treffer, "cm_id", katalog_zeile, "pkatalog", knopf="Auswählen", zurueck="← Zurück zu den Treffern")
            if p is not None:
                formular("katalog", typ_namen, set_namen, p)

    st.divider()
    st.subheader("Von Hand anlegen")
    st.caption("Für Produkte, die Cardmarket nicht kennt. Sie bekommen keinen automatischen Preis.")
    formular("hand", typ_namen, set_namen)

    with st.expander("Neue Produktart anlegen (z. B. Ultra Premium Kollektion)"):
        with st.form("form_typ", clear_on_submit=True):
            t_name = st.text_input("Name der Art *")
            if st.form_submit_button("Art anlegen"):
                if t_name.strip():
                    run("INSERT INTO produkt_typen (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (t_name.strip(),))
                    st.success(f"Art „{t_name.strip()}“ ist angelegt, sie erscheint beim nächsten Laden in der Auswahl „Typ“.")
                else:
                    st.error("Der Name ist Pflicht.")


def formular(prefix, typ_namen, set_namen, p=None):
    """Formular für ein neues Produkt. p = Treffer aus dem Produktkatalog (füllt Name und Art vor und merkt sich die Cardmarket-Nummer)."""
    cm_id = None if p is None else int(p["cm_id"])
    if p is not None:
        st.markdown(f"**{p['name']}** · {p['art']}" + (f" · aktuell ca. {euro(p['preis'])}" if euro(p["preis"]) else ""))
        if cm_link(cm_id):
            st.link_button("Auf Cardmarket ansehen", cm_link(cm_id))
    typ_index = list(typ_namen).index(produktkatalog.art_vorschlag(p, typ_namen)) if p is not None else 0
    with st.form(f"form_produkt_{prefix}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Produktname *", value="" if p is None else p["name"], key=f"p_name_{prefix}_{cm_id}")
        typ = c1.selectbox("Typ", list(typ_namen), index=typ_index, format_func=typ_namen.get, key=f"p_typ_{prefix}_{cm_id}")
        sprache = c1.selectbox("Sprache", SPRACHEN, key=f"p_sprache_{prefix}")
        set_id = c1.selectbox("Set (optional)", list(set_namen), format_func=set_namen.get, key=f"p_set_{prefix}")
        anzahl = c2.number_input("Anzahl", min_value=1, value=1, step=1, key=f"p_anzahl_{prefix}")
        kaufpreis = c2.number_input("Kaufpreis pro Stück in € (optional)", min_value=0.0, value=None, step=0.5, key=f"p_kauf_{prefix}")
        bild = c2.file_uploader("Bild (optional)", type=["png", "jpg", "jpeg", "webp"], key=f"p_bild_{prefix}")
        gesendet = st.form_submit_button("Zur Sammlung hinzufügen")
    if gesendet and not name.strip():
        st.error("Der Produktname ist Pflicht.")
    elif gesendet:
        bild_pfad = save_image(bild, "produkte")
        with transaktion() as cur:   # Produkt suchen oder anlegen, dann in die Sammlung (gibt es schon: Anzahl erhöhen)
            cur.execute("""INSERT INTO produkte (name, sprache, typ_id, set_id, bild_pfad, cm_id) VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (name, sprache) DO NOTHING""", (name.strip(), sprache, typ, set_id, bild_pfad, cm_id))
            cur.execute("SELECT produkt_id FROM produkte WHERE name = %s AND sprache = %s", (name.strip(), sprache))
            produkt_id = cur.fetchone()[0]
            if bild_pfad:
                cur.execute("UPDATE produkte SET bild_pfad = %s WHERE produkt_id = %s", (bild_pfad, produkt_id))
            if cm_id:
                cur.execute("UPDATE produkte SET cm_id = %s WHERE produkt_id = %s AND cm_id IS NULL", (cm_id, produkt_id))
            cur.execute("""INSERT INTO sammlung_produkte (produkt_id, anzahl, kaufpreis) VALUES (%s, %s, %s)
                           ON CONFLICT (produkt_id) DO UPDATE SET anzahl = sammlung_produkte.anzahl + EXCLUDED.anzahl,
                                                                kaufpreis = COALESCE(EXCLUDED.kaufpreis, sammlung_produkte.kaufpreis)""",
                        (produkt_id, int(anzahl), kaufpreis))
        preis_ok = cm_id is not None and preis_eintragen(produkt_id, cm_id)
        st.success(f"„{name.strip()}“ wurde hinzugefügt." + (" Der aktuelle Preis ist eingetragen." if preis_ok else
                   " Der Preis erscheint bei der nächsten Preisaktualisierung." if cm_id else ""))


def preis_eintragen(produkt_id, cm_id):
    """Trägt den heutigen Cardmarket-Preis sofort ein. Gibt True zurück, wenn das geklappt hat (ein Fehler hier ist unkritisch)."""
    try:
        stand, liste = katalog._preisliste()
        p = liste.get(cm_id)
        if not p:
            return False
        with transaktion() as cur:
            cur.execute("""INSERT INTO preis_produkte (produkt_id, datum, preis_cm, preis_ab) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (produkt_id, datum) DO UPDATE SET preis_cm = EXCLUDED.preis_cm, preis_ab = EXCLUDED.preis_ab""",
                        (produkt_id, stand, p.get("trend"), p.get("low")))
        return True
    except Exception:
        return False
