# Hypothèses du réseau 2028 (GTFS « futur »)

Auteur : data engineer transport · 14 octobre 2026 · statut : **à valider par Cyprien**

Ce document justifie chaque valeur de `data/futur/parametres.yaml` et des CSV de stations. Il distingue les **faits** (chiffre public, source citée) des **hypothèses** (estimation de l'équipe, avec son raisonnement). Toutes les pages ont été consultées le 14/10/2026 ; la liste est en fin de document.

Règles de modélisation reprises de `docs/equipe/README.md` : les lignes futures roulent sur le calendrier actuel, le réseau de bus reste celui d'aujourd'hui, aucune donnée n'est inventée.

## 1. Ce qui est simulé

| Ligne | Parcours | Stations | Longueur | Mise en service annoncée |
| --- | --- | --- | --- | --- |
| C | Colomiers - Gare ↔ Labège - Gare | 21 [S1][S3][S5] | 27 km [S1][S3] | fin 2028 [S1][S3] |
| B prolongée | Ramonville ↔ Labège Madron | 2 nouvelles + Ramonville [S2] | 2,7 km [S2] | septembre 2027 [S1][S2] |

La B prolongée est modélisée comme une **navette Ramonville ↔ Labège Madron** : la ligne B actuelle reste celle du GTFS Tisséo et le voyageur change à Ramonville (voir §6 et le point d'arbitrage n° 2).

## 2. Stations : noms et positions

### 2.1 Ordre et noms

L'ordre et les noms viennent de la liste de Wikipédia (en), qui cite les noms définitifs publiés par Tisséo [S5]. Elle est recoupée avec l'article francophone [S4] et les deux pages de Toulouse Métropole [S3][S6]. Quand la page Métropole « La Ligne C embarque ses voyageurs fin 2028 » [S3], source officielle la plus récente, donne une forme plus complète, c'est elle qui est retenue.

**Stations renommées depuis les documents Tisséo de 2022 :**

| Nom en 2022 [S1][S2] | Nom actuel | Source du nom actuel | Certitude |
| --- | --- | --- | --- |
| Institut National Polytechnique (INP) | **Labège Madron** | [S5][S6] | sûre (station commune B et C) |
| Labège La Cadène | **Labège - Gare** | [S3][S5][S6] | la page [S3] emploie encore les deux noms |
| Labège Enova | **Diagora** (probable) | [S5][S6] | déduction par élimination, à confirmer |
| Parc Technologique du Canal | **Parc du Canal** | [S6] | à confirmer |

**Autres points sur les noms :**
- « Aerospace Campus » (station 18) n'apparaît que sur la liste anglophone [S5] : nom à confirmer.
- « Colomiers - Gare », « La Vache Gare - Le Grand marché » et « Montaudran Gare - Piste des Géants » suivent [S3] ; d'autres sources écrivent « Colomiers Gare », « La Vache », « Montaudran Gare ».
- La liaison TER Arènes – Colomiers a longtemps porté le nom « ligne C ». Wikipédia la désigne aujourd'hui comme « ex-ligne C » [S4], mais il reste à vérifier dans les GTFS Tisséo et SNCF qu'aucune ligne actuelle ne porte encore `route_short_name = C` (tâche QA).
- Communes marquées « à confirmer » dans le CSV : aucune source consultée ne les donne explicitement. Saint-Martin-du-Touch est un quartier de Toulouse, mais la page chantier de la Métropole [S6] range la station dans le secteur Blagnac.

### 2.2 Coordonnées : état au 14/10/2026

| | Ligne C | B prolongée | Total |
| --- | --- | --- | --- |
| Station exacte (dans les CSV) | 0 | 0 | 0 |
| Approximative (dans les CSV) | 0 | 0 | 0 |
| **Manquante** (vide et signalée) | 21 | 3 (dont Ramonville) | **24 lignes**, soit 23 stations distinctes (Labège Madron est commune aux deux lignes) |

Aucune coordonnée vérifiable n'a pu être lue depuis l'espace de travail : l'API Overpass, l'API OpenStreetMap, Nominatim, Photon, OpenRailwayMap et l'open data de Toulouse Métropole refusent l'outil de lecture (robots.txt). Wikipédia ne donne pas de coordonnées pour ces stations. Les colonnes `lat` et `lon` restent donc **vides**, conformément à la règle « aucune donnée inventée ».

Le script de construction complète les positions dans cet ordre de priorité :
1. **CSV** : coordonnées saisies à la main depuis une source vérifiable ;
2. **OpenStreetMap** : `scripts/extract_futur_osm.py`, lancé en CI sur l'extrait Geofabrik, cherche les stations en construction de même nom. Il sort chaque position avec son objet OSM et sa précision, ainsi que le tracé en construction. Il n'a pas encore pu être lancé sur les vraies données : on ne sait pas combien de stations OSM cartographie ;
3. **GTFS Tisséo** (colonne `arret_tisseo_reference`) : Ramonville = **station exacte** (c'est la station existante). La Vache, François Verdier et Matabiau Gare (via Marengo - SNCF) = **approximatives** : on prend la position de la station existante voisine, et l'écart avec la future station n'est pas mesuré.

S'il reste une station sans position, la construction **s'arrête** (code 2) et liste les stations manquantes. Elle n'interpole jamais une position.

## 3. Temps entre stations

### 3.1 Temps d'arrêt en station — HYPOTHÈSE

**20 s** par station intermédiaire. Aucune source publique n'a été trouvée. 20 s est un ordre de grandeur courant pour un métro automatique ; ce temps est compris dans les temps officiels de bout en bout (il ne les allonge pas).

### 3.2 Méthode

Les temps officiels servent de **points de calage**. Entre deux points de calage, on retire les arrêts en station, puis le temps de roulage restant est **réparti au prorata de la distance** de chaque interstation :

```
temps de roulage du segment = temps officiel du segment − (nombre d'arrêts dans le segment × 20 s)
temps de l'interstation i   = temps de roulage du segment × distance(i) / distance totale du segment
```

Les distances sont mesurées le long du tracé OSM quand il existe, sinon en ligne droite entre stations. Un tracé en ligne droite sous-estime toutes les distances à peu près dans les mêmes proportions ; comme on ne garde que les rapports, l'effet sur les temps reste faible.

### 3.3 Ligne C

| Donnée | Valeur | Statut |
| --- | --- | --- |
| Colomiers Gare → Labège (terminus) | 37 min | FAIT [S3] |
| Labège → gare Matabiau | 20 min | FAIT [S1][S2] (2022) |
| Colomiers → Matabiau | 37 − 20 = **17 min** | HYPOTHÈSE déduite : on suppose les deux chiffres compatibles alors qu'ils datent de 2022 et 2026 et sont peut-être arrondis |
| Vitesse commerciale | > 40 km/h | FAIT [S1] |
| Vitesse maximale | 80 km/h | FAIT [S1] |

Calcul :

| Segment | Temps officiel | Arrêts comptés | Temps de roulage |
| --- | --- | --- | --- |
| Colomiers - Gare → Matabiau Gare (11 interstations) | 1 020 s | 10 (stations 2 à 11) | 1 020 − 200 = **820 s** |
| Matabiau Gare → Labège - Gare (9 interstations) | 1 200 s | 9 (Matabiau + stations 13 à 20) | 1 200 − 180 = **1 020 s** |
| **Ligne entière** | 2 220 s | 19 | **1 840 s** |

Contrôles de cohérence :
- vitesse commerciale = 27 km / 37 min = **43,8 km/h**, compatible avec « > 40 km/h » [S1] (Wikipédia cite 41 km/h [S4]) ;
- vitesse moyenne en roulage = 27 000 m / 1 840 s = **52,8 km/h**, sous la vitesse maximale de 80 km/h [S1] ;
- interstation moyenne = 27 km / 20 = **1,35 km**, cohérent avec « plus de 1 km » [S4].

Exemple : une interstation qui fait 10 % de la longueur du segment Matabiau → Labège reçoit 1 020 × 0,10 = 102 s de roulage. Les temps réels de chaque interstation sont calculés à la construction et publiés dans `build/gtfs/futur-rapport.md`, puisqu'ils dépendent des positions.

Dans le sens Labège → Colomiers, on retrouve exactement les 20 min officielles de Labège à Matabiau.

### 3.4 Ligne B prolongée

| Donnée | Valeur | Statut |
| --- | --- | --- |
| Ramonville → INP (Labège Madron) | 3 min 30 « minimum » | FAIT [S1][S2] |
| Longueur | 2,7 km (500 m en tunnel, 2,2 km en viaduc) | FAIT [S2] |

Temps de roulage = 210 − 1 × 20 = **190 s** (un arrêt, à Parc du Canal). Vitesse moyenne en roulage : 2 700 / 190 = 51 km/h ; vitesse commerciale : 46 km/h. Le chiffre officiel est un **minimum** : le retenir tel quel est optimiste (point d'arbitrage n° 3).

## 4. Fréquences et amplitude

### 4.1 Intervalle en heure de pointe — FAIT

| Ligne | Intervalle de pointe | Source |
| --- | --- | --- |
| C | **3 min 25** (205 s) « à la mise en service » | [S1] |
| B prolongée | **5 min** (300 s) | [S1][S2] |

### 4.2 Heures creuses, soirée, week-end — HYPOTHÈSE

Aucune valeur officielle n'a été trouvée. Principe : les lignes futures suivent le **même rythme que la ligne B actuelle**. À chaque construction en CI, le script mesure dans le GTFS Tisséo l'intervalle médian de la ligne B par période (un mardi, un samedi et un dimanche représentatifs), puis applique à l'intervalle de pointe officiel le rapport `intervalle B de la période / intervalle B en pointe`. Le résultat n'est jamais plus fréquent qu'en pointe.

Sans GTFS Tisséo, des coefficients **provisoires et non sourcés** s'appliquent. Ils ont été choisis pour donner moins de passages qu'en pointe, et ne servent qu'en mode autonome (tests, poste local) :

| Période | Coefficient provisoire | Ligne C | B prolongée |
| --- | --- | --- | --- |
| pointe | 1 | 3 min 25 | 5 min |
| creuse | 1,5 | 5 min 08 | 7 min 30 |
| soirée | 2 | 6 min 50 | 10 min |
| samedi | 1,5 | 5 min 08 | 7 min 30 |
| dimanche | 2 | 6 min 50 | 10 min |

Les coefficients mesurés et les intervalles retenus sont publiés dans le rapport de construction.

### 4.3 Découpage de la journée — HYPOTHÈSE

Pointe 7 h – 9 h et 16 h 30 – 19 h en semaine ; soirée après 20 h 30 ; creuse le reste du temps. Le samedi et le dimanche ont chacun un intervalle unique jusqu'à 20 h 30, puis l'intervalle de soirée. Ce découpage se corrige dans `parametres.yaml` sans toucher au code.

### 4.4 Amplitude horaire

| Jours | Premier départ | Dernier départ | Statut |
| --- | --- | --- | --- |
| lundi à mercredi | 5 h 15 | minuit | dernier départ : FAIT, presse 2020 « aux alentours de minuit » [S7] ; premier départ : HYPOTHÈSE |
| jeudi et vendredi | 5 h 15 | 3 h | FAIT, presse 2020 : métro jusqu'à 3 h le jeudi, le vendredi et le samedi [S7] |
| samedi | 5 h 15 | 3 h | idem |
| dimanche et jours fériés | 5 h 15 | minuit | idem lundi |

Les lignes futures reprennent l'amplitude de la ligne B **mesurée dans le GTFS Tisséo** (premier et dernier départ par type de jour, nuits codées après minuit comprises). Les valeurs ci-dessus ne servent que sans GTFS Tisséo ; elles datent de 2020 et sont peut-être périmées.

## 5. Calendrier

- **Avec le GTFS Tisséo** : même période de validité. Chaque date reçoit le type de jour de son jour de semaine. Les jours fériés sont détectés dans les données Tisséo : une date de semaine dont le nombre de courses de la ligne B ressemble à un dimanche roule comme un dimanche (exemple : un 11 novembre). Une date sans métro B n'a pas de service. Le résultat va dans `calendar.txt` + `calendar_dates.txt`.
- **Sans GTFS Tisséo** : calendrier autonome de 21 jours à partir de la date du jour, sans jours fériés.

## 6. Identifiants et correspondances

- **Identifiants** : tous préfixés `FUT_` (`FUT_C`, `FUT_B_EXT`, `FUT_STA_MATABIAU_GARE`, `FUT_C_LUNMER_0_0001`…). Avec le GTFS Tisséo, le script vérifie qu'aucun identifiant n'entre en collision et s'arrête sinon. OTP charge le flux sous l'identifiant `futur` (`otp/build-config.json`).
- **Stations** : une station parente par nom, un quai par ligne. Labège Madron a un quai C et un quai B sous la même station parente.
- **Correspondance interne** C ↔ B prolongée à Labège Madron : `transfers.txt`, **2 min** minimum (HYPOTHÈSE : deux lignes à des niveaux différents, viaduc et station C, sans plan de station publié).
- **Correspondances avec Tisséo et SNCF : on laisse la marche au moteur**, sans `transfers.txt`. Pourquoi :
  1. un `transfers.txt` ne peut citer que des arrêts du même flux ; OTP n'y résout pas un arrêt d'un autre flux ;
  2. OTP relie déjà tous les arrêts, tous flux confondus, au réseau piéton OSM et calcule lui-même les temps de marche. C'est le même mécanisme qui relie aujourd'hui Tisséo et SNCF ;
  3. la marche réelle (escaliers, traversées) est plus juste qu'un temps forfaitaire.

  Le rapport de construction liste, pour chaque station future, les arrêts Tisséo à moins de 400 m (Matabiau, Ramonville, La Vache…). Il signale toute correspondance attendue avec le métro ou le tram sans arrêt proche.

## 7. Tableau récapitulatif

| Élément | Valeur | Fait / hypothèse | Source |
| --- | --- | --- | --- |
| Ligne C : stations, ordre, longueur | 21 stations, 27 km | Fait | [S1][S3][S5] |
| Ligne C : Colomiers → Labège | 37 min | Fait | [S3] |
| Ligne C : Labège → Matabiau | 20 min | Fait (2022) | [S1][S2] |
| Ligne C : Colomiers → Matabiau | 17 min | Hypothèse (37 − 20) | §3.3 |
| Ligne C : intervalle de pointe | 3 min 25 | Fait | [S1] |
| B prolongée : stations, longueur | 2 nouvelles, 2,7 km | Fait | [S2] |
| B prolongée : Ramonville → Labège Madron | 3 min 30 (minimum) | Fait | [S1][S2] |
| B prolongée : intervalle de pointe | 5 min | Fait | [S1][S2] |
| Noms actuels (Labège Madron, Labège - Gare…) | §2.1 | Fait, sauf Diagora, Parc du Canal et Aerospace Campus (à confirmer) | [S3][S5][S6] |
| Coordonnées des stations | aucune dans les CSV | Manquantes, à extraire d'OSM en CI | §2.2 |
| Temps d'arrêt | 20 s | Hypothèse | §3.1 |
| Répartition des temps | au prorata des distances | Hypothèse (méthode) | §3.2 |
| Intervalles creuse, soirée, week-end | rapport mesuré sur la ligne B | Hypothèse | §4.2 |
| Découpage des périodes | 7-9 h, 16 h 30-19 h, après 20 h 30 | Hypothèse | §4.3 |
| Dernier métro | minuit, 3 h du jeudi au samedi | Fait (2020), recalé sur la ligne B | [S7] |
| Premier départ | ligne B mesurée (sinon 5 h 15) | Hypothèse | §4.4 |
| Correspondance C ↔ B à Labège Madron | 2 min | Hypothèse | §6 |
| Calendrier | celui de Tisséo, jours fériés en dimanche | Règle du projet | §5 |

## 8. Points à arbitrer par Cyprien

1. **Coordonnées** : si l'extraction OSM en CI ne trouve pas toutes les stations, saisir à la main les manquantes depuis openstreetmap.org (environ 15 minutes, source vérifiable). Le scénario 2028 reste bloqué tant qu'une station n'a pas de position.
2. **B prolongée en navette** (choix actuel, simple : une correspondance à Ramonville en plus) ou **ligne B complète prolongée** (plus réaliste, mais il faut exclure la ligne B Tisséo du scénario 2028, comme le prévoit `config/scenarios.json`). Tisséo n'a publié aucune information sur la part des rames B qui iront jusqu'à Labège.
3. **3 min 30 « minimum »** entre Ramonville et Labège Madron : retenu tel quel, donc optimiste. Faut-il ajouter une marge ?
4. **Noms à confirmer** : Diagora, Parc du Canal, Aerospace Campus, et Labège - Gare ou Labège La Cadène.
5. **Colomiers → Matabiau 17 min** : ce chiffre combine deux sources d'époques différentes. Garder ce point de calage, ou ne retenir que les 37 min de bout en bout ?

## 9. Mise en œuvre (pour l'architecte)

```bash
python -m pip install -r scripts/requirements.txt
# 1. positions et tracé depuis OSM (extrait régional ou découpé)
python scripts/extract_futur_osm.py --osm build/raw/midi-pyrenees-latest.osm.pbf --output-dir build/futur-osm
# 2. GTFS futur (lit build/futur-osm s'il existe)
python scripts/build_gtfs_futur.py --tisseo-gtfs build/raw/tisseo.gtfs.zip --output build/gtfs/futur.gtfs.zip
```

L'étape 1 est nécessaire tant que les CSV n'ont pas de coordonnées. Les sorties sont des données dérivées sous ODbL : `build/futur-osm/*.csv|geojson|md`, `build/gtfs/futur.gtfs.zip` (licence dans `feed_info.txt` et `attributions.txt`) et `build/gtfs/futur-rapport.md`. Rien n'est versionné, puisque `build/` est ignoré. À l'ouverture réelle de la B prolongée, il suffit de retirer la ligne `B_EXT` de `parametres.yaml`.

## Sources (consultées le 14/10/2026)

- [S1] Tisséo Collectivités, démarrage des travaux de Labège, 15/02/2022 — https://tisseo-collectivites.fr/sites/default/files/media/downloads/lab-demarrage-tvx-metro-20220215.pdf
- [S2] Tisséo Collectivités, démarrage des travaux de la Connexion Ligne B à Ramonville, 09/02/2022 — https://tisseo-collectivites.fr/sites/default/files/media/downloads/ram_-_dmarrage_tvx_clb_-_2022_02_09_.pdf
- [S3] Toulouse Métropole, « La Ligne C embarque ses voyageurs fin 2028 » — https://metropole.toulouse.fr/mon-environnement/amenagement/3e-ligne-metro-ligne-C (l'adresse metropole.toulouse.fr/3e-ligne affichait une page de maintenance)
- [S4] Wikipédia, « Ligne C du métro de Toulouse » — https://fr.wikipedia.org/wiki/Ligne_C_du_m%C3%A9tro_de_Toulouse
- [S5] Wikipedia, « List of Toulouse Metro stations » (cite Tisséo et actu.fr, 2023) — https://en.wikipedia.org/wiki/List_of_Toulouse_Metro_stations
- [S6] Toulouse Métropole, « Chantier de la ligne C : où se trouvent les travaux ? » — https://metropole.toulouse.fr/actualites/chantier-de-la-ligne-c-ou-se-trouvent-les-travaux
- [S7] Le Journal toulousain, « Dernier métro à 3 h le jeudi », 29/08/2020, modifié le 24/03/2023 — https://lejournaltoulousain.fr/les-breves-du-jt/dernier-metro-3h-jeudi-86039
- GTFS Tisséo (ODbL), mesuré à chaque construction : https://www.data.gouv.fr/datasets/tisseo-reseau-transport-urbain-toulousain

## Ce qu'il faut retenir

- Les chiffres officiels sont repris tels quels : 21 stations, 37 min de Colomiers à Labège, une rame toutes les 3 min 25 en pointe sur la C et toutes les 5 min sur la B prolongée.
- Le reste (heures creuses, soirées, week-end) copie le rythme de la ligne B actuelle, mesuré automatiquement dans les données Tisséo : c'est une hypothèse, et elle est affichée comme telle.
- Aucune position de station n'a encore pu être vérifiée depuis notre espace de travail. Elles seront lues dans OpenStreetMap par la CI, et sans position le scénario 2028 ne se construit pas : on préfère bloquer que deviner.
- Quatre noms de stations et la façon de modéliser la B prolongée restent à trancher (§8).
