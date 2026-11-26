-- Beispielabfragen zur Datenbank der Pokémon-Sammlung (PostgreSQL)

-- 1) Neuester Preis je Karte der Sammlung: LEFT JOIN LATERAL holt pro Zeile genau den jüngsten Preis
SELECT k.name, s.name AS set_name, sk.anzahl, p.preis_cm, p.datum
FROM sammlung_karten sk
JOIN karten k ON k.karten_id = sk.karten_id
JOIN sets s   ON s.set_id = k.set_id
LEFT JOIN LATERAL (
    SELECT preis_cm, datum FROM preis_karten x
    WHERE x.karten_id = k.karten_id
    ORDER BY datum DESC LIMIT 1
) p ON TRUE
ORDER BY p.preis_cm DESC NULLS LAST;

-- 2) Preisänderung zwischen den letzten beiden Ständen: Fensterfunktion ROW_NUMBER
WITH r AS (
    SELECT karten_id, datum, preis_cm,
           ROW_NUMBER() OVER (PARTITION BY karten_id ORDER BY datum DESC) AS rn
    FROM preis_karten WHERE preis_cm IS NOT NULL
)
SELECT k.name, b.preis_cm AS vorher, a.preis_cm AS jetzt, a.preis_cm - b.preis_cm AS differenz
FROM r a
JOIN r b ON b.karten_id = a.karten_id AND a.rn = 1 AND b.rn = 2
JOIN karten k ON k.karten_id = a.karten_id
WHERE a.preis_cm <> b.preis_cm;

-- 3) Wert der Sammlung je Set: JOIN, GROUP BY, Aggregation
SELECT s.name AS set_name, SUM(sk.anzahl) AS karten,
       SUM(sk.anzahl * p.preis_cm) AS wert
FROM sammlung_karten sk
JOIN karten k ON k.karten_id = sk.karten_id
JOIN sets s   ON s.set_id = k.set_id
LEFT JOIN LATERAL (SELECT preis_cm FROM preis_karten x WHERE x.karten_id = k.karten_id
                   ORDER BY datum DESC LIMIT 1) p ON TRUE
GROUP BY s.name
ORDER BY wert DESC NULLS LAST;

-- 4) Gewinn/Verlust bei versiegelten Produkten: Kaufpreis, sonst UVP der Produktart (COALESCE)
SELECT pr.name, sp.anzahl,
       COALESCE(sp.kaufpreis, t.uvp) AS einkauf,
       pp.preis_cm AS aktuell,
       sp.anzahl * (pp.preis_cm - COALESCE(sp.kaufpreis, t.uvp)) AS gewinn
FROM sammlung_produkte sp
JOIN produkte pr      ON pr.produkt_id = sp.produkt_id
JOIN produkt_typen t  ON t.typ_id = pr.typ_id
LEFT JOIN LATERAL (SELECT preis_cm FROM preis_produkte x WHERE x.produkt_id = pr.produkt_id
                   ORDER BY datum DESC LIMIT 1) pp ON TRUE;

-- 5) Karte hinzufügen oder Anzahl erhöhen (Upsert): ON CONFLICT auf den eindeutigen Schlüssel
BEGIN;
INSERT INTO sammlung_karten (karten_id, anzahl, sprache, zustand, variante)
VALUES (1, 1, 'DE', 'NM', 'Normal')
ON CONFLICT (karten_id, sprache, zustand, variante)
DO UPDATE SET anzahl = sammlung_karten.anzahl + EXCLUDED.anzahl;
ROLLBACK;   -- nur zum Ausprobieren: nimmt die Änderung wieder zurück

-- 6) Regeln der Datenbank greifen: CHECK verhindert eine ungültige Sprache
-- INSERT INTO sammlung_karten (karten_id, sprache) VALUES (1, 'XX');
--   -> ERROR: new row ... violates check constraint "sammlung_karten_sprache_check"
