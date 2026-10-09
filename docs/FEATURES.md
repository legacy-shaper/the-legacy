# The Legacy — registre des fonctions (à lire à chaque session)

Ce fichier est la mémoire permanente de ce qui existe dans les deux applications.
**Règle (Dylan, 9 oct. 2026)** : toute nouvelle fonction codée est ajoutée ici dans le même commit
(où la trouver, comment elle marche, le test qui la couvre). Avant de dire « ça n'existe pas » ou de
recoder quelque chose, relire ce fichier et chercher dans le code.

Master = `tools/master.html` → `app/` (https://legacy-shaper.github.io/the-legacy/app/).
Client = `tools/client.html` → `client/` → repo `legacy-shaper/app` (https://app.legacy-shaper.com).

## Œuvres — fiches et PDF

| Fonction | App | Où | Comment | Test |
|---|---|---|---|---|
| Fiche PDF d'une œuvre | master | fiche œuvre → « Fiche PDF » | Template `ficheHTML()` (logo, photo principale HD, artiste gras, titre italique + date, technique, dimensions cm + inches, édition, description, provenance si case cochée, « Copyright The Artist / Courtesy of Legacy Shaper »). `exportFiche()` | `test_scale_view.py` |
| Fiche + vues supplémentaires | master | fiche œuvre → « Fiche + additional views… » | Page 1 = fiche, puis une pleine page par vue cochée (+ page « à l'échelle » si cochée). `openViewsChooser()` | `test_scale_view.py` |
| **PDF de plusieurs œuvres** (9 oct. 2026) | master | liste Œuvres → « Sélectionner pour un PDF » → cocher → « Créer le PDF » | Une fiche pleine page par œuvre (même template `ficheHTML`, photo principale HD, provenance si la case « provenance » est cochée), ordre de la liste, un seul fichier `Legacy_Shaper_-_N_works_-_AAAA-MM-JJ.pdf` (1 œuvre = nom habituel de sa fiche). « Tout sélectionner » suit les filtres et la recherche. `exportFicheSet()`, `artSel` | `test_master_fiche_set.py` |
| Fiche d'inventaire (client) | client | œuvre → « Fiche d'inventaire (PDF) » | `sheetHTML()` + `printHTML()` (impression → PDF du téléphone/Mac). Page « à l'échelle » en option | `test_client.py` |
| **Fiches d'inventaire de plusieurs œuvres** (9 oct. 2026) | client | Œuvres → « Sélectionner » → cocher → « Fiches d'inventaire (PDF) » | Une fiche par page A4, un seul PDF « Collection - N œuvres - date ». `workTap()`, `selBar()`, `printSheets()`. `fitSheets()` réduit la photo (min. 55 mm) si le texte est long, pour qu'une œuvre tienne toujours sur une page (vaut aussi pour la fiche seule) | `test_client_sheets.py` (vérifie le vrai PDF imprimé : 1 page par œuvre) |

## Autres fonctions déjà en place (résumé)
- Vue à l'échelle (chaise cannée, parquet Versailles) : `tools/room.js`, master + client — `test_scale_view.py`, `test_client_room.py`.
- Emballage & caisse (crating) sur la fiche œuvre : master + client — `test_master_crating.py`, `test_client_crating.py`.
- Copropriétaires et cloisonnement des collections clients — `test_master_coowners.py`, `test_master_collections.py`.
- Contacts (emails/téléphones pro et perso, primary, documents hors comptabilité) — `test_master_contacts.py`.
- Messagerie client ↔ Legacy Shaper — `test_master_messages.py`, `test_client_chat.py`.
- App client hors ligne — `test_client_offline.py`.
- Factures, dépenses, comptabilité AED, sauvegarde hebdomadaire : voir le skill « the-legacy ».

## Tester avant de publier
Toutes les suites de `tests/` doivent passer (zéro échec) avant tout push sur main.
Les bibliothèques PDF (jsPDF, html2canvas) viennent d'un CDN non joignable depuis le bac à sable :
les tests les simulent et enregistrent chaque page produite.
