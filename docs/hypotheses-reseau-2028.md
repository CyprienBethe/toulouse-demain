# Hypothèses du réseau 2028 (GTFS « futur »)

Auteur : data engineer transport · 14 octobre 2026 · mis à jour le même jour après le premier passage CI et la revue QA (`docs/qa/sprint-0-revue.md`) · statut : **à valider par Cyprien**

Ce document justifie chaque valeur de `data/futur/parametres.yaml` et des CSV de stations. Il distingue les **faits** (chiffre public, source citée) des **hypothèses** (estimation de l'équipe, avec son raisonnement). Toutes les pages ont été consultées le 14/10/2026 ; la liste est en fin de document. Les sources [S8] à [S10] ont été relues par la QA, pas par le data engineer.

Règles de modélisation reprises de `docs/equipe/README.md` : les lignes futures roulent sur le calendrier actuel, le réseau de bus reste celui d'aujourd'hui, aucune donnée n'est inventée.

## 1. Ce qui est simulé

| Ligne | Parcours | Stations | Longueur | Mise en service annoncée |
| --- | --- | --- | --- | --- |
| C | Colomiers - Gare ↔ Labège - Gare | 21 [S1][S3][S8] | 27 km [S1][S3] | fin 2028 [S1][S3] |
| B prolongée | Ramonville ↔ Labège Madron | 2 nouvelles + Ramonville [S2][S9] | 2,7 km [S2] | septembre 2027 [S9] (annonce de mars 2024, non redonnée depuis : à revérifier à chaque sprint) |

**Décision de Cyprien (14/10/2026) : la B prolongée roule en rames directes.** Tisséo annonce que « la ligne B actuelle sera prolongée » et que Labège Madron (ex-INP) devient son nouveau terminus [S10]. Avec le GTFS Tisséo, toute la ligne B est recopiée dans le flux futur, et une partie de ses rames continue jusqu'à Labège Madron (§4.5). La navette Ramonville ↔ Labège Madron ne sert plus qu'en mode autonome, sans GTFS Tisséo (tests, poste local).

## 2. Stations : noms et positions

### 2.1 Ordre et noms

L'ordre et les noms viennent de la liste officielle de Tisséo du 10/05/2023 [S8]. Elle est recoupée avec Wikipédia [S4][S5] et les deux pages de Toulouse Métropole [S3][S6]. Quand la page Métropole « La Ligne C embarque ses voyageurs fin 2028 » [S3] donne une forme plus longue pour une station multimodale, c'est elle qui est retenue.

**Stations renommées depuis les documents Tisséo de 2022 :**

| Nom en 2022 [S1][S2] | Nom actuel (officiel) | Source du nom actuel | Remarque |
| --- | --- | --- | --- |
| Institut National Polytechnique (INP) | **Labège Madron** | [S6][S8][S10] | station commune B et C |
| Labège La Cadène | **Labège - Gare** | [S3][S6][S8] | la page [S3] emploie encore les deux noms |
| Labège Enova | **Diagora** | [S6][S8] | nom officiel ; seule l'équivalence avec « Labège Enova » est une déduction, sans effet sur le GTFS |
| Parc Technologique du Canal | **Parc du Canal** | [S6][S9] | nom officiel |

**Autres points sur les noms :**
- « Aerospace Campus » (station 18) est un nom officiel [S8].
- « Ponts-Jumeaux » prend un trait d'union, comme dans la liste Tisséo [S8].
- « Colomiers - Gare », « La Vache Gare - Le Grand marché » et « Montaudran Gare - Piste des Géants » suivent [S3] ; Tisséo écrit « Colomiers Gare », « La Vache », « Montaudran Gare » [S8].
- La liaison TER Arènes – Colomiers a longtemps porté le nom « ligne C » (« ex-ligne C » sur Wikipédia [S4]). Il reste à vérifier dans les GTFS Tisséo et SNCF qu'aucune ligne actuelle ne porte encore `route_short_name = C` (tâche QA).
- Les communes marquées « à confirmer » dans le CSV ne sont données par aucune source consultée.

### 2.2 Coordonnées

**Dans les CSV : aucune** (24 lignes, soit 23 stations distinctes, toutes vides et signalées). Depuis l'espace de travail, aucune source de coordonnées n'est joignable (Overpass, API OSM, Nominatim… refusent l'accès par robots.txt).

**En CI**, `scripts/extract_futur_osm.py` lit l'extrait OSM. Au premier passage (14/10/2026), il a rapproché les 24 lignes, mais **deux rapprochements étaient faux** : Raisin à 14 km au sud, vers Labège, et Ormeau sur un nœud « Bel Air » de Colomiers (noté 1,00 grâce à un autre nom du nœud). Le tri gardait le premier objet lu à égalité. Le script applique désormais ces garde-fous :

1. **Nom** : la note de 1,00 est réservée au même nom `name` (accents, casse et ponctuation ignorés). Un rapprochement par une autre clé (`alt_name`, `old_name`…) vaut au plus 0,95. Un objet existant doit avoir le même nom ; un objet en construction est accepté dès 0,85.
2. **Préférence** : d'abord les objets en construction (`construction*`), puis le candidat le plus proche du tracé en construction, puis, sans tracé à proximité, le plus proche des stations voisines.
3. **Contrôle géographique** : un choix est rejeté si la distance à vol d'oiseau jusqu'à la station précédente ou suivante sort de **[300 m ; 3,5 km]** (3,5 km par station manquante entre les deux), ou s'il crée un détour : d(précédente, x) + d(x, suivante) > 2,5 × d(précédente, suivante) + 500 m. Ce seuil a été calé sur les 19 stations bien placées au premier passage : distances de 811 m à 3 091 m, détour maximal de 2,13 à Ponts-Jumeaux. Le candidat suivant est alors essayé. **S'il n'en reste aucun, la station est manquante**, jamais remplacée par un faux positif. Le rapport `rapport_osm.md` liste chaque rejet avec sa raison.

Précision indiquée par le script : « station exacte » pour un objet en construction, pour un arrêt de même nom situé à moins de 30 m du tracé en construction, ou pour la même station (Ramonville) ; « approximative » sinon, avec la distance au tracé.

Le script de construction prend les positions dans cet ordre : CSV, puis extraction OSM, puis arrêt Tisséo de référence (La Vache, François Verdier, Matabiau Gare via Marengo - SNCF : approximatives). S'il reste une station sans position, la construction **s'arrête** (code 2). Elle n'interpole jamais.

## 3. Temps entre stations

### 3.1 Temps d'arrêt en station — HYPOTHÈSE

**20 s** par station intermédiaire. Aucune source publique n'a été trouvée. 20 s est un ordre de grandeur courant pour un métro automatique ; ce temps est compris dans les temps officiels de bout en bout (il ne les allonge pas).

### 3.2 Méthode

Les temps officiels servent de **points de calage**. Entre deux points de calage, on retire les arrêts en station, puis le temps de roulage restant est **réparti au prorata de la distance** de chaque interstation :

```
temps de roulage du segment = temps officiel du segment − (nombre d'arrêts dans le segment × 20 s)
temps de l'interstation i   = temps de roulage du segment × distance(i) / distance totale du segment
```

Les distances sont mesurées le long du tracé OSM quand il existe, sinon en ligne droite entre stations.

### 3.3 Ligne C

| Donnée | Valeur | Statut |
| --- | --- | --- |
| Colomiers Gare → Labège (terminus) | 37 min | FAIT [S3] |
| Labège → gare Matabiau | 20 min | FAIT [S1][S2] (2022) |
| Colomiers → Matabiau | 37 − 20 = **17 min** | HYPOTHÈSE déduite : on suppose compatibles deux chiffres de 2022 et de 2026, peut-être arrondis |
| Vitesse commerciale | > 40 km/h | FAIT [S1] |
| Vitesse maximale | 80 km/h | FAIT [S1] |

Calcul (temps cumulés à l'arrivée en station) :

| Sens | Segment | Temps officiel | Arrêts comptés | Temps de roulage |
| --- | --- | --- | --- | --- |
| Colomiers → Labège | Colomiers - Gare → Matabiau Gare (11 interstations) | 1 020 s | 10 (stations 2 à 11) | **820 s** |
| Colomiers → Labège | Matabiau Gare → Labège - Gare (9 interstations) | 1 200 s | 9 (Matabiau + stations 13 à 20) | **1 020 s** |
| Labège → Colomiers | Labège - Gare → Matabiau Gare | 1 200 s | 8 (stations 20 à 13) | **1 040 s** |
| Labège → Colomiers | Matabiau Gare → Colomiers - Gare | 1 020 s | 11 (Matabiau + stations 11 à 2) | **800 s** |

Le temps d'arrêt à Matabiau est compté dans le segment qui en repart. Cela crée une **asymétrie de 20 s** (un temps d'arrêt) selon le sens. De Labège à Matabiau, on retrouve exactement les 20 min officielles. Dans l'autre sens, Matabiau → Labège prend 19 min 40 entre le départ et l'arrivée. Les 37 min de bout en bout sont respectées dans les deux sens.

Contrôles de cohérence :
- vitesse commerciale = 27 km / 37 min = **43,8 km/h**, compatible avec « > 40 km/h » [S1] ;
- vitesse moyenne en roulage = 27 000 m / 1 840 s = **52,8 km/h**, sous la vitesse maximale de 80 km/h [S1] ;
- interstation moyenne = 27 km / 20 = **1,35 km**.

Les temps de chaque interstation dépendent des positions : ils sont calculés à la construction et publiés dans `build/gtfs/futur-rapport.md`.

### 3.4 Ligne B prolongée

| Donnée | Valeur | Statut |
| --- | --- | --- |
| Ramonville → Labège Madron | « estimé entre 3 et 3 min 30 » | FAIT [S10] (les PDF de 2022 disaient « 3 min 30 minimum » [S1][S2]) |
| Longueur | 2,7 km (500 m en tunnel, 2,2 km en viaduc) | FAIT [S2] |
| Voie unique entre Parc du Canal et Labège Madron | — | FAIT [S10], non modélisée (§4.5) |

On retient **3 min 30**, le haut de la fourchette actuelle, soit un choix prudent. Temps de roulage = 210 − 1 × 20 = **190 s** (un arrêt, à Parc du Canal). Vitesse moyenne en roulage : 2 700 / 190 = 51 km/h ; vitesse commerciale : 46 km/h. Dans une rame directe, s'ajoute l'arrêt de 20 s à Ramonville, qui devient une station intermédiaire.

## 4. Fréquences et amplitude

### 4.1 Intervalle en heure de pointe — FAIT

| Ligne | Intervalle de pointe | Source |
| --- | --- | --- |
| C | **3 min 25** (205 s) « à la mise en service » | [S1] |
| B prolongée (au-delà de Ramonville) | **5 min** (300 s) | [S1][S2] |

### 4.2 Heures creuses, soirée, week-end — HYPOTHÈSE

Aucune valeur officielle n'a été trouvée. Principe : les lignes futures suivent le **même rythme que la ligne B actuelle**. À chaque construction en CI, le script mesure dans le GTFS Tisséo l'intervalle médian de la ligne B par période (un mardi, un samedi et un dimanche représentatifs). Il applique ensuite à l'intervalle de pointe officiel le rapport `intervalle B de la période / intervalle B en pointe`. Le résultat n'est jamais plus fréquent qu'en pointe.

Sans GTFS Tisséo, des coefficients **provisoires et non sourcés** s'appliquent (mode autonome uniquement) :

| Période | Coefficient provisoire | Ligne C | B prolongée |
| --- | --- | --- | --- |
| pointe | 1 | 3 min 25 | 5 min |
| creuse | 1,5 | 5 min 08 | 7 min 30 |
| soirée | 2 | 6 min 50 | 10 min |
| samedi | 1,5 | 5 min 08 | 7 min 30 |
| dimanche | 2 | 6 min 50 | 10 min |

### 4.3 Découpage de la journée — HYPOTHÈSE

Pointe 7 h – 9 h et 16 h 30 – 19 h en semaine ; soirée après 20 h 30 ; creuse le reste du temps. Le samedi et le dimanche ont chacun un intervalle unique jusqu'à 20 h 30, puis l'intervalle de soirée. Ce découpage se corrige dans `parametres.yaml` sans toucher au code.

### 4.4 Amplitude horaire

| Jours | Premier départ | Dernier départ | Statut |
| --- | --- | --- | --- |
| lundi à mercredi | 5 h 15 | minuit | dernier départ : FAIT, presse 2020 [S7] ; premier départ : HYPOTHÈSE |
| jeudi, vendredi, samedi | 5 h 15 | 3 h | FAIT, presse 2020 [S7] |
| dimanche et jours fériés | 5 h 15 | minuit | idem lundi |

La ligne C reprend l'amplitude de la ligne B **mesurée dans le GTFS Tisséo**, nuits codées après minuit comprises. Les valeurs ci-dessus ne servent que sans GTFS Tisséo. La ligne B recopiée garde, elle, ses propres horaires.

### 4.5 Ligne B en rames directes — HYPOTHÈSE de répartition

**Modèle (avec `--tisseo-gtfs`) :**
1. Toutes les courses de la ligne B du GTFS Tisséo sont recopiées dans le flux futur, sur une route « B » (`FUT_B`), avec les mêmes arrêts (mêmes positions), les mêmes horaires et les mêmes tracés.
2. Parmi les rames qui arrivent à Ramonville, certaines **continuent** vers Parc du Canal et Labège Madron : arrêt de 20 s à Ramonville, puis les temps du §3.4. Parmi celles qui partent de Ramonville, certaines **viennent de** Labège Madron : leur départ de Ramonville reste l'horaire Tisséo, et le trajet depuis Labège est ajouté avant.
3. **Quelles rames ?** Tisséo ne publie pas la part des rames prolongées. Wikipédia écrit « 1 rame sur 4 », pour une configuration antérieure, sans que ce soit vérifiable sur une source primaire. On retient donc le nombre de rames qui donne **l'intervalle officiel de 5 min en pointe** sur le prolongement, et aux autres périodes 5 min × le coefficient du §4.2 (≈ 10 min en creuse si la B passe deux fois moins souvent qu'en pointe). Concrètement, on pose une grille régulière à cet intervalle et on prolonge, pour chaque créneau, la rame la plus proche. L'intervalle obtenu n'est donc régulier qu'à un intervalle de la ligne B près (par exemple 4 et 6 min en alternance pour une B toutes les 2 min). Quand la B passe moins souvent que l'intervalle visé (nuit), toutes ses rames sont prolongées. La grille repart après chaque trou de plus de 30 min.
4. Les jours qui ont le même ensemble de services Tisséo partagent le même choix. Si une course est prolongée certains jours et pas d'autres, elle est recopiée deux fois, chacune avec ses propres dates : une course ne roule jamais deux fois le même jour.
5. **Non modélisé** : la voie unique entre Parc du Canal et Labège Madron [S10] (à 5 min d'intervalle, deux rames de sens opposés peuvent s'y croiser en simulation). Le moteur ne vérifie pas ces conflits.
6. **Scénario 2028** : le script écrit `build/gtfs/scenario-2028.json` = `{"exclude_routes": ["tisseo:<route_id de la B>"]}` à côté du zip. Le scénario 2028 exclut la B Tisséo et utilise la B complète du flux futur ; le scénario actuel exclut tout le flux futur (`config/scenarios.json`).

Le rapport de construction donne le nombre de courses recopiées et prolongées et l'intervalle obtenu par période.

## 5. Calendrier

- **Avec le GTFS Tisséo** : même période de validité. Chaque date reçoit le type de jour de son jour de semaine. Les jours fériés sont détectés dans les données Tisséo : une date de semaine dont le nombre de courses de la ligne B ressemble à un dimanche roule comme un dimanche. La ligne B recopiée garde les services Tisséo (`FUT_TIS_<service>`), complétés si besoin par des services datés (§4.5, point 4).
- **Sans GTFS Tisséo** : calendrier autonome de 21 jours à partir de la date du jour, sans jours fériés.

## 6. Identifiants et correspondances

- **Identifiants** : tous préfixés `FUT_`. Ligne C : `FUT_C`, `FUT_C_<station>` ; ligne B recopiée : `FUT_B`, `FUT_TIS_<identifiant Tisséo>` (suffixe `_P` pour une course prolongée) ; navette du mode autonome : `FUT_B_EXT`. Le script vérifie qu'aucun identifiant n'entre en collision avec Tisséo. OTP charge le flux sous l'identifiant `futur`.
- **Stations** : une station parente par nom, un quai par ligne. Labège Madron a un quai C et un quai B sous la même station parente.
- **Correspondance interne** C ↔ B à Labège Madron : `transfers.txt`, **2 min** minimum (HYPOTHÈSE : deux lignes à des niveaux différents, sans plan de station publié).
- **Correspondances avec Tisséo et SNCF : on laisse la marche au moteur**, sans `transfers.txt`. Un `transfers.txt` ne peut citer que des arrêts du même flux, alors qu'OTP relie déjà tous les arrêts au réseau piéton OSM. Avec les rames directes, il n'y a plus de changement à Ramonville. Le rapport liste les arrêts Tisséo à moins de 400 m de chaque station future.

## 7. Tableau récapitulatif

| Élément | Valeur | Fait / hypothèse | Source |
| --- | --- | --- | --- |
| Ligne C : stations, ordre, longueur | 21 stations, 27 km | Fait | [S1][S3][S8] |
| Ligne C : Colomiers → Labège | 37 min | Fait | [S3] |
| Ligne C : Labège → Matabiau | 20 min | Fait (2022) | [S1][S2] |
| Ligne C : Colomiers → Matabiau | 17 min | Hypothèse (37 − 20) | §3.3 |
| Ligne C : intervalle de pointe | 3 min 25 | Fait | [S1] |
| B prolongée : stations, longueur | 2 nouvelles, 2,7 km | Fait | [S2][S9] |
| B prolongée : Ramonville → Labège Madron | 3 min 30 (haut de « 3 à 3 min 30 ») | Fait | [S10] |
| B prolongée : rames directes de la ligne B | toute la B recopiée, une partie prolongée | Fait (principe) [S10] ; décision de Cyprien | §4.5 |
| B prolongée : part des rames prolongées | celle qui donne 5 min en pointe | Hypothèse | §4.5 |
| B prolongée : intervalle de pointe | 5 min | Fait | [S1][S2] |
| Noms actuels | §2.1 | Fait | [S8][S3][S6] |
| Coordonnées des stations | extraction OSM en CI, avec garde-fous | Données OSM (ODbL) | §2.2 |
| Temps d'arrêt | 20 s | Hypothèse | §3.1 |
| Répartition des temps | au prorata des distances | Hypothèse (méthode) | §3.2 |
| Intervalles creuse, soirée, week-end | rapport mesuré sur la ligne B | Hypothèse | §4.2 |
| Découpage des périodes | 7-9 h, 16 h 30-19 h, après 20 h 30 | Hypothèse | §4.3 |
| Dernier métro (ligne C) | mesuré sur la ligne B (sinon minuit, 3 h du jeudi au samedi) | Fait (2020), recalé | [S7] |
| Correspondance C ↔ B à Labège Madron | 2 min | Hypothèse | §6 |
| Calendrier | celui de Tisséo, jours fériés en dimanche | Règle du projet | §5 |

## 8. Points à arbitrer par Cyprien

1. **Stations manquantes** : si les garde-fous laissent une station sans position au prochain passage CI, la saisir à la main depuis openstreetmap.org (source vérifiable). Le scénario 2028 reste bloqué tant qu'une station n'a pas de position.
2. **Part des rames B prolongées** : l'hypothèse actuelle (assez de rames pour 5 min en pointe) est à remplacer dès que Tisséo publie la grille réelle.
3. **Colomiers → Matabiau 17 min** : ce chiffre combine deux sources d'époques différentes. Faut-il garder ce point de calage, ou ne retenir que les 37 min de bout en bout ?
4. **Labège - Gare ou Labège La Cadène** pour le terminus (les deux figurent sur la page Métropole).

## 9. Mise en œuvre (pour l'architecte)

```bash
python -m pip install -r scripts/requirements.txt
# 1. positions et tracé depuis OSM (extrait découpé)
python scripts/extract_futur_osm.py --osm build/otp/osm/zone.osm.pbf --output-dir build/futur-osm
# 2. GTFS futur + scenario-2028.json, dans le dossier de --output
python scripts/build_gtfs_futur.py --tisseo-gtfs build/raw/tisseo.gtfs.zip --osm-dir build/futur-osm \
  --output build/gtfs/futur.gtfs.zip
```

Sorties (données dérivées sous ODbL) : `build/futur-osm/stations_osm.csv`, `traces_osm.geojson`, `rapport_osm.md` ; `build/gtfs/futur.gtfs.zip` (licence dans `feed_info.txt` et `attributions.txt`), `build/gtfs/scenario-2028.json`, `build/gtfs/futur-rapport.md`. Rien n'est versionné, puisque `build/` est ignoré. À l'ouverture réelle de la B prolongée, il suffit de retirer la ligne `B_EXT` de `parametres.yaml`.

## Sources (consultées le 14/10/2026)

- [S1] Tisséo Collectivités, démarrage des travaux de Labège, 15/02/2022 — https://tisseo-collectivites.fr/sites/default/files/media/downloads/lab-demarrage-tvx-metro-20220215.pdf
- [S2] Tisséo Collectivités, démarrage des travaux de la Connexion Ligne B à Ramonville, 09/02/2022 — https://tisseo-collectivites.fr/sites/default/files/media/downloads/ram_-_dmarrage_tvx_clb_-_2022_02_09_.pdf
- [S3] Toulouse Métropole, « La Ligne C embarque ses voyageurs fin 2028 » — https://metropole.toulouse.fr/mon-environnement/amenagement/3e-ligne-metro-ligne-C
- [S4] Wikipédia, « Ligne C du métro de Toulouse » — https://fr.wikipedia.org/wiki/Ligne_C_du_m%C3%A9tro_de_Toulouse
- [S5] Wikipedia, « List of Toulouse Metro stations » — https://en.wikipedia.org/wiki/List_of_Toulouse_Metro_stations
- [S6] Toulouse Métropole, « Chantier de la ligne C : où se trouvent les travaux ? » — https://metropole.toulouse.fr/actualites/chantier-de-la-ligne-c-ou-se-trouvent-les-travaux
- [S7] Le Journal toulousain, « Dernier métro à 3 h le jeudi », 29/08/2020 — https://lejournaltoulousain.fr/les-breves-du-jt/dernier-metro-3h-jeudi-86039
- [S8] Tisséo, « Les noms des futures stations de la ligne C », 10/05/2023 (relue par la QA) — https://www.projetsmetro.tisseo.fr/actualites/les-noms-des-futures-stations-de-la-ligne-c
- [S9] Tisséo Collectivités, chantiers ligne C, Connexion Ligne B, Ligne Aéroport Express, 25/03/2024 (relue par la QA) — https://tisseo-collectivites.fr/actualites/chantiers-ligne-c-connexion-ligne-b-ligne-aeroport-express-2
- [S10] Tisséo Collectivités, « Connexion Ligne B » (relue par la QA) — https://tisseo-collectivites.fr/connexion-ligne-b
- GTFS Tisséo (ODbL), recopié et mesuré à chaque construction : https://www.data.gouv.fr/datasets/tisseo-reseau-transport-urbain-toulousain

## Ce qu'il faut retenir

- Les chiffres officiels sont repris tels quels : 21 stations, 37 min de Colomiers à Labège, une rame toutes les 3 min 25 en pointe sur la C, et 5 min sur le prolongement de la B.
- La B prolongée est désormais un vrai prolongement : on garde toute la ligne B de Tisséo, et assez de rames continuent jusqu'à Labège Madron pour en avoir une toutes les 5 min en pointe. Cette répartition est une hypothèse, faute de grille publiée.
- Les positions des stations viennent d'OpenStreetMap. Deux erreurs du premier essai (Raisin, Ormeau) sont maintenant bloquées : une station mal placée est rejetée et signalée comme manquante plutôt que fausse.
- Il reste à trancher le calage à 17 min de Matabiau et le nom du terminus de Labège (§8).
