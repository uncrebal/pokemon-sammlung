"""Produktkatalog (aus der Cardmarket-Produktliste): Sealed-Produkte nach Name oder Link finden.
Die Liste wird einmal am Tag von Cardmarket geladen, dafür gibt es keine eigene Tabelle. Cardmarket hat nur englische Namen:
deutsche Setnamen und Produktarten werden vor der Suche übersetzt („Stürmische Funken Top-Trainer-Box“ ->
„Surging Sparks Elite Trainer Box“)."""
import re
import unicodedata
import urllib.parse

import pandas as pd
import streamlit as st

import preise
from db import run_katalog

LISTE_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_nonsingles_6.json"

ARTEN = {"Pokémon Booster": "Booster", "Pokémon Display": "Display", "Pokémon Elite Trainer Boxes": "Top-Trainer-Box",
         "Pokémon Box Set": "Box / Kollektion", "Pokémon Tins": "Tin", "Pokémon Blisters": "Blister",
         "Pokémon Theme Decks": "Themendeck", "Pokémon Coins": "Münze", "Pokémon Trainer Kits": "Trainer-Kit",
         "Pokémon Lot": "Paket", "PCG Set": "Japanisches Set"}

# Deutsche Wörter -> englische Wörter bei Cardmarket (schon vereinfacht, siehe _woerter)
UEBERSETZUNG = [("top trainer box", "elite trainer box"), ("ttb", "elite trainer box"), ("etb", "elite trainer box"),("display", "booster box"), ("kollektion", "collection"),
                ("sammelbox", "collection"), ("sammelkoffer", "collection"), ("themendeck", "theme deck"),
                ("muenze", "coin"), ("tin box", "tin")]

# Wörter, die in eigenen Produktnamen vorkommen, aber nichts über das Produkt sagen
UNWICHTIG = {"pokemon", "tcg", "sammelkartenspiel", "karten", "deutsch", "englisch", "de", "en", "und", "the", "and", "of", "mit"}

# Vorschlag für die eigene Produktart: Steht das Wort links im Cardmarket-Namen oder in der Art,
# wird die erste eigene Produktart genommen, deren Name eines der Wörter rechts enthält.
ART_HINWEISE = [("elite trainer box", ["top trainer", "top-trainer", "elite", "etb"]), ("booster bundle", ["bundle"]),
                ("booster box", ["display", "booster box"]), ("display", ["display", "booster box"]),
                ("build battle", ["build"]), ("blister", ["blister"]), ("tin", ["tin"]),
                ("collection", ["kollektion", "collection"]), ("booster", ["booster"])]


def _woerter(text):
    """„Stürmische Funken: Top-Trainer-Box“ -> „stuermische funken top trainer box“ (klein, Umlaute ausgeschrieben, ohne Zeichen)."""
    text = str(text or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text))


@st.cache_resource(ttl=24 * 3600, show_spinner="Produktliste von Cardmarket wird geladen …")
def produktliste():
    """Alle Sealed-Produkte von Cardmarket, neueste zuerst, Münzen am Ende (Spalten: cm_id, name, art, kategorie, such, link)."""
    df = pd.DataFrame(preise.lade_preisliste(LISTE_URL)["products"])
    df = df.rename(columns={"idProduct": "cm_id", "categoryName": "kategorie"})
    df["art"] = df["kategorie"].map(ARTEN).fillna(df["kategorie"])
    df["such"] = df["name"].map(_woerter)
    df["link"] = df["name"].map(lambda n: re.sub(r"[^a-z0-9]", "", _woerter(n)))
    df["muenze"] = df["kategorie"] == "Pokémon Coins"
    df = df.sort_values(["muenze", "dateAdded", "cm_id"], ascending=[True, False, False])
    return df[["cm_id", "name", "art", "kategorie", "such", "link"]]


@st.cache_resource(ttl=24 * 3600, show_spinner=False)
def _uebersetzungen():
    """Deutsch -> Englisch aus dem Kartenkatalog: Setnamen („Stürmische Funken“) und einwortige Kartennamen („Glurak“),
    dazu die Produktarten. Längste zuerst, damit „Karmesin & Purpur“ vor „Purpur“ drankommt."""
    sets = run_katalog("SELECT name_de, name_en FROM katalog_sets WHERE name_de IS NOT NULL AND name_en IS NOT NULL")
    karten = run_katalog("SELECT DISTINCT name_de, name_en FROM katalog_karten WHERE name_de IS NOT NULL AND name_en IS NOT NULL")
    paare = {}
    for de, en in zip(karten["name_de"], karten["name_en"]):
        if " " not in _woerter(de):
            paare.setdefault(_woerter(de), _woerter(en))
    paare.update({_woerter(de): _woerter(en) for de, en in zip(sets["name_de"], sets["name_en"])})
    paare = sorted(((de, en) for de, en in paare.items() if de and de != en), key=lambda p: -len(p[0]))
    return paare + UEBERSETZUNG


def _uebersetzen(begriff):
    text = f" {_woerter(begriff)} "
    for de, en in _uebersetzungen():
        text = text.replace(f" {de} ", f" {en} ")
    return text.split()


def suchen(begriff, limit=100):
    """Produkte, deren Name alle Wörter des Begriffs enthält (deutsch oder englisch), oder die zum Cardmarket-Link passen.
    Ein Wort muss am Wortanfang passen: „tin“ findet „Tins“, aber nicht „Painting“."""
    alle = produktliste()
    begriff = begriff.strip()
    if "cardmarket." in begriff:
        teil = urllib.parse.urlparse(begriff if "://" in begriff else "https://" + begriff).path.rstrip("/").split("/")[-1]
        return alle[alle["link"] == re.sub(r"[^a-z0-9]", "", _woerter(teil))].reset_index(drop=True)
    passt = pd.Series(True, index=alle.index)
    for wort in _uebersetzen(begriff):
        passt &= alle["such"].str.contains(rf"\b{re.escape(wort)}")
    return alle[passt].head(limit).reset_index(drop=True)


def vorschlaege(begriff, limit=8):
    """Die am besten passenden Produkte, auch wenn nicht alle Wörter stimmen (für eigene, abweichende Produktnamen).
    Es muss mindestens die Hälfte der Wörter passen. Bei gleich vielen Wörtern: keine Münzen, dann der kürzeste Name."""
    if "cardmarket." in begriff:
        return suchen(begriff)
    alle = produktliste()
    woerter = [w for w in _uebersetzen(begriff) if w not in UNWICHTIG]
    if not woerter:
        return alle.iloc[0:0].reset_index(drop=True)
    anzahl = sum(alle["such"].str.contains(rf"\b{re.escape(w)}").astype(int) for w in woerter)
    df = alle.assign(anzahl=anzahl, muenze=alle["kategorie"] == "Pokémon Coins", laenge=alle["such"].str.len())
    df = df[df["anzahl"] >= max(1, (len(woerter) + 1) // 2)]
    df = df.sort_values(["anzahl", "muenze", "laenge"], ascending=[False, True, True], kind="stable")
    return df.head(limit).drop(columns=["anzahl", "muenze", "laenge"]).reset_index(drop=True)


def art_vorschlag(produkt, typ_namen):
    """Die eigene Produktart (typ_id), die am besten zum Cardmarket-Produkt passt, sonst die erste."""
    text = f" {_woerter(produkt['name'])} {_woerter(produkt['kategorie'])} "
    for wort, hinweise in ART_HINWEISE:
        if f" {wort} " in text:
            for typ_id, typ in typ_namen.items():
                if any(h in typ.lower() for h in hinweise):
                    return typ_id
    return next(iter(typ_namen))
