"""Reiter „Hinzufügen“ → „Mehrere Karten“: viele Karten auf einmal (Links oder Namen, eine pro Zeile)."""
import streamlit as st

from bausteine import SPRACHEN, VARIANTEN, ZUSTAENDE, mit_punkt
from design import zeile
from katalog import add_karte_katalog, katalog_bild, variante_vorschlag, zeile_zu_treffern


def _beschriftung(t, j):
    z = t.iloc[j]
    return f"{z['name']} · {z['set_name']} · Nr. {z['nr']}{mit_punkt(z['seltenheit'])}"


def zeigen():
    st.caption("Pro Zeile ein Link (Cardmarket oder TCGdex) oder ein Kartenname, optional mit Nummer am Ende, "
               "z. B. „Pikachu 025“. Danach prüfst du die Treffer und fügst alle auf einmal hinzu.")
    zaehler = st.session_state.get("bulk_n", 0)      # wird nach dem Hinzufügen erhöht, das leert das Textfeld
    text = st.text_area("Karten", height=180, key=f"bulk_text_{zaehler}", label_visibility="collapsed",
                        placeholder="https://www.cardmarket.com/de/Pokemon/Products/Singles/Obsidian-Flames/Charizard-ex-V2-OBF125\nGlurak ex 125\nPikachu")
    b1, b2, b3, b4 = st.columns(4)
    sprache = b1.selectbox("Sprache für alle", SPRACHEN, key="bulk_sprache")
    zustand = b2.selectbox("Zustand für alle", ZUSTAENDE, key="bulk_zustand")
    anzahl = b3.number_input("Anzahl je Karte", min_value=1, value=1, step=1, key="bulk_anzahl")
    variante = b4.selectbox("Variante", ["Automatisch"] + VARIANTEN, key="bulk_variante",
                            help="Automatisch nimmt die im Katalog hinterlegte Art (Normal, Holo oder Reverse Holo).")
    zeilen = [z.strip() for z in text.splitlines() if z.strip()][:60]
    if not zeilen:
        if st.session_state.get("bulk_meldung"):
            st.success(st.session_state.pop("bulk_meldung"))
        return

    st.subheader("Treffer prüfen")
    gewaehlt = []
    for i, eingabe in enumerate(zeilen):
        try:
            treffer, hinweis = zeile_zu_treffern(eingabe)
        except Exception as fehler:
            treffer, hinweis = None, f"Fehler: {fehler}"
        kurz = eingabe if len(eingabe) < 60 else eingabe[:57] + "…"
        if treffer is None:
            st.warning(f"**{kurz}**: {hinweis}")
            continue
        if len(treffer) == 1:
            st.write(f"✅ **{kurz}** → {_beschriftung(treffer, 0)}")
            wahl = 0
        else:
            wahl = st.selectbox(f"{kurz}: {len(treffer)} Treffer, welche?", range(len(treffer)), index=None,
                                placeholder="Bitte auswählen (oder leer lassen zum Überspringen)",
                                format_func=lambda j, t=treffer: _beschriftung(t, j), key=f"bulk_wahl_{zaehler}_{i}")
        if wahl is not None:
            gewaehlt.append(treffer.iloc[wahl])
    if not gewaehlt:
        return

    for k in gewaehlt:
        st.markdown(zeile(k["name"], f"{k['set_name']} · Nr. {k['nr']}", bild=katalog_bild(k, "low")), unsafe_allow_html=True)
    if st.button(f"{len(gewaehlt)} Karten zur Sammlung hinzufügen", type="primary", key="bulk_los"):
        fortschritt = st.progress(0.0)
        fehler_liste = []
        for n, k in enumerate(gewaehlt, 1):
            try:
                add_karte_katalog(k, {"sprache": sprache, "zustand": zustand, "anzahl": int(anzahl), "notiz": None,
                                      "variante": variante_vorschlag(k) if variante == "Automatisch" else variante})
            except Exception as fehler:
                fehler_liste.append(f"{k['name']}: {fehler}")
            fortschritt.progress(n / len(gewaehlt))
        if fehler_liste:
            st.error(f"{len(gewaehlt) - len(fehler_liste)} Karten hinzugefügt, {len(fehler_liste)} Fehler:")
            st.code("\n".join(fehler_liste))
        else:
            st.session_state["bulk_n"] = zaehler + 1
            st.session_state["bulk_meldung"] = (f"{len(gewaehlt)} Karten wurden hinzugefügt. "
                                                "Preise erscheinen bei der nächsten Preisaktualisierung, falls sie noch fehlen.")
            st.rerun()
