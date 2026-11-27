# Dokumentation

Wie die App benutzt wird, woher die Daten kommen und wie sie betrieben wird. Den Datenbankentwurf beschreibe ich
gesondert in [datenbank.md](datenbank.md).

## Ziel
- Eine Datenbank für Pokémon-Karten und versiegelte Produkte (Booster, Boxen, Displays, Tins)
- Bedienung im Browser, auch am Handy, ohne IT-Kenntnisse
- Zu jeder Karte und jedem Produkt ein Bild und ein ungefährer Preis, dazu der Gesamtwert und sein Verlauf
- Nur wenige Personen haben Zugriff, für Fremde ist die App gesperrt
- Für mich: Datenbankdesign an einem echten Beispiel lernen

## Bausteine

| Baustein | Aufgabe | Wo |
|---|---|---|
| PostgreSQL | speichert alle Daten | Supabase (Rechenzentrum in der EU), kostenloser Tarif |
| Streamlit-App | Oberfläche im Browser | Streamlit Community Cloud, als private App |
| GitHub | Code und Produktbilder, wöchentliches Backup | privates Repository |
| DBeaver | Datenbank ansehen, SQL ausführen, Struktur ändern | auf meinem PC |
| Cardmarket | tägliche Preisliste und Produktliste | öffentliche Dateien |
| TCGdex | Kartenkatalog mit deutschen Namen und Bildern | offenes Projekt |

Die App ändert nur Daten, nie die Struktur. Neue Tabellen oder Spalten lege ich selbst in DBeaver an.

## Die App benutzen

| Ansicht | Was man dort macht |
|---|---|
| Übersicht | Gesamtwert, Gewinn bei Produkten, Wertverlauf, wertvollste Karten, Export als Excel. Beträge sind beim Öffnen ausgeblendet. |
| Karten | Suchen, filtern, Details mit großem Bild, Anzahl ändern, eigenen Preis setzen, löschen |
| Produkte | wie Karten, dazu Kaufpreis und die UVP je Produktart für die Gewinnberechnung |
| Hinzufügen | eine Karte per Suche oder Cardmarket-Link, mehrere Karten auf einmal, Produkte über die Cardmarket-Liste |
| Vollständigkeit | wie viel von jedem Set vorhanden ist und welche Karten fehlen |
| Sets | alle Sets, eigene Sets anlegen (z. B. japanische) |
| Preise | Preisstand, größte Preisänderungen, Preise von Hand neu holen |

Oben gibt es eine globale Suche über Sammlung und Katalog. Die gewählte Seite steht in der Adresse, deshalb bleibt
man beim Neuladen auf derselben Seite. Mit `?m=1` am Ende der Adresse öffnet sich die Handy-Ansicht.

Wird dieselbe Karte in gleicher Sprache, gleichem Zustand und gleicher Variante noch einmal hinzugefügt, erhöht
die App nur die Anzahl.

## Woher die Daten kommen
Die Sammlung lag vorher in einer Excel-Liste, einer Sammler-App und auf einer Sammler-Webseite. Daraus wurden
SQL-Importskripte erzeugt und nacheinander in DBeaver ausgeführt.

| Quelle | Inhalt |
|---|---|
| Export einer Sammler-App (CSV) | erste Karten und Produkte |
| Excel-Liste | Produktbilder, die als Bilder in Zellen gespeichert waren |
| Sammler-Webseite (gespeicherte Seiten) | zweiter, größerer Import |
| TCGdex | Kartenkatalog mit rund 21.000 Karten, deutsche Namen, Bilder |
| Cardmarket | Preise und Liste aller Produkte |

Regeln beim Import:
- Alle Skripte dürfen mehrfach laufen, ohne Daten doppelt anzulegen.
- Ein großer Import läuft in einer Transaktion: Bei einem Fehler wird nichts gespeichert.
- Vor großen Importen gibt es ein frisches Backup.
- Unsichere Zuordnungen bekommen einen Vermerk „prüfen“ und werden von Hand kontrolliert.

## Preise
- Cardmarket stellt täglich eine öffentliche Preisliste bereit. Die App lädt sie höchstens alle 6 Stunden, wenn der
  Stand älter als heute ist, und schreibt pro Karte und Tag eine Zeile.
- Angezeigt wird: eigener Preis, falls gesetzt, sonst bei Reverse-Holo-Karten der passende Preis, sonst der
  Trendpreis.
- Die Preise sind Orientierungswerte. Zustand und Sprache unterscheidet Cardmarket dabei nicht.

## Betrieb

| Thema | Lösung |
|---|---|
| Zugangsdaten | nur in den Einstellungen von Streamlit und GitHub, nie im Code |
| Zugriff | private App, nur eingetragene E-Mail-Adressen dürfen sie öffnen |
| Backup | wöchentlich per `pg_dump` über GitHub Actions, 90 Tage aufbewahrt, zusätzlich Sicherungen aus DBeaver |
| Pause | Supabase pausiert kostenlose Projekte nach 7 Tagen ohne Zugriff, dann im Dashboard wieder starten |
| Strukturänderungen | erst die Spalte in der Datenbank anlegen, dann den Code hochladen. Einmal ist die App abgestürzt, weil es andersherum war. |
| Änderungen am Code | landen über GitHub automatisch in der App. Geht etwas schief, wird der Commit zurückgenommen. |
| Tests | Die App wird mit Streamlits AppTest gegen Beispieldaten getestet, nicht gegen die echte Datenbank. |
| Sicherheit im Code | Eingaben werden als Parameter an die Datenbank übergeben, nicht in den SQL-Text eingebaut. Das verhindert SQL-Injection. |

## Was noch offen ist
- Eigene Fotos aus den Formularen gehen beim Neustart der App verloren. Dauerhaft ginge das mit einem
  Dateispeicher wie Supabase Storage.
- Eine falsche Cardmarket-Zuordnung lässt sich nur in DBeaver korrigieren, noch nicht in der App.
- Das Werkzeug für fehlende Bilder ist nicht gegen alle Bildquellen getestet.
