# Hypothèses du réseau 2028 (GTFS « futur »)

Auteur : data engineer transport · 14 octobre 2026 · mis à jour le même jour après le premier passage CI et la revue QA (`docs/qa/sprint-0-revue.md`), puis le 15 octobre 2026 (Ligne Aéroport, §7 ; haltes TER, §8) · statut : **à valider par Cyprien**

Ce document justifie chaque valeur de `data/futur/parametres.yaml` et des CSV de stations. Il distingue les **faits** (chiffre public, source citée) des **hypothèses** (estimation de l'équipe, avec son raisonnement). Les pages [S1] à [S10] ont été consultées le 14/10/2026, les pages [S11] à [S21] le 15/10/2026 ; la liste est en fin de document. Les sources [S8] à [S10] ont été relues par la QA, pas par le data engineer.

Règles de modélisation reprises de `docs/equipe/README.md` : les lignes futures roulent sur le calendrier actuel, le réseau de bus reste celui d'aujourd'hui, aucune donnée n'est inventée.

## 1. Ce qui est simulé

| Ligne | Parcours | Stations | Longueur | Mise en service annoncée |
| --- | --- | --- | --- | --- |
| C | Colomiers - Gare ↔ Labège - Gare | 21 [S1][S3][S8] | 27 km [S1][S3] | fin 2028 [S1][S3] |
| B prolongée | Ramonville ↔ Labège Madron | 2 nouvelles + Ramonville [S2][S9] | 2,7 km [S2] | septembre 2027 [S9] (annonce de mars 2024, non redonnée depuis : à revérifier à chaque sprint) |
| Ligne Aéroport (tram) | Blagnac ↔ Aéroport | 2 [S9][S11] | 2,5 km [S11][S12] | début 2027 visé [S11] (§7) |

**Retrait de la navette Aéroport en 2028** (décision de Cyprien, 15/10/2026) : la ligne Tisséo `AERO` est exclue du scénario 2028, remplacée par la Ligne Aéroport (§7.5).

**Haltes TER prévisionnelles** (décision de Cyprien, 15/10/2026) : Route de Launaguet (réouverture annoncée à l'automne 2026) et Labège-La Cadène (fin 2028), insérées dans les trains SNCF actuels (§8).

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

**Dans les CSV : aucune** (26 lignes, soit 24 stations distinctes, toutes vides et signalées ; Blagnac est commune à la ligne C et à la Ligne Aéroport). Depuis l'espace de travail, aucune source de coordonnées n'est joignable (Overpass, API OSM, Nominatim… refusent l'accès par robots.txt).

**En CI**, `scripts/extract_futur_osm.py` lit l'extrait OSM. Au premier passage (14/10/2026), il a rapproché les 24 lignes, mais **deux rapprochements étaient faux** : Raisin à 14 km au sud, vers Labège, et Ormeau sur un nœud « Bel Air » de Colomiers (noté 1,00 grâce à un autre nom du nœud). Le tri gardait le premier objet lu à égalité. Le script applique désormais ces garde-fous :

1. **Nom** : la note de 1,00 est réservée au même nom `name` (accents, casse et ponctuation ignorés). Un rapprochement par une autre clé (`alt_name`, `old_name`…) vaut au plus 0,95. Un objet existant doit avoir le même nom ; un objet en construction est accepté dès 0,85.
2. **Préférence** : d'abord les objets en construction (`construction*`), puis le candidat le plus proche du tracé en construction, puis, sans tracé à proximité, le plus proche des stations voisines.
3. **Contrôle géographique** : un choix est rejeté si la distance à vol d'oiseau jusqu'à la station précédente ou suivante sort de **[300 m ; 3,5 km]** (3,5 km par station manquante entre les deux), ou s'il crée un détour : d(précédente, x) + d(x, suivante) > 2,5 × d(précédente, suivante) + 500 m. Ce seuil a été calé sur les 19 stations bien placées au premier passage : distances de 811 m à 3 091 m, détour maximal de 2,13 à Ponts-Jumeaux. Le candidat suivant est alors essayé. **S'il n'en reste aucun, la station est manquante**, jamais remplacée par un faux positif. Le rapport `rapport_osm.md` liste chaque rejet avec sa raison.

Pour une ligne de tram (Ligne Aéroport, §7), les arrêts de tram (`railway=tram_stop`) sont aussi candidats, et le « tracé » est la voie de tram existante ou en construction (`railway=tram`), puisque la ligne reprend l'ancienne branche du T2.

Précision indiquée par le script : « station exacte » pour un objet en construction, pour un arrêt de même nom situé à moins de 30 m du tracé en construction, ou pour la même station (Ramonville) ; « approximative » sinon, avec la distance au tracé.

Le script de construction prend les positions dans cet ordre : CSV, puis extraction OSM, puis arrêt Tisséo de référence (La Vache, François Verdier, Matabiau Gare via Marengo - SNCF, Aéroport via l'arrêt Tisséo « Aéroport » : approximatives). S'il reste une station sans position, la construction **s'arrête** (code 2). Elle n'interpole jamais.

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
| Ligne Aéroport | **5 min** (300 s) | [S11][S12][S14] (§7.3) |

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
6. **Scénario 2028** : le script écrit `build/gtfs/scenario-2028.json` = `{"exclude_routes": ["tisseo:<route_id de la B>", …]}` à côté du zip (la liste contient aussi les lignes Tisséo remplacées du §7.5, comme la navette Aéroport). Le scénario 2028 exclut la B Tisséo et utilise la B complète du flux futur ; le scénario actuel exclut tout le flux futur (`config/scenarios.json`).

Le rapport de construction donne le nombre de courses recopiées et prolongées et l'intervalle obtenu par période.

## 5. Calendrier

- **Avec le GTFS Tisséo** : même période de validité. Chaque date reçoit le type de jour de son jour de semaine. Les jours fériés sont détectés dans les données Tisséo : une date de semaine dont le nombre de courses de la ligne B ressemble à un dimanche roule comme un dimanche. La ligne B recopiée garde les services Tisséo (`FUT_TIS_<service>`), complétés si besoin par des services datés (§4.5, point 4).
- **Sans GTFS Tisséo** : calendrier autonome de 21 jours à partir de la date du jour, sans jours fériés.

## 6. Identifiants et correspondances

- **Identifiants** : tous préfixés `FUT_`. Ligne C : `FUT_C`, `FUT_C_<station>` ; ligne B recopiée : `FUT_B`, `FUT_TIS_<identifiant Tisséo>` (suffixe `_P` pour une course prolongée) ; navette du mode autonome : `FUT_B_EXT` ; Ligne Aéroport : `FUT_AEROPORT`, `FUT_AEROPORT_<station>`. Le script vérifie qu'aucun identifiant n'entre en collision avec Tisséo. OTP charge le flux sous l'identifiant `futur`.
- **Stations** : une station parente par nom, un quai par ligne. Labège Madron a un quai C et un quai B sous la même station parente ; Blagnac, un quai C et un quai Ligne Aéroport.
- **Correspondances internes** C ↔ B à Labège Madron et C ↔ Ligne Aéroport à Blagnac : `transfers.txt`, **2 min** minimum (HYPOTHÈSE : deux lignes à des niveaux différents, sans plan de station publié).
- **Correspondances avec Tisséo et SNCF : on laisse la marche au moteur**, sans `transfers.txt`. Un `transfers.txt` ne peut citer que des arrêts du même flux, alors qu'OTP relie déjà tous les arrêts au réseau piéton OSM. Avec les rames directes, il n'y a plus de changement à Ramonville. Le rapport liste les arrêts Tisséo à moins de 400 m de chaque station future ; c'est ainsi qu'est traitée la correspondance avec le T1 à Blagnac (§7.4).

## 7. Ligne Aéroport (tram)

Ajoutée le 15/10/2026. **Décisions de Cyprien (15/10/2026)** : ajouter la Ligne Aéroport au scénario 2028, et **retirer la navette Aéroport** de ce scénario. Raison : la ligne C ne dessert pas l'aérogare ; sans la Ligne Aéroport, Capitole → Aéroport donnait en 2028 exactement les trajets d'aujourd'hui (navette « BUS AERO », rapport CI du 15/10/2026 [R1]).

### 7.1 Ce qui est simulé

| Donnée | Valeur | Statut |
| --- | --- | --- |
| Mode | tram (`route_type` 0) ; les autres lignes futures sont des métros (1) | FAIT : le tram reprend l'ancienne branche du T2 [S11][S12] |
| Longueur | 2,5 km entre le pôle de Jean-Maga et l'aéroport | FAIT [S11][S12] (2 375 m pour l'ancienne branche, selon Wikipédia [S15]) |
| Stations | **Blagnac** (pôle d'échanges du rond-point Jean Maga) → **Aéroport** | FAIT pour les deux terminus [S9][S11][S12] ; arrêts intermédiaires : voir §7.6 |
| Nom de la station du pôle | « Blagnac », celui de la station de la ligne C | FAIT : Tisséo, 25/03/2024 [S9] (« station de métro ligne C “Blagnac” […] au niveau du rond-point de Jean Maga ») ; Tisséo Ingénierie [S12] (« La station “Blagnac” jouera un rôle central » pour la correspondance Ligne Aéroport, ligne C, T1). La presse parle du « pôle d'échanges de Jean-Maga » [S11]. Le nom du CSV de la ligne C est donc **confirmé**. |
| Nom de la station terminus | « Aéroport », nom de l'ancien terminus du T2 [S15][S16] | HYPOTHÈSE : nom non encore publié pour la nouvelle ligne |
| Ouverture | visée « début de 2027 » par Tisséo (d'après La Dépêche, citée par [S11]) ; Toulouse Métropole annonce encore « fin 2026 » [S11] ; « décembre 2026 » sur la page de Tisséo Ingénierie, modifiée le 13/10/2025 [S12] | FAIT, date incertaine |

La Ligne Aéroport ouvrira avant 2028. Règle 4 du projet (`docs/equipe/README.md`) : à son ouverture réelle, elle passera dans le réseau actuel (GTFS Tisséo) et sortira du flux futur (§7.6).

### 7.2 Temps de parcours — FAIT

| Donnée | Valeur | Source |
| --- | --- | --- |
| Blagnac → Aéroport | **7 min** | [S9] (« en 7 minutes depuis la future station de la ligne C BLAGNAC ») ; [S11] (« environ sept minutes de trajet entre Jean-Maga et l'aérogare ») ; [S12] |
| Matabiau → aéroport avec la ligne C | 22 min | [S9][S11] (contrôle de cohérence, pas un point de calage) |

On retient 7 min dans les deux sens (`points_de_calage`). Wikipédia donne 6 min [S15], d'après une ancienne page du T2 : écarté, les sources officielles et la presse de 2026 disent 7 min. Une seule interstation, donc aucun temps d'arrêt intermédiaire. Vitesse commerciale : 2,5 km / 7 min ≈ 21 km/h ; la longueur réelle du tracé et la vitesse figurent dans le rapport de construction.

Contrôle de cohérence avec les 22 min annoncées : temps de la ligne C de Matabiau Gare à Blagnac (dans `futur-rapport.md`) + correspondance de 2 min (§7.4) + attente du tram (0 à 5 min en pointe) + 7 min. À relire dans le rapport CI ; non vérifié ici.

### 7.3 Fréquence et amplitude

| Donnée | Valeur | Statut |
| --- | --- | --- |
| Intervalle de pointe | **5 min** (300 s) | FAIT : « Tisséo prévoit à terme un tram toutes les cinq minutes » [S11] ; « Airport line frequency: in 2026, one tram every 5min » [S14] ; « un train toutes les 5 minutes » en heure de pointe [S12] |
| Heures creuses, soirée, week-end | 5 min × les coefficients du §4.2 (mesurés sur la ligne B) | HYPOTHÈSE : aucun chiffre publié ; un tram ne suit pas forcément le rythme d'un métro |
| Premier et dernier départ | ceux de la ligne B mesurés dans le GTFS Tisséo (§4.4) | HYPOTHÈSE : aucune amplitude publiée pour la Ligne Aéroport |

### 7.4 Correspondances, nom court et couleur

- **Ligne C ↔ Ligne Aéroport à Blagnac** : même station parente (`FUT_STA_BLAGNAC`), un quai par ligne, `transfers.txt` avec **2 min** minimum. HYPOTHÈSE, comme à Labège Madron : aucun plan de la station publié. Le chiffre de 22 min (§7.2) servira de contrôle.
- **T1 ↔ Ligne Aéroport** : le mécanisme existant (§6) : la marche est laissée au moteur, et le rapport liste les arrêts Tisséo à moins de 400 m de la station Blagnac (avertissement s'il n'y en a aucun, puisque le CSV annonce « Tram T1 »). Tisséo crée une nouvelle station de tram « Blagnac » entre Ancely et Servanty Airbus [S9]. Si elle n'est pas encore dans le GTFS Tisséo, l'arrêt du T1 le plus proche peut être plus loin : **à confirmer par le rapport CI**.
- **Nom court** (`route_short_name`) : « Aéroport » ; le site affiche « Tram Aéroport ». HYPOTHÈSE : Tisséo emploie « Ligne Aéroport » et n'a pas publié d'indice de ligne.
- **Couleur** : lavande `#B39DDB`, texte `#16304F` (contraste 5,6:1). HYPOTHÈSE, couleur provisoire de l'équipe : aucune couleur de ligne officielle n'a été trouvée. Elle suit la charte (`docs/ux/parcours.md`, section 4 : texte blanc ou `#16304F` à 4,5:1 au moins, sans assombrir) et se distingue des lignes futures (C `#5BBF8A`, B `#F2C230`), des couleurs de l'interface (pastel `#24476F`, brique `#A8473C`) et de la navette Aéroport (`#E46809` dans le GTFS Tisséo [R1]). Un test vérifie que chaque ligne future a sa propre couleur et un contraste suffisant.

### 7.5 Retrait de la navette Aéroport — décision de Cyprien (15/10/2026)

**Ce qui est retiré.** La navette Aéroport du GTFS Tisséo : `route_short_name` **`AERO`**, `route_long_name` « Navette Aéroport », `route_id` `line:99` (`tisseo:line:99` dans OTP), mode bus. Source : la réponse brute d'OTP au trajet Capitole → Aéroport, publiée par le CI le 15/10/2026 [R1]. Aujourd'hui, elle passe toutes les 15 min, 7 jours sur 7, et met environ 25 min depuis le centre-ville [S13][S14].

**Statut.** Aucune source lue n'annonce la suppression de la navette à l'ouverture de la Ligne Aéroport : c'est un **choix de modélisation** du scénario 2028, décidé par Cyprien, pas un fait. La ligne de bus 31 (aéroport ↔ arrêts du T1 Pasteur - Mairie de Blagnac et Guyenne - Berry), créée pendant la fermeture du T2 [S13], reste en service : le réseau de bus est celui d'aujourd'hui.

**Mécanisme (générique).** `data/futur/parametres.yaml` liste les lignes Tisséo remplacées dans `lignes_tisseo_remplacees`, chacune par son `route_short_name` et la ligne du flux futur qui la remplace :

```yaml
lignes_tisseo_remplacees:
  - ligne: "AERO"
    remplacee_par: "AEROPORT"
```

1. À la construction, avec le GTFS Tisséo, chaque nom est cherché dans `routes.txt` (casse et espaces ignorés).
2. **Il doit désigner exactement une ligne.** Zéro ligne (navette renommée ou supprimée) ou plusieurs : la construction **s'arrête** (code 2), avec les lignes trouvées ou les noms voisins. On ne laisse jamais la navette rouler en silence, et on ne retire jamais une ligne au hasard.
3. Les `route_id` trouvés s'ajoutent à ceux de la ligne B recopiée (§4.5) dans `build/gtfs/scenario-2028.json`, au **format inchangé** : `{"exclude_routes": ["tisseo:<B>", "tisseo:line:99"]}`. Le CI, `scenario-filters.json` et le site les lisent sans modification.
4. Sans GTFS Tisséo (tests, poste local), rien ne peut être résolu : rien n'est exclu, et le rapport le signale.
5. Le rapport de construction a une section « Lignes Tisséo exclues du scénario 2028 ».
6. Contrôles du CI (`config/reference-trips.json`, trajet Capitole → Aéroport) : en 2028, **échec** si un itinéraire emprunte la ligne `AERO` (l'exclusion ne marche pas) ; contrôle ignoré si le flux futur est absent. **Avertissement** si le trajet le plus rapide n'emprunte pas la Ligne Aéroport.

### 7.6 Non modélisé, à vérifier

- **Nadot et Daurat**, les deux arrêts de l'ancienne branche du T2 entre Jean Maga et l'aéroport [S15][S16]. Le tram ne les dessert plus depuis le 5 juin 2023 [S13]. Les sources officielles récentes ne citent que la station Blagnac et l'aéroport [S9][S11][S12], et aucune ne dit si la Ligne Aéroport s'y arrêtera. Ils ne sont donc **pas modélisés**. Les ajouter = deux lignes dans `data/futur/stations_ligne_aeroport.csv` ; le temps de bout en bout reste 7 min.
- **Ouverture réelle avant 2028** : quand la Ligne Aéroport apparaîtra dans le GTFS Tisséo, il faudra retirer la ligne `AEROPORT` de `parametres.yaml`. Si la navette existe encore à ce moment-là, son exclusion restera un choix à trancher. Si elle disparaît du GTFS, la construction s'arrêtera (point 2 du §7.5), ce qui obligera à mettre la liste à jour.
- Article du Petit Journal du 18/09/2026 cité par Cyprien : **non consulté**, la page refuse l'accès à l'outil de lecture.

## 8. Haltes TER prévisionnelles

Ajoutées le 15/10/2026. **Décision de Cyprien (15/10/2026)** : ajouter au scénario 2028 deux haltes TER, marquées **« prévisionnel »** : Route de Launaguet et Labège-La Cadène.

### 8.1 Ce que disent les sources

| Donnée | Route de Launaguet | Labège-La Cadène |
| --- | --- | --- |
| Ligne | Bordeaux-Saint-Jean – Sète-Ville, PK 253,490 [S18] ; « axe Bordeaux-Sète » [S17] | Bordeaux-Saint-Jean – Sète-Ville [S21], trains liO de la ligne Toulouse – Narbonne [S20] |
| Gares voisines | Lalande-Église et Toulouse-Matabiau [S17][S18] | Labège-Innopole et Labège-Village [S21] |
| Correspondance | « à deux pas de la station de métro La Vache » [S17] (métro B) | pôle d'échanges du terminus de la ligne C (Labège - Gare) [S20][S21] |
| Ouverture | halte fermée depuis 2016 [S18] ; « dès l'automne 2026 » [S17], sans date précise | « fin 2028 », travaux à partir de 2027 [S20] |
| Desserte | non publiée [S17] | « 1000 voyageurs et 42 trains sont attendus par jour à la mise en service de la halte, en 2028 » [S20] ; grille 2028-2029 pas encore arrêtée [S20] |
| Position | déplacée « d'une centaine de mètres vers l'ouest » [S17] ou « vers le nord » [S18] : **les deux sources se contredisent**, nouvelle position non publiée | non publiée |
| Nom | « Route de Launaguet » (SNCF Gares & Connexions [S19]) ; « Route-de-Launaguet » sur Wikipédia [S18] | « Labège-La Cadène » [S21] ; « Labège–La Cadène » [S20] |

Le chiffre de 42 trains par jour a été **relu dans le compte rendu** de la réunion publique du 16/12/2024 [S20]. Une autre source, citée par Cyprien, annonce Route de Launaguet pour novembre 2026 ou 2027 : non retrouvée ; seule la date « automne 2026 » de [S17] est retenue, comme ordre de grandeur.

### 8.2 Méthode (avec le GTFS SNCF filtré, `--sncf-gtfs`)

1. Les gares voisines (`entre` dans `parametres.yaml`) sont cherchées dans le GTFS SNCF par leur nom, accents, casse et ponctuation ignorés (« Lalande-Église » = « Lalande Église »). Faute de nom identique, un nom plus long qui le contient est accepté s'il est unique. Seuls les arrêts des TER comptent (`motif_arrets_sncf` : « Train TER » dans le `stop_id`, ni les cars ni les TGV).
   **Gares de repli** (ajout du 15/10/2026, après le premier passage CI : « Lalande-Église » n'était desservie par aucun train du GTFS SNCF filtré) : chaque côté de la halte est une liste de gares, dans l'ordre de la ligne en s'éloignant de la halte. Au nord de Route de Launaguet : Lalande-Église, Lacourtensourt, Fenouillet - Saint-Alban, Saint-Jory, Castelnau-d'Estrétefonds (haltes de la ligne citées par [S17]) ; au sud de Labège-La Cadène : Labège Village, puis Escalquens [S21]. La première paire desservie successivement par des trains l'emporte, et le rapport dit laquelle. Si aucune ne l'est, la construction s'arrête et le message liste les gares SNCF desservies à moins de 5 km de la halte (nom, distance, nombre de courses) et les gares qui encadrent chaque candidate dans les trains. Avec une gare de repli éloignée, l'heure de passage reste partagée au prorata des distances (§8.3) : approximation plus grossière.
2. **HYPOTHÈSE de desserte** : un train qui s'arrête aux deux gares voisines, l'une juste après l'autre, s'arrêtera aussi à la halte. Un train qui ne s'arrête pas à l'une des deux (direct) ne s'y arrête pas.
   **La Cadène, décision de Cyprien (25/10/2026) : viser les 42 trains par jour annoncés** [S20]. La règle de la première paire ne donnait que 7 trains par jour de semaine (premier passage CI du 15/10/2026), car beaucoup de TER ne s'arrêtent pas à Labège Village. Pour La Cadène, `desserte: "toutes_paires"` : tout train qui s'arrête successivement à une gare de chaque côté (Labège Innopole ou Montaudran, puis Labège Village, Escalquens, Montlaur ou Baziège) s'arrête à la halte, à l'heure calculée au prorata de la distance entre ces deux arrêts. Les trains directs entre Matabiau et des gares plus lointaines ne s'y arrêtent pas. Le nombre obtenu est lu dans le rapport CI et comparé aux 42 ; HYPOTHÈSE. Seuls les trains comptent (`route_type` 2 ou 100 à 117) : les autocars SNCF qui desservent les mêmes gares ne reçoivent jamais de halte.
3. Les lignes SNCF (`route_id`) de ces trains sont **recopiées en entier** dans le flux futur (`FUT_SNCF_<identifiant SNCF>`), avec leurs arrêts, horaires, calendriers et tracés. La halte est insérée dans les trains concernés ; les autres trains de ces lignes sont recopiés sans changement, pour qu'ils roulent encore en 2028.
4. Le scénario 2028 **exclut les lignes SNCF d'origine** (`sncf:<route_id>` dans `scenario-2028.json`, même mécanisme que la navette Aéroport, §7.5) : les filtres d'OTP portent sur des lignes, pas sur des courses, d'où la copie de lignes entières.
5. Rapport de construction : une section « Haltes TER prévisionnelles » donne, pour chaque halte, son statut, l'origine de sa position, le nombre de courses qui s'y arrêtent et la médiane par jour de semaine, à comparer aux 42 trains annoncés pour La Cadène.

### 8.3 Temps de parcours — HYPOTHÈSES

- **Heure de passage** : le temps entre les deux gares voisines (horaire SNCF) est partagé au prorata des distances à vol d'oiseau gare voisine → halte → gare voisine.
- **Arrêt en halte : 60 s** (`temps_arret_s`), aucune source publique. Le train repart 60 s plus tard, et **toute la suite de sa course est décalée de 60 s**.
- Le temps perdu à freiner et à repartir n'est pas ajouté : choix un peu optimiste, d'environ une minute de plus par arrêt.

### 8.4 Positions et garde-fous

- **Position** : CSV (vide aujourd'hui), puis extraction OSM (objets ferroviaires de même nom : gare, halte, quai, jamais un arrêt de bus homonyme ; en construction d'abord), puis la station voisine citée par les sources, en **position approximative** : l'arrêt Tisséo La Vache pour Route de Launaguet [S17], la station Labège - Gare de la ligne C pour La Cadène [S20][S21].
- **Contrôle** : la halte doit se trouver entre ses deux gares voisines (gare A → halte → gare B ≤ 1,5 × A → B + 300 m), sinon elle est écartée.
- **Halte déjà ouverte** : si le GTFS SNCF dessert déjà un arrêt du même nom, ou un autre arrêt à moins de 150 m de la position de la halte, la halte **n'est pas dupliquée** en 2028 : elle est déjà dans le réseau actuel, et le rapport le signale. C'est le cas attendu pour Route de Launaguet après sa réouverture.
- **Échec bruyant** (construction arrêtée, code 2) : une gare voisine introuvable dans le GTFS SNCF, ou aucun train qui dessert les deux. Rien n'est alors recopié ni exclu au hasard.
- **Halte sautée, avec avertissement**, sans bloquer le reste du flux futur : halte sans position vérifiable, ou position hors de la ligne. Une halte prévisionnelle ne doit pas priver le scénario 2028 de la ligne C.

### 8.5 Limites

- En 2028, **tous les trains des lignes recopiées** passent par le flux futur. Sur le site, leur pastille porte donc le liseré en tirets des lignes en projet, même pour un train qui ne dessert pas la halte. Leurs horaires sont ceux de la SNCF, sauf le décalage de 60 s après la halte.
- Le nombre de trains vient de la grille SNCF actuelle (même calendrier que le reste, règle 1 du projet), pas de la grille 2028 annoncée : l'écart avec les 42 trains de La Cadène est attendu, et sera lu dans le rapport CI.
- Non vérifié ici : le nombre de trains qui s'arrêtent à Lalande-Église puis à Matabiau, ou à Labège-Innopole puis à Labège-Village. Le GTFS SNCF n'est pas téléchargeable depuis l'espace de travail : **le rapport CI le dira**.

## 9. Tableau récapitulatif

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
| Ligne Aéroport : stations | Blagnac → Aéroport (Nadot, Daurat non modélisés) | Fait (terminus) ; arrêts intermédiaires inconnus | [S9][S11][S12], §7.6 |
| Ligne Aéroport : Blagnac → Aéroport | 7 min | Fait | [S9][S11] |
| Ligne Aéroport : intervalle de pointe | 5 min | Fait | [S11][S14] |
| Ligne Aéroport : autres périodes, amplitude | comme les lignes de métro (§4.2, §4.4) | Hypothèse | §7.3 |
| Correspondance C ↔ Ligne Aéroport à Blagnac | 2 min | Hypothèse | §7.4 |
| Ligne Aéroport : nom court, couleur | « Aéroport », `#B39DDB` | Hypothèse | §7.4 |
| Navette Aéroport (`AERO`) en 2028 | retirée | Décision de Cyprien (pas une annonce officielle) | §7.5 |
| Haltes TER : emplacement, gares voisines | Route de Launaguet, Labège-La Cadène | Fait | [S17] à [S21], §8.1 |
| Haltes TER : trains qui s'y arrêtent | ceux qui desservent les deux gares voisines | Hypothèse | §8.2 |
| Haltes TER : arrêt | 60 s, suite de la course décalée | Hypothèse | §8.3 |
| Labège-La Cadène : trains par jour | 42 annoncés ; nombre simulé dans le rapport CI | Fait (annonce) ; écart attendu | [S20], §8.5 |
| Calendrier | celui de Tisséo, jours fériés en dimanche | Règle du projet | §5 |

## 10. Points à arbitrer par Cyprien

1. **Stations manquantes** : si les garde-fous laissent une station sans position au prochain passage CI, la saisir à la main depuis openstreetmap.org (source vérifiable). Le scénario 2028 reste bloqué tant qu'une station n'a pas de position.
2. **Part des rames B prolongées** : l'hypothèse actuelle (assez de rames pour 5 min en pointe) est à remplacer dès que Tisséo publie la grille réelle.
3. **Colomiers → Matabiau 17 min** : ce chiffre combine deux sources d'époques différentes. Faut-il garder ce point de calage, ou ne retenir que les 37 min de bout en bout ?
4. **Labège - Gare ou Labège La Cadène** pour le terminus (les deux figurent sur la page Métropole).
5. **Nadot et Daurat** sur la Ligne Aéroport : les ajouter (hypothèse : desservis comme par l'ancien T2) ou attendre une annonce de Tisséo (§7.6) ?
6. **Navette Aéroport** : la retirer en 2028 est un choix de modélisation, pas une annonce. À revoir si Tisséo annonce son maintien (§7.5).
7. **Correspondance à Blagnac** : 2 min retenues ; à comparer aux 22 min Matabiau → aéroport annoncées, une fois le rapport CI lu (§7.2).
8. **Haltes TER** : l'arrêt de 60 s et la règle « s'arrête aux deux gares voisines » conviennent-ils pour Route de Launaguet ? Pour La Cadène, tranché le 25/10/2026 : viser les 42 trains annoncés (§8.2).
9. **Route de Launaguet** : si elle n'est pas encore dans le GTFS SNCF quand elle ouvre, faut-il la garder dans le scénario 2028 ? (Dès qu'elle y est, elle n'est plus dupliquée, §8.4.)

## 11. Mise en œuvre (pour l'architecte)

```bash
python -m pip install -r scripts/requirements.txt
# 1. positions et tracé depuis OSM (extrait découpé)
python scripts/extract_futur_osm.py --osm build/otp/osm/zone.osm.pbf --output-dir build/futur-osm
# 2. GTFS futur + scenario-2028.json, dans le dossier de --output
python scripts/build_gtfs_futur.py --tisseo-gtfs build/raw/tisseo.gtfs.zip \
  --sncf-gtfs build/otp/gtfs/sncf.gtfs.zip --osm-dir build/futur-osm --output build/gtfs/futur.gtfs.zip
```

Sorties (données dérivées sous ODbL) : `build/futur-osm/stations_osm.csv`, `traces_osm.geojson`, `rapport_osm.md` ; `build/gtfs/futur.gtfs.zip` (licence dans `feed_info.txt` et `attributions.txt`), `build/gtfs/scenario-2028.json`, `build/gtfs/futur-rapport.md`. Rien n'est versionné, puisque `build/` est ignoré. À l'ouverture réelle de la B prolongée, il suffit de retirer la ligne `B_EXT` de `parametres.yaml` ; à celle de la Ligne Aéroport, la ligne `AEROPORT` (et l'entrée `AERO` de `lignes_tisseo_remplacees` si la navette disparaît). Si un nom de `lignes_tisseo_remplacees` ne désigne plus exactement une ligne du GTFS Tisséo, la construction du GTFS futur échoue : le graphe est alors publié sans le flux futur (« succès partiel »), et il faut corriger la liste.

## Sources (consultées le 14/10/2026, [S11] à [S21] et [R1] le 15/10/2026)

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
- [S11] La Clé publique, « Toulouse-Blagnac : le tram revient à l'aéroport, mais pas le T2 », 16/09/2026 — https://laclepublique.fr/haute-garonne/articles/2026/2026-09-16-rames-ligne-aeroport/
- [S12] Tisséo Ingénierie, « Ligne Aéroport » (page modifiée le 13/10/2025) — https://www.tisseo-ingenierie.fr/projets_en_cours/ligne-aeroport/
- [S13] Tisséo, dépliant « À partir du lundi 5 juin 2023 » (arrêt du T2, navette Aéroport, bus 31) — https://www.toulouse.aeroport.fr/sites/default/files/2024-10/TISSEO%20aeroport%20tram%20T2%20depliant-FR.pdf
- [S14] Tisséo, même dépliant en anglais (« Airport line frequency: in 2026, one tram every 5min ») — https://www.toulouse.aeroport.fr/sites/default/files/2024-09/Tisseo_solutions-arret-T2_ANG_V2_depliant.pdf
- [S15] Wikipédia, « Ligne Aéroport du tramway de Toulouse » — https://fr.wikipedia.org/wiki/Ligne_A%C3%A9roport_Express_du_tramway_de_Toulouse
- [S16] Wikipedia, « Toulouse tramway » — https://en.wikipedia.org/wiki/Toulouse_tramway
- [S17] toulouseimmo9, « Halte Route de Launaguet : réouverture en 2026 », 16/09/2026 — https://www.toulouseimmo9.com/actualites/transports/halte-route-de-launaguet-toulouse-reouverture-2026
- [S18] Wikipédia, « Gare de Route-de-Launaguet » — https://fr.wikipedia.org/wiki/Gare_de_Route-de-Launaguet
- [S19] SNCF Gares & Connexions, fiche « Route de Launaguet » — https://www.garesetconnexions.sncf/en/stations-services/route-launaguet/pratical-info
- [S20] SNCF Gares & Connexions, compte rendu de la réunion publique du 16/12/2024 sur la halte de Labège-La Cadène — https://www.garesetconnexions.sncf/sites/default/files/2025-01/SNCF-G-Co_Labege__CR--reunion-publique-du-16122024_V1.pdf
- [S21] Wikipédia, « Gare de Labège-La Cadène » — https://fr.wikipedia.org/wiki/Gare_de_Lab%C3%A8ge-La_Cad%C3%A8ne
- [R1] Rapport de construction du graphe du 15/10/2026 (exécution 38801486541), branche `rapports` du dépôt : `latest.md` (« BUS AERO (tisseo) ») et `latest-files/demo-responses.json` (route `tisseo:line:99`, `shortName` « AERO », `longName` « Navette Aéroport », couleur `e46809`) — https://github.com/CyprienBethe/toulouse-demain/actions/runs/38801486541
- GTFS Tisséo (ODbL), recopié et mesuré à chaque construction : https://www.data.gouv.fr/datasets/tisseo-reseau-transport-urbain-toulousain
- GTFS SNCF (ODbL), filtré à la zone, dont les lignes qui passent par une halte sont recopiées : https://www.data.gouv.fr/datasets/horaires-sncf

## Ce qu'il faut retenir

- Les chiffres officiels sont repris tels quels : 21 stations, 37 min de Colomiers à Labège, une rame toutes les 3 min 25 en pointe sur la C ; la B est vraiment prolongée, avec assez de rames jusqu'à Labège Madron pour une toutes les 5 min en pointe (répartition supposée, faute de grille publiée).
- Les positions des stations viennent d'OpenStreetMap. Deux erreurs du premier essai (Raisin, Ormeau) sont maintenant bloquées : une station mal placée est rejetée et signalée comme manquante plutôt que fausse.
- Il reste à trancher le calage à 17 min de Matabiau et le nom du terminus de Labège (§10).
- Nouveau (15/10/2026) : le tram de la Ligne Aéroport relie Blagnac (station de la ligne C) à l'aéroport en 7 min, toutes les 5 min en pointe, et la navette Aéroport est retirée du scénario 2028 (choix de Cyprien). Si Tisséo renomme ou supprime la navette dans ses données, la construction s'arrête au lieu de se tromper en silence.
- Deux haltes TER « prévisionnelles » s'ajoutent en 2028 : Route de Launaguet (près du métro La Vache) et Labège-La Cadène (au terminus de la C). Les trains qui s'arrêtent déjà aux deux gares voisines s'y arrêtent aussi, une minute ; une halte déjà ouverte n'est jamais comptée deux fois.
