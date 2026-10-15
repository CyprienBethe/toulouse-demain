# Rapport de construction du GTFS « futur »

Données dérivées sous ODbL. Horaires simulés : voir docs/hypotheses-reseau-2028.md.

- GTFS Tisséo : oui (tisseo.gtfs.zip)
- Extraction OSM : oui (build/futur-osm)
- Calendrier : du 2026-10-14 au 2026-11-17, 8 jour(s) modifié(s)
  - 2026-10-29 : JEUVEN → DIM
  - 2026-11-11 : LUNMER → aucun service
  - 2026-11-12 : JEUVEN → aucun service
  - 2026-11-13 : JEUVEN → aucun service
  - 2026-11-14 : SAM → aucun service
  - 2026-11-15 : DIM → aucun service
  - 2026-11-16 : LUNMER → aucun service
  - 2026-11-17 : LUNMER → aucun service
- Temps d'arrêt en station : 20 s

## Ligne B en rames directes (recopiée du GTFS Tisséo et prolongée)

- Courses Tisséo recopiées : 12466
- Courses non prolongées : 9068
- Courses prolongées depuis Labège Madron : 1704
- Courses prolongées vers Labège Madron : 1694
- Services Tisséo dédoublés (choix différent selon les jours) : 0
- Scénario 2028 : exclut tisseo:line:69 (scenario-2028.json)
- Intervalle obtenu sur le prolongement, jours les plus fréquents (4 jour(s), profil semaine) :
  - creuse : 8 min 13 en moyenne
  - pointe : 5 min 05 en moyenne
  - soiree : 14 min 14 en moyenne

## Lignes Tisséo exclues du scénario 2028 (scenario-2028.json)

| Ligne Tisséo | route_id | Nom long | Remplacée par |
| --- | --- | --- | --- |
| B | tisseo:line:69 | - | B (recopiée et prolongée) |
| AERO | tisseo:line:99 | Navette Aéroport | Aéroport |
| K1 | sncf:FR:Line::0312E125-B6BC-404C-A7D1-C1600D4CACAF: | Toulouse Matabiau - Brive La Gaillarde | copie avec halte(s) Route de Launaguet, Labège-La Cadène |
| K13 | sncf:FR:Line::1CEA14EA-7F5A-4D44-A739-F6A13138F139: | Toulouse Matabiau - Nimes | copie avec halte(s) Route de Launaguet, Labège-La Cadène |
| C1 | sncf:FR:Line::3EA7647F-5C9C-4833-AFB5-3B9D213283B0: | Toulouse Matabiau - Montauban Ville Bourbon | copie avec halte(s) Route de Launaguet, Labège-La Cadène |
| C3 | sncf:FR:Line::52D5BA37-0A0E-43ED-AB0D-DAF12888D586: | Toulouse Matabiau - Narbonne | copie avec halte(s) Route de Launaguet, Labège-La Cadène |
| K11 | sncf:FR:Line::F9BD440B-D41F-4106-B2BA-B807F0635262: | Toulouse Matabiau - Agen | copie avec halte(s) Route de Launaguet, Labège-La Cadène |

## Haltes TER prévisionnelles

Temps d'arrêt en halte : 60 s ; courses SNCF recopiées : 298.

| Halte | Entre | Statut | Position | Courses avec arrêt | Trains par jour de semaine (médiane) | Annoncés |
| --- | --- | --- | --- | --- | --- | --- |
| Route de Launaguet | Lacourtensourt – Toulouse Matabiau | ajoutée | GTFS Tisséo, arrêt stop_area:SA_332 « La Vache » : approximative (la halte est annoncée à côté) | 96 | 12.0 | - |
| Labège-La Cadène | Labège Innopole – Labège Village | ajoutée | station future voisine « Labège - Gare » (ligne C) : approximative (la halte est annoncée à côté) | 16 | 7.0 | 42 |

## Ligne C (C, métro)

| # | Station | lat | lon | Position |
| --- | --- | --- | --- | --- |
| 1 | Colomiers - Gare | 43.604438 | 1.335278 | OpenStreetMap (https://www.openstreetmap.org/node/8832609048) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 2 | Fontaine Lumineuse | 43.608832 | 1.353838 | OpenStreetMap (https://www.openstreetmap.org/node/8832609049) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 3 | Saint-Martin-du-Touch | 43.610345 | 1.371380 | OpenStreetMap (https://www.openstreetmap.org/node/8832609053) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 4 | Blagnac | 43.621614 | 1.395620 | OpenStreetMap (https://www.openstreetmap.org/node/8832609065) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 5 | Sept Deniers - Stade Toulousain | 43.620455 | 1.411535 | OpenStreetMap (https://www.openstreetmap.org/node/8832609067) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 6 | Ponts-Jumeaux | 43.619939 | 1.423221 | OpenStreetMap (https://www.openstreetmap.org/node/8832609070) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 7 | Fondeyre | 43.632202 | 1.427996 | OpenStreetMap (https://www.openstreetmap.org/node/8832628139) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 8 | La Vache Gare - Le Grand marché | 43.635551 | 1.437172 | OpenStreetMap (https://www.openstreetmap.org/node/8832609078) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 9 | Lycée Toulouse-Lautrec | 43.626722 | 1.443863 | OpenStreetMap (https://www.openstreetmap.org/node/8832609082) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 10 | Raisin | 43.618298 | 1.446263 | OpenStreetMap (https://www.openstreetmap.org/node/8832609088) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 11 | Bonnefoy | 43.618649 | 1.456353 | OpenStreetMap (https://www.openstreetmap.org/node/8832609092) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 12 | Matabiau Gare | 43.611381 | 1.455571 | OpenStreetMap (https://www.openstreetmap.org/node/8832609095) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 13 | François Verdier | 43.600361 | 1.451951 | OpenStreetMap (https://www.openstreetmap.org/node/8832609101) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 14 | Côte Pavée | 43.593818 | 1.465899 | OpenStreetMap (https://www.openstreetmap.org/node/8832609106) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 15 | Limayrac - Cité de l'Espace | 43.591257 | 1.480239 | OpenStreetMap (https://www.openstreetmap.org/node/8832609110) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 16 | Ormeau | 43.579078 | 1.483376 | OpenStreetMap (https://www.openstreetmap.org/node/11071166323) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 17 | Montaudran Gare - Piste des Géants | 43.572234 | 1.481426 | OpenStreetMap (https://www.openstreetmap.org/node/8832628138) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 18 | Aerospace Campus | 43.563518 | 1.492399 | OpenStreetMap (https://www.openstreetmap.org/node/10890417177) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 19 | Labège Madron | 43.551260 | 1.505392 | OpenStreetMap (https://www.openstreetmap.org/node/8832628130) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 20 | Diagora | 43.544148 | 1.509680 | OpenStreetMap (https://www.openstreetmap.org/node/8832628132) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 21 | Labège - Gare | 43.538970 | 1.520634 | OpenStreetMap (https://www.openstreetmap.org/node/8832628137) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |

| De | À | Distance (m) | Tracé | Arrivée cumulée |
| --- | --- | --- | --- | --- |
| Colomiers - Gare | Fontaine Lumineuse | 1573 | osm | 1 min 29 |
| Fontaine Lumineuse | Saint-Martin-du-Touch | 1467 | osm | 3 min 12 |
| Saint-Martin-du-Touch | Blagnac | 2587 | osm | 5 min 59 |
| Blagnac | Sept Deniers - Stade Toulousain | 1296 | osm | 7 min 32 |
| Sept Deniers - Stade Toulousain | Ponts-Jumeaux | 954 | osm | 8 min 46 |
| Ponts-Jumeaux | Fondeyre | 1508 | osm | 10 min 32 |
| Fondeyre | La Vache Gare - Le Grand marché | 1079 | osm | 11 min 53 |
| La Vache Gare - Le Grand marché | Lycée Toulouse-Lautrec | 1132 | osm | 13 min 17 |
| Lycée Toulouse-Lautrec | Raisin | 1039 | osm | 14 min 36 |
| Raisin | Bonnefoy | 901 | osm | 15 min 47 |
| Bonnefoy | Matabiau Gare | 940 | osm | 17 min 00 |
| Matabiau Gare | François Verdier | 1317 | osm | 19 min 11 |
| François Verdier | Côte Pavée | 1618 | osm | 21 min 48 |
| Côte Pavée | Limayrac - Cité de l'Espace | 1212 | osm | 23 min 51 |
| Limayrac - Cité de l'Espace | Ormeau | 1554 | osm | 26 min 22 |
| Ormeau | Montaudran Gare - Piste des Géants | 787 | osm | 27 min 49 |
| Montaudran Gare - Piste des Géants | Aerospace Campus | 1368 | osm | 30 min 04 |
| Aerospace Campus | Labège Madron | 1943 | osm | 33 min 09 |
| Labège Madron | Diagora | 899 | osm | 34 min 45 |
| Diagora | Labège - Gare | 1361 | osm | 37 min 00 |

Longueur : 26.54 km ; temps de bout en bout : 37 min 00 ; vitesse commerciale : 43.0 km/h.

## Ligne B (B_EXT, métro)

| # | Station | lat | lon | Position |
| --- | --- | --- | --- | --- |
| 1 | Ramonville | 43.556101 | 1.477827 | OpenStreetMap (https://www.openstreetmap.org/node/5130283102) : station exacte (OSM : quai ou arrêt existant, même station) |
| 2 | Parc du Canal | 43.551261 | 1.488743 | OpenStreetMap (https://www.openstreetmap.org/node/10890417169) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |
| 3 | Labège Madron | 43.551260 | 1.505392 | OpenStreetMap (https://www.openstreetmap.org/node/8832628130) : station exacte (OSM : quai ou arrêt de même nom sur le tracé en construction) |

| De | À | Distance (m) | Tracé | Arrivée cumulée |
| --- | --- | --- | --- | --- |
| Ramonville | Parc du Canal | 1078 | osm | 1 min 25 |
| Parc du Canal | Labège Madron | 1342 | droit | 3 min 30 |

Longueur : 2.42 km ; temps de bout en bout : 3 min 30 ; vitesse commerciale : 41.5 km/h.

## Ligne Aéroport (AEROPORT, tram)

| # | Station | lat | lon | Position |
| --- | --- | --- | --- | --- |
| 1 | Blagnac | 43.621614 | 1.395620 | OpenStreetMap (https://www.openstreetmap.org/node/8832609065) : station exacte (OSM : quai ou arrêt de même nom sur la voie de tram) |
| 2 | Aéroport | 43.631625 | 1.375218 | OpenStreetMap (https://www.openstreetmap.org/node/5352944268) : approximative (OSM : quai ou arrêt existant de même nom, à 892 m de la voie de tram) |

| De | À | Distance (m) | Tracé | Arrivée cumulée |
| --- | --- | --- | --- | --- |
| Blagnac | Aéroport | 1984 | droit | 7 min 00 |

Longueur : 1.98 km ; temps de bout en bout : 7 min 00 ; vitesse commerciale : 17.0 km/h.

## Intervalles

| Période | Coefficient | Origine | Ligne C | Ligne B_EXT | Ligne AEROPORT |
| --- | --- | --- | --- | --- | --- |
| pointe | 1.0 | mesuré sur la ligne B Tisséo (1 min 25) | 3 min 25 | 5 min 00 | 5 min 00 |
| creuse | 1.65 | mesuré sur la ligne B Tisséo (2 min 20) | 5 min 38 | 8 min 15 | 8 min 15 |
| soiree | 2.82 | mesuré sur la ligne B Tisséo (4 min 00) | 9 min 38 | 14 min 06 | 14 min 06 |
| samedi | 1.76 | mesuré sur la ligne B Tisséo (2 min 30) | 6 min 01 | 8 min 48 | 8 min 48 |
| dimanche | 2.82 | mesuré sur la ligne B Tisséo (4 min 00) | 9 min 38 | 14 min 06 | 14 min 06 |

| Service | Premier départ | Dernier départ | Origine |
| --- | --- | --- | --- |
| LUNMER | 05:15:19 | 24:00:19 | mesuré sur la ligne B Tisséo le 2026-10-19 |
| JEUVEN | 05:15:19 | 24:00:19 | mesuré sur la ligne B Tisséo le 2026-10-22 |
| SAM | 05:15:19 | 27:00:19 | mesuré sur la ligne B Tisséo le 2026-10-17 |
| DIM | 05:15:19 | 24:00:19 | mesuré sur la ligne B Tisséo le 2026-10-25 |

## Arrêts Tisséo à moins de 400 m

Les correspondances avec le réseau actuel sont calculées par le moteur (marche sur le réseau OSM).

| Ligne | Station | Correspondances attendues | Arrêts Tisséo proches |
| --- | --- | --- | --- |
| C | Colomiers - Gare | TER (ligne Arènes - Colomiers) | Colomiers Gare SNCF (105 m), Oisans (214 m), Mont Blanc (358 m) |
| C | Fontaine Lumineuse | - | Fontaine (61 m), Caulet (236 m), Oratoire (264 m) |
| C | Saint-Martin-du-Touch | - | Crabe (52 m), Bouriette (279 m), Passerelle Airbus (363 m) |
| C | Blagnac | Tram T1 ; Ligne Aéroport (tram) | Ancely (373 m) |
| C | Sept Deniers - Stade Toulousain | - | Nougaro (296 m), Lully (306 m), Route de Blagnac (388 m) |
| C | Ponts-Jumeaux | - | Matisse (175 m), Elche (182 m) |
| C | Fondeyre | - | Jules Ferry (297 m), Bastiat (335 m), Adonis (392 m) |
| C | La Vache Gare - Le Grand marché | Métro B ; TER (projet de halte) | La Vache (266 m), Pader (323 m), Claude Bernard (330 m) |
| C | Lycée Toulouse-Lautrec | - | Lycée Toulouse-Lautrec (70 m), Cordeau (108 m), Impasse Curie (249 m) |
| C | Raisin | - | Raisin (306 m) |
| C | Bonnefoy | - | Eglise Bonnefoy (57 m), Arago (187 m), Hauts de Bonnefoy (291 m) |
| C | Matabiau Gare | Métro A (Marengo - SNCF) ; TER et grandes lignes (gare Toulouse-Matabiau) | Marengo-SNCF (73 m), Matabiau Gare SNCF (203 m), Riquet (270 m) |
| C | François Verdier | Métro B | François Verdier (66 m), Place Dupuy (179 m), Quartier Général (307 m) |
| C | Côte Pavée | - | Belle Paule (169 m), Beau Soleil (197 m), Lanfant (379 m) |
| C | Limayrac - Cité de l'Espace | - | Baroux (151 m), Firmis (182 m), Jacinthes (363 m) |
| C | Ormeau | - | Ormeau (58 m), Garin (101 m), Tahiti (181 m) |
| C | Montaudran Gare - Piste des Géants | TER (gare de Montaudran) | Montaudran Gare (59 m), Gonin (240 m), Piste (255 m) |
| C | Aerospace Campus | - | Clément Ader (151 m), Cosmonautes (326 m), Rodier (388 m) |
| C | Labège Madron | Métro B (prolongement) | Ctre Cial Labège (205 m), Centre Commercial Labège (236 m), Arts (260 m) |
| C | Diagora | - | Tolosane (127 m), Rostand (201 m), Marco Polo (255 m) |
| C | Labège - Gare | TER (gare de Labège) | Chêne Vert (273 m), Campus de Bissy (335 m), Guiraudie-Aufève (346 m) |
| B_EXT | Ramonville | Métro B (terminus actuel) ; bus | Ramonville (11 m), CNES (294 m), Violettes (381 m) |
| B_EXT | Parc du Canal | - | Ateliers 31 (87 m), Hermès (262 m), Joliot Curie (361 m) |
| B_EXT | Labège Madron | Métro C | Ctre Cial Labège (205 m), Centre Commercial Labège (236 m), Arts (260 m) |
| AEROPORT | Blagnac | Métro C ; Tram T1 | Ancely (373 m) |
| AEROPORT | Aéroport | - | Aéroport (16 m), Doret (323 m), Daurat (365 m) |

## Contenu du GTFS

- agency.txt : 1 ligne(s)
- attributions.txt : 3 ligne(s)
- calendar.txt : 4 ligne(s)
- calendar_dates.txt : 31133 ligne(s)
- feed_info.txt : 1 ligne(s)
- routes.txt : 8 ligne(s)
- shapes.txt : 4142 ligne(s)
- stop_times.txt : 290852 ligne(s)
- stops.txt : 144 ligne(s)
- transfers.txt : 4 ligne(s)
- trips.txt : 15260 ligne(s)

## Avertissements

- Halte TER Route de Launaguet : gares voisines de repli retenues, Lacourtensourt et Toulouse Matabiau (Lalande-Église : non desservie ; Lacourtensourt → Toulouse Matabiau : 96 passage(s) de train).
