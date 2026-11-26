"""Gemeinsame Bausteine für alle Ansichten: feste Auswahllisten, Formatierung, Cardmarket-Links und die Liste mit Details."""
import urllib.parse

import pandas as pd
import streamlit as st

SPRACHEN = ["DE", "EN", "JP", "KR", "ZH"]
ZUSTAENDE = ["NM", "M", "EX", "GD", "LP", "PL", "PO"]
VARIANTEN = ["Normal", "Holo", "Reverse Holo", "Pokéball Reverse Holo", "Masterball Reverse Holo", "First Edition"]
EURO = st.column_config.NumberColumn(format="%.2f €")     # Spaltenformat für Tabellen


def handy():
    """True, wenn oben die Handy-Ansicht eingeschaltet ist."""
    return st.session_state.get("mobil", False)


def euro(x):
    """12345.6 -> „12.345,60 €“; leere Werte -> „“."""
    if x is None or pd.isna(x):
        return ""
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def leer(x):
    """True für fehlende Werte: None, NaN, leerer Text oder der Text „None“ (so steht es bei manchen Karten im Katalog)."""
    return x is None or (not isinstance(x, str) and pd.isna(x)) or str(x).strip() in ("", "None")


def mit_punkt(x):
    """„ · Wert“ für Untertitel, oder nichts, wenn der Wert fehlt."""
    return "" if leer(x) else f" · {x}"


def leer_zu_none(text):
    text = (text or "").strip()
    return text or None


def cm_link(cm_id):
    """Link zur Cardmarket-Seite (Cardmarket leitet die Produktnummer selbst auf die richtige Seite weiter)."""
    if cm_id is None or pd.isna(cm_id):
        return None
    return f"https://www.cardmarket.com/de/Pokemon/Products?idProduct={int(cm_id)}"


def cm_link_oder_suche(cm_id, name, nr):
    """Direktlink zur Karte auf Cardmarket; ohne bekannte Produktnummer ein Suchlink mit Name und Nummer."""
    return cm_link(cm_id) or ("https://www.cardmarket.com/de/Pokemon/Products/Search?searchString="
                              + urllib.parse.quote_plus(f"{name} {nr}"))


def mehr_knopf(schluessel, gesamt, schritt=30):
    """Gibt zurück, wie viele Einträge gezeigt werden, und zeigt bei Bedarf „Mehr anzeigen“."""
    n = st.session_state.get(schluessel, schritt)
    if gesamt > n and st.button(f"Mehr anzeigen ({gesamt - n} weitere)", key=f"mehr_{schluessel}", width="stretch"):
        st.session_state[schluessel] = n + schritt
        st.rerun()
    return n


def gewaehlte_zeile(df, id_spalte, name, zurueck="← Zurück zur Liste"):
    """Ist in der Liste „name“ ein Eintrag gewählt (st.session_state["sel_<name>"]), zeigt den Zurück-Knopf
    und gibt die Zeile zurück. Sonst None. Die Ansichten rufen das ganz oben auf, damit die Details sofort oben stehen."""
    schluessel = f"sel_{name}"
    gewaehlt = st.session_state.get(schluessel)
    treffer = df[df[id_spalte] == gewaehlt] if gewaehlt is not None else df.iloc[0:0]
    if treffer.empty:
        st.session_state.pop(schluessel, None)
        return None
    if st.button(zurueck, key=f"zurueck_{name}", width="stretch" if handy() else "content"):
        st.session_state.pop(schluessel, None)
        st.rerun()
    return treffer.iloc[0]


def knopf_zeile(html, knopf, key, on_click=None, args=(), kwargs=None, knopf_breite=2):
    """Eine Listenzeile mit Knopf rechts daneben (am Handy ein kleiner Pfeil statt Text). Gibt True zurück, wenn geklickt."""
    c_zeile, c_knopf = st.columns([14, 3 if handy() else knopf_breite], vertical_alignment="center")
    c_zeile.markdown(html, unsafe_allow_html=True)
    return c_knopf.button("›" if handy() else knopf, key=key, width="stretch", on_click=on_click, args=args, kwargs=kwargs)


def liste_mit_auswahl(df, id_spalte, zeile_html, name, knopf="Details", zurueck="← Zurück zur Liste", tabelle=None, knopf_breite=2):
    """Die Liste, die Karten, Produkte, Vollständigkeit und Kartensuche gemeinsam nutzen.

    Jede Zeile von df wird mit zeile_html(zeile) gezeichnet und bekommt einen Knopf (z. B. „Details“).
    Ein Klick merkt sich die Zeile in st.session_state["sel_<name>"]; beim nächsten Aufbau zeigt gewaehlte_zeile() sie an.
    Gibt die gewählte Zeile zurück (falls schon gewählt), sonst None.
    tabelle = (Spalten, Spaltenbeschriftungen): bietet zusätzlich den Schalter „Alle Spalten als Tabelle zeigen“."""
    z = gewaehlte_zeile(df, id_spalte, name, zurueck)
    if z is not None:
        return z
    if tabelle and not handy() and st.toggle("Alle Spalten als Tabelle zeigen", key=f"tabelle_{name}",
                                             help="Zeigt statt der Liste die Tabelle mit allen Angaben. Zeile anklicken öffnet die Details."):
        spalten, beschriftung = tabelle
        auswahl = st.dataframe(df[spalten], hide_index=True, width="stretch", column_config=beschriftung,
                               on_select="rerun", selection_mode="single-row", key=f"tab_{name}_{st.session_state.get('v', 0)}")
        return df.iloc[auswahl.selection.rows[0]] if auswahl.selection.rows else None

    n = st.session_state.get(f"limit_{name}", 30)
    with st.container(key=f"liste_{name}"):
        for z in df.iloc[:n].itertuples():
            wert = getattr(z, id_spalte)
            if knopf_zeile(zeile_html(z), knopf, f"auf_{name}_{wert}", knopf_breite=knopf_breite):
                st.session_state[f"sel_{name}"] = wert.item() if hasattr(wert, "item") else wert
                st.rerun()
    mehr_knopf(f"limit_{name}", len(df))
    return None


def einfache_liste(df, zeile_html, name):
    """Liste ohne Knöpfe (nur zum Ansehen), 30 Einträge und „Mehr anzeigen“."""
    n = st.session_state.get(f"limit_{name}", 30)
    with st.container(key=f"liste_{name}"):
        for z in df.iloc[:n].itertuples():
            st.markdown(zeile_html(z), unsafe_allow_html=True)
    mehr_knopf(f"limit_{name}", len(df))
