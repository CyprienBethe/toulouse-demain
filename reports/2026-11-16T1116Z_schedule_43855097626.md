<!-- toulouse-demain:graph-report -->
## Rapport de construction du graphe : SUCCÈS

- Date : 2026-11-16 11:16 UTC
- Événement : `schedule`, branche `main`, commit `e962114`
- Image OTP : `docker.io/opentripplanner/opentripplanner:2.10.0`
- Exécution : https://github.com/CyprienBethe/toulouse-demain/actions/runs/43855097626
- Durée depuis le début du workflow : 7 min 47 s

### Étapes

| Étape | Résultat |
| --- | --- |
| Téléchargement des sources | réussi |
| Calcul de la zone | réussi |
| Découpage OpenStreetMap | réussi |
| Filtrage du GTFS SNCF | réussi |
| Construction du GTFS futur (data engineer) | réussi |
| Construction du graphe OTP | réussi |
| Démarrage du serveur OTP | réussi |
| Trajets de référence | réussi |

### Données

| Source | Taille | SHA-256 (début) | Last-Modified |
| --- | --- | --- | --- |
| tisseo | 11,00 Mo | `4de6bc73c9a1` | ? |
| sncf | 5,65 Mo | `c7fa334890da` | Sun, 15 Nov 2026 20:49:52 GMT |
| osm | 364,55 Mo | `3e9e17d9f12b` | Mon, 16 Nov 2026 04:58:42 GMT |

Zone (rectangle WGS84 min_lon,min_lat,max_lon,max_lat) : `1.02706,43.30141,1.81453,43.83973` — calculée sur 5728 arrêts Tisséo + 10.0 km de marge.
OpenStreetMap découpé : 364,55 Mo → 82,76 Mo (osmium version 1.16.0).
GTFS SNCF filtré : 1388 courses, 22 lignes, 118 arrêts gardés ; stop_times 529281 → 7068 lignes ; route_type {'2': 20, '3': 2}.
GTFS futur : 1,83 Mo, 2 lignes (C, B), 105 arrêts, 8722 courses.

### Moteur OpenTripPlanner (mesures de cette exécution)

| Mesure | Valeur |
| --- | --- |
| Durée de construction du graphe | 1 min 26 s |
| Mémoire max du conteneur pendant la construction (-Xmx12g) | 4,19 Go |
| Tas Java vivant max après GC, construction | 1,19 Go |
| Taille de graph.obj | 83,27 Mo |
| Démarrage du serveur (chargement du graphe) | 11 s |
| Mémoire du conteneur serveur prêt (-Xmx6g) | 914,25 Mo |
| Mémoire du conteneur serveur après les trajets | 1,12 Go |
| Tas Java vivant max après GC, serveur | 613,42 Mo |

### Trajets de référence (départ 2026-11-17T08:30:00+01:00)

| Trajet | Actuel | 2028 | Écart |
| --- | --- | --- | --- |
| Capitole → Aéroport Toulouse-Blagnac | 28 min | 28 min | identique |
| Gare Matabiau → Ramonville | 20 min | 21 min | 1 min plus long en 2028 |
| Colomiers gare → Labège | 45 min | 48 min | 3 min plus long en 2028 |
| Gare de Colomiers → Diagora (Labège) | 53 min | 38 min | 15 min plus court en 2028 |
| Capitole → Gare Matabiau, marche seule | 17 min | — |  |
| Capitole → Aéroport Toulouse-Blagnac, vélo | 38 min | — |  |

- Scénario actuel : 1 agence(s) exclue(s), lignes exclues : aucune
- Scénario 2028 : 0 agence(s) exclue(s), lignes exclues : tisseo:line:69
- Modes présents dans le graphe : BUS, GONDOLA, RAIL, SUBWAY, TRAM ; modes demandés : BUS, TRAM, SUBWAY, RAIL, GONDOLA

<details><summary>Détail des trajets</summary>

**Capitole → Aéroport Toulouse-Blagnac** (transit)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 37 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 34 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 28 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 862 ms)
- 2028 : 37 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- 2028 : 34 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- 2028 : 28 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 371 ms)

**Gare Matabiau → Ramonville** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Ramonville [tisseo, 12 arrêt(s), 43.555866, 1.47705]
- actuel : 20 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 1 min
- actuel : 32 min, 0 corresp., walk 14 min → SUBWAY B (tisseo) → walk 1 min
- actuel : 30 min, 1 corresp., walk 6 min → SUBWAY A (tisseo) → walk 2 min → SUBWAY B (tisseo) → walk 1 min
  (réponse en 390 ms)
- 2028 : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (futur) → walk 3 min
- 2028 : 32 min, 0 corresp., walk 13 min → SUBWAY B (futur) → walk 3 min
- 2028 : 32 min, 0 corresp., walk 13 min → SUBWAY B (futur) → walk 3 min
  (réponse en 212 ms)

**Colomiers gare → Labège** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- actuel : 57 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- actuel : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 430 ms)
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
  (réponse en 292 ms)

**Gare de Colomiers → Diagora (Labège)** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Diagora [futur, 2 arrêt(s), 43.544148, 1.50968]
- actuel : 53 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf) → walk 8 min
- actuel : 68 min, 3 corresp., RAIL C16 (sncf) → walk 4 min → BUS 34 (tisseo) → walk 3 min → SUBWAY B (tisseo) → walk 2 min → BUS 79 (tisseo) → walk 2 min
- actuel : 61 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min → BUS 79 (tisseo) → walk 2 min
  (réponse en 330 ms)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
  (réponse en 246 ms)

**Capitole → Gare Matabiau, marche seule** (walk)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 17 min, 0 corresp., walk 17 min
  (réponse en 22 ms)

**Capitole → Aéroport Toulouse-Blagnac, vélo** (bicycle)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 38 min, 0 corresp., bicycle 38 min
  (réponse en 119 ms)

</details>

- Graphe publié : release « graph-20261116-16 »
