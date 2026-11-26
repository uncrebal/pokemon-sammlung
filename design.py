"""Aussehen der App (rotes Pokédex-Design): Farben, Kopfzeile und die HTML-Bausteine für Listen.
Die Grundfarben für Tabellen stehen zusätzlich in .streamlit/config.toml."""
import html

import pandas as pd
import streamlit as st

# Farben: Rot #D32F2F · Dunkelrot #B02424 · Dunkel #1B2433 · Beige #F3EFE4 · Gelb #FFCB05 · Blau #2F80ED
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Nunito:wght@400;600;700;800&display=swap');
.stApp {background: #F3EFE4; color: #1B2433; font-family: 'Nunito', sans-serif;}
[data-testid="stHeader"] {background: transparent;}
h1, h2, h3, h4 {font-family: 'Baloo 2', sans-serif !important; color: #1B2433 !important; letter-spacing: 0;}
.block-container {padding-bottom: 4rem !important;}
/* Kopfzeile */
.pk-kopf {display: flex; align-items: center; gap: 16px; background: #D32F2F; border: 4px solid #1B2433; border-radius: 20px;
          box-shadow: 5px 5px 0 #1B2433; padding: 12px 22px; margin-bottom: 14px;}
.pk-linse {width: 46px; height: 46px; border-radius: 50%; background: #2F80ED; border: 4px solid #fff; box-shadow: 0 0 0 4px #1B2433; flex: none;}
.pk-punkte {display: flex; gap: 6px; flex: none;}
.pk-punkte i {width: 13px; height: 13px; border-radius: 50%; border: 2px solid #1B2433; display: block;}
.pk-titel {font-family: 'Baloo 2', sans-serif; font-weight: 800; font-size: 2rem; color: #fff; line-height: 1.1; flex: 1;}
.pk-baelle {display: flex; gap: 6px; align-items: center; flex: none;}
/* Menü (Ansichten) und andere Auswahlreihen */
[data-testid="stRadio"] [role="radiogroup"] {gap: 8px; flex-wrap: wrap;}
[data-testid="stRadioOption"] > div > div:first-child {display: none;}
[data-testid="stRadioOption"] {background: #fff; border: 2px solid #1B2433; border-radius: 999px; padding: 2px 12px; margin: 0; cursor: pointer;}
[data-testid="stRadioOption"] p {color: #1B2433 !important; font-weight: 700;}
[data-testid="stRadioOption"]:has(input:checked) {background: #2F80ED;}
[data-testid="stRadioOption"]:has(input:checked) p {color: #fff !important;}
.st-key-ansicht [data-testid="stRadioOption"] {background: #B02424; border: 3px solid #1B2433; border-radius: 14px; padding: 4px 14px;
                       box-shadow: 3px 3px 0 #1B2433; transition: transform .08s;}
.st-key-ansicht [data-testid="stRadioOption"]:hover {transform: translate(-1px,-1px);}
.st-key-ansicht [data-testid="stRadioOption"] p {color: #fff !important; font-weight: 800;}
.st-key-ansicht [data-testid="stRadioOption"]:has(input:checked) {background: #FFCB05;}
.st-key-ansicht [data-testid="stRadioOption"]:has(input:checked) p {color: #1B2433 !important;}
/* Kennzahlen, Aufklappbereiche, Formulare, Tabellen */
[data-testid="stMetric"] {background: #fff; border: 3px solid #1B2433; border-radius: 18px; box-shadow: 5px 5px 0 #1B2433; padding: 14px 18px;}
[data-testid="stMetricValue"] {font-family: 'Baloo 2', sans-serif; font-weight: 800;}
[data-testid="stDataFrame"], [data-testid="stExpander"], [data-testid="stForm"] {border: 3px solid #1B2433 !important; border-radius: 16px !important;
          box-shadow: 4px 4px 0 #1B2433; background: #fff; overflow: hidden;}
[data-testid="stExpander"] details {border: none !important;}
[data-testid="stSidebar"] {background: #FFF6CC; border-right: 4px solid #1B2433;}
/* Knöpfe */
.stButton > button, .stDownloadButton > button, .stLinkButton > a, [data-testid="stFormSubmitButton"] > button {
    background: #fff; color: #1B2433; border: 3px solid #1B2433; border-radius: 999px; font-weight: 800; box-shadow: 3px 3px 0 #1B2433;
    transition: transform .08s, box-shadow .08s;}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {transform: translate(-1px,-1px); box-shadow: 4px 4px 0 #1B2433; color: #1B2433; border-color: #1B2433;}
.stButton > button:active {transform: translate(2px,2px); box-shadow: 1px 1px 0 #1B2433;}
button[data-testid="stBaseButton-primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {background: #D32F2F; color: #fff;}
button[data-testid="stBaseButton-primary"]:hover {color: #fff;}
.st-key-werte_knopf button {background: #FFCB05 !important; color: #1B2433 !important;}
/* Eingabefelder */
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"],
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"], [data-testid="stDateInput"] [role="group"] {
    border: 3px solid #1B2433 !important; border-radius: 14px !important; background: #fff !important; overflow: hidden;}
.st-key-global_suche [data-testid="stTextInputRootElement"] {border-radius: 999px !important;}
[data-testid="stFileUploaderDropzone"] {border: 3px dashed #1B2433 !important; border-radius: 14px !important; background: #fff !important;}
/* Listen (Karten, Produkte, Sets …) */
[class*="st-key-liste_"] {gap: .55rem;}
[class*="st-key-liste_"] button {min-height: 2.3rem;}
.zeile {display: flex; align-items: center; gap: 14px; background: #fff; border: 3px solid #1B2433; border-radius: 14px;
        box-shadow: 3px 3px 0 #1B2433; padding: 6px 16px 6px 8px; min-height: 78px; margin: 3px 6px 6px 0;}
.zeile img, .zeile .platz {width: 46px; height: 64px; object-fit: contain; flex: none; border-radius: 4px;}
.zeile .platz {background: #EEE;}
.zt {flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.3;}
.zt b {font-size: 1.05rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.zs {font-size: .85rem; color: #5A6475; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.zc {display: flex; gap: 6px; flex: none;}
.chip {background: #2F80ED; color: #fff; font-weight: 800; font-size: .75rem; border-radius: 999px; padding: 2px 10px; white-space: nowrap;}
.chip.leise {background: #FFE680; color: #1B2433;}
.zn {font-family: 'Baloo 2', sans-serif; font-weight: 800; font-size: 1.2rem; width: 48px; text-align: center; flex: none;}
.zp {font-family: 'Baloo 2', sans-serif; font-weight: 800; font-size: 1.15rem; color: #D32F2F; min-width: 92px; text-align: right; flex: none;}
.zp.hoch {color: #1B7A46;}
.zp small {font-size: .8rem; font-weight: 700;}
.prozent {width: 58px; height: 58px; border: 4px solid #D32F2F; border-radius: 50%; display: flex; align-items: center; justify-content: center;
          font-family: 'Baloo 2', sans-serif; font-weight: 800; font-size: 1rem; flex: none; background: #fff;}
.balken {flex: 0 0 38%; height: 16px; background: #E9E3D2; border: 2px solid #1B2433; border-radius: 999px; overflow: hidden;}
.balken i {display: block; height: 100%; border-radius: 999px;}
.cmlink {flex: none; font-weight: 800; color: #D32F2F !important; text-decoration: none; border: 2px solid #D32F2F; border-radius: 999px; padding: 3px 12px; white-space: nowrap;}
table.fakten {border-collapse: collapse; width: 100%; background: #fff; border: 3px solid #1B2433; border-radius: 12px; overflow: hidden; margin: .4rem 0 .8rem;}
table.fakten th {text-align: left; background: #D32F2F; color: #fff; padding: 5px 12px; width: 42%; font-weight: 700;}
table.fakten td {padding: 5px 12px; border-bottom: 1px solid #E5E0D0;}
/* Listen: Zeile und Knopf bleiben nebeneinander, auch am Handy */
[class*="st-key-liste_"] [data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important; gap: .5rem !important;}
[class*="st-key-liste_"] [data-testid="stColumn"] {min-width: 0 !important;}
@media (max-width: 900px) {.pk-baelle, .pk-punkte {display: none;} .balken {flex-basis: 25%;}}
/* Handy (schmaler Bildschirm) */
@media (max-width: 640px) {
  .pk-kopf {padding: 8px 14px; gap: 10px; border-width: 3px; margin-bottom: 6px; box-shadow: 3px 3px 0 #1B2433;}
  .pk-linse {width: 28px; height: 28px; border-width: 3px; box-shadow: 0 0 0 3px #1B2433;}
  .pk-titel {font-size: 1.25rem;}
  /* Zeile als Raster: Bild | Name + Etiketten | Anzahl + Preis, damit der Name mehr Platz hat */
  .zeile {display: grid; grid-template-columns: auto 1fr auto; column-gap: 10px; row-gap: 3px; align-items: center;
          padding: 6px 10px 6px 6px; min-height: 66px; margin: 2px 3px 4px 0; box-shadow: 2px 2px 0 #1B2433;}
  .zeile > img, .zeile > .platz, .zeile > .prozent, .zeile > svg {grid-column: 1; grid-row: 1 / span 2;}
  .zeile img, .zeile .platz {width: 38px; height: 53px;}
  .zt {grid-column: 2; grid-row: 1;}
  .zt b {font-size: .98rem;}
  .zs {white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-size: .8rem;}
  .zc {grid-column: 2; grid-row: 2; gap: 4px;}
  .chip {font-size: .68rem; padding: 1px 7px;}
  .zn {grid-column: 3; grid-row: 1; width: auto; font-size: 1rem; text-align: right;}
  .zp {grid-column: 3; grid-row: 2; min-width: 0; font-size: 1rem;}
  .zeile > .cmlink {grid-column: 3; grid-row: 1 / span 2;}
  .prozent {width: 44px; height: 44px; font-size: .85rem; border-width: 3px;}
  .balken {display: none;}
  .cmlink {padding: 2px 8px; font-size: .8rem;}
  [class*="st-key-liste_"] {gap: .3rem;}
  [class*="st-key-liste_"] [data-testid="stColumn"] .stButton > button {min-height: 66px; padding: 0; border-radius: 14px; box-shadow: 2px 2px 0 #1B2433;}
  [class*="st-key-liste_"] [data-testid="stColumn"] .stButton > button p {font-size: 1.7rem; line-height: 1;}
  .st-key-liste_suche {padding: 10px 8px !important;}
  [data-testid="stMetric"] {padding: 8px 14px; box-shadow: 3px 3px 0 #1B2433;}
  [data-testid="stMetricValue"] > div {font-size: 1.6rem !important;}
  table.fakten th, table.fakten td {padding: 4px 8px; font-size: .9rem;}
}
</style>"""

# Zusätzlich in der Handy-Ansicht: größere Schrift und Knöpfe, weniger Rand
CSS_HANDY = """<style>
.block-container {padding: 2.2rem 0.7rem 4rem !important;}
.stButton > button, .stDownloadButton > button, .stLinkButton > a {min-height: 2.8rem;}
input, textarea, [data-baseweb="select"] {font-size: 16px !important;}   /* 16 px: das iPhone zoomt dann nicht ins Feld */
</style>"""

POKEBALL = ('<svg width="{n}" height="{n}" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" fill="#fff" stroke="#1B2433" stroke-width="3"/>'
            '<path d="M2 20a18 18 0 0 1 36 0z" fill="#D32F2F" stroke="#1B2433" stroke-width="3" stroke-linejoin="round"/>'
            '<line x1="2" y1="20" x2="38" y2="20" stroke="#1B2433" stroke-width="3"/>'
            '<circle cx="20" cy="20" r="6" fill="#fff" stroke="#1B2433" stroke-width="3"/></svg>')


def anwenden(handy=False):
    """Design einbinden und die rote Kopfzeile zeichnen."""
    st.markdown(CSS + (CSS_HANDY if handy else ""), unsafe_allow_html=True)
    st.markdown(
        '<div class="pk-kopf"><div class="pk-linse"></div>'
        '<div class="pk-punkte"><i style="background:#FF8A80"></i><i style="background:#FFCB05"></i><i style="background:#5CDB95"></i></div>'
        '<div class="pk-titel">Pokémon-Sammlung</div>'
        '<div class="pk-baelle">' + POKEBALL.format(n=34) + POKEBALL.format(n=24) + POKEBALL.format(n=16) + '</div></div>',
        unsafe_allow_html=True,
    )


def text(x):
    """Wert für die Anzeige: leere Werte werden zu „–“, alles wird HTML-sicher gemacht."""
    if x is None or (not isinstance(x, str) and pd.isna(x)) or str(x).strip() in ("", "None"):
        return "–"
    return html.escape(str(x))


def zeile(titel, unter="", bild=None, vorne=None, chips=(), anzahl=None, rechts="", rechts_klasse="", hinten=""):
    """Eine Zeile einer Liste als HTML.
    vorne: eigenes HTML statt Bild (z. B. Pokéball oder Prozent-Kreis); bild="" zeigt einen grauen Platzhalter.
    chips: Liste von (Text, Klasse) für die Etiketten; rechts und hinten sind fertiges HTML."""
    if vorne is None:
        vorne = f'<img src="{html.escape(bild)}" loading="lazy" alt="">' if bild else ('<div class="platz"></div>' if bild is not None else "")
    teile = ['<div class="zeile">', vorne,
             f'<div class="zt"><b>{html.escape(str(titel))}</b><span class="zs">{html.escape(str(unter))}</span></div>']
    if chips:
        teile.append('<div class="zc">' + "".join(f'<span class="chip {k}">{html.escape(str(t))}</span>' for t, k in chips) + "</div>")
    if anzahl is not None:
        teile.append(f'<div class="zn">{"×" + str(int(anzahl)) if anzahl else ""}</div>')
    if rechts:
        teile.append(f'<div class="zp {rechts_klasse}">{rechts}</div>')
    teile += [hinten, "</div>"]
    return "".join(teile)


def fakten_tabelle(paare):
    """Tabelle „Bezeichnung | Wert“ für die Detailansicht."""
    st.markdown('<table class="fakten">' + "".join(f"<tr><th>{html.escape(a)}</th><td>{text(b)}</td></tr>" for a, b in paare)
                + "</table>", unsafe_allow_html=True)
