"""Cardmarket-Preise einlesen. Wird von der App und vom täglichen GitHub-Job benutzt."""
import json
import urllib.request
from datetime import date

import psycopg2.extras

PREIS_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_6.json"


def lade_preisliste(url=PREIS_URL):
    """Lädt die Preisliste von Cardmarket herunter und gibt sie als Python-Dict zurück."""
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Pokemon-Sammlung)"})
    with urllib.request.urlopen(anfrage, timeout=90) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def aktualisiere_preise(conn, daten):
    """Schreibt die Preise zu euren Karten und Produkten in die Datenbank.
    daten = Inhalt von price_guide_6.json (Dict). Gibt (Stand, Anzahl Karten, Anzahl Produkte) zurück."""
    stand = date.fromisoformat(daten["createdAt"][:10])
    preise = {p["idProduct"]: p for p in daten["priceGuides"]}
    with conn, conn.cursor() as cur:
        cur.execute("SELECT karten_id, cm_id FROM karten WHERE cm_id IS NOT NULL")
        karten = [(kid, stand, preise[cid].get("trend"), preise[cid].get("low"), preise[cid].get("trend-holo"))
                  for kid, cid in cur.fetchall() if cid in preise]
        cur.execute("SELECT produkt_id, cm_id FROM produkte WHERE cm_id IS NOT NULL")
        produkte = [(pid, stand, preise[cid].get("trend"), preise[cid].get("low"))
                    for pid, cid in cur.fetchall() if cid in preise]
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO preis_karten (karten_id, datum, preis_cm, preis_ab, preis_reverse) VALUES %s
               ON CONFLICT (karten_id, datum) DO UPDATE
               SET preis_cm = EXCLUDED.preis_cm, preis_ab = EXCLUDED.preis_ab, preis_reverse = EXCLUDED.preis_reverse""",
            karten,
        )
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO preis_produkte (produkt_id, datum, preis_cm, preis_ab) VALUES %s
               ON CONFLICT (produkt_id, datum) DO UPDATE
               SET preis_cm = EXCLUDED.preis_cm, preis_ab = EXCLUDED.preis_ab""",
            produkte,
        )
    return stand, len(karten), len(produkte)


if __name__ == "__main__":
    # Aufruf durch den täglichen GitHub-Job: Zugangsdaten kommen aus Umgebungsvariablen
    import os

    import psycopg2

    verbindung = psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT", "5432"), dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], sslmode="require",
    )
    print(aktualisiere_preise(verbindung, lade_preisliste()))
