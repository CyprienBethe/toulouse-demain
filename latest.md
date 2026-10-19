<!-- toulouse-demain:graph-report -->
## Rapport de construction du graphe : SUCCÈS

- Date : 2026-10-19 08:53 UTC
- Événement : `schedule`, branche `main`, commit `e962114`
- Image OTP : `docker.io/opentripplanner/opentripplanner:2.10.0`
- Exécution : https://github.com/CyprienBethe/toulouse-demain/actions/runs/39225337666
- Durée depuis le début du workflow : 5 min 49 s

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
| tisseo | 15,95 Mo | `579186e46fa2` | ? |
| sncf | 5,45 Mo | `6892f10eb62e` | Sun, 18 Oct 2026 19:36:04 GMT |
| osm | 363,16 Mo | `2c94a7b6942a` | Mon, 19 Oct 2026 01:29:24 GMT |

Zone (rectangle WGS84 min_lon,min_lat,max_lon,max_lat) : `1.02706,43.30141,1.81453,43.83973` — calculée sur 5730 arrêts Tisséo + 10.0 km de marge.
OpenStreetMap découpé : 363,16 Mo → 82,63 Mo (osmium version 1.16.0).
GTFS SNCF filtré : 1378 courses, 22 lignes, 121 arrêts gardés ; stop_times 512070 → 6992 lignes ; route_type {'2': 20, '3': 2}.
GTFS futur : 2,88 Mo, 2 lignes (C, B), 105 arrêts, 13950 courses.

### Moteur OpenTripPlanner (mesures de cette exécution)

| Mesure | Valeur |
| --- | --- |
| Durée de construction du graphe | 3 min 51 s |
| Mémoire max du conteneur pendant la construction (-Xmx12g) | 4,82 Go |
| Tas Java vivant max après GC, construction | 1,58 Go |
| Taille de graph.obj | 88,16 Mo |
| Démarrage du serveur (chargement du graphe) | 11 s |
| Mémoire du conteneur serveur prêt (-Xmx6g) | 1,15 Go |
| Mémoire du conteneur serveur après les trajets | 1,22 Go |
| Tas Java vivant max après GC, serveur | 750,78 Mo |

### Trajets de référence (départ 2026-10-20T08:30:00+02:00)

| Trajet | Actuel | 2028 | Écart |
| --- | --- | --- | --- |
| Capitole → Aéroport Toulouse-Blagnac | 26 min | 26 min | identique |
| Gare Matabiau → Ramonville | 21 min | 21 min | identique |
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
- actuel : 33 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 32 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 26 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 898 ms)
- 2028 : 33 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- 2028 : 32 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- 2028 : 26 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 280 ms)

**Gare Matabiau → Ramonville** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Ramonville [tisseo, 11 arrêt(s), 43.555881, 1.47712]
- actuel : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min
- actuel : 32 min, 0 corresp., walk 14 min → SUBWAY B (tisseo) → walk 2 min
- actuel : 31 min, 0 corresp., walk 1 min → BUS 27 (tisseo) → walk 0 min
  (réponse en 433 ms)
- 2028 : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (futur) → walk 3 min
- 2028 : 32 min, 0 corresp., walk 13 min → SUBWAY B (futur) → walk 3 min
- 2028 : 31 min, 0 corresp., walk 1 min → BUS 27 (tisseo) → walk 0 min
  (réponse en 166 ms)

**Colomiers gare → Labège** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- actuel : 53 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- actuel : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 376 ms)
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
  (réponse en 311 ms)

**Gare de Colomiers → Diagora (Labège)** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Diagora [futur, 2 arrêt(s), 43.544148, 1.50968]
- actuel : 53 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf) → walk 8 min
- actuel : 59 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min → BUS 79 (tisseo) → walk 2 min
- actuel : 76 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf) → walk 8 min
  (réponse en 344 ms)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
  (réponse en 250 ms)

**Capitole → Gare Matabiau, marche seule** (walk)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 17 min, 0 corresp., walk 17 min
  (réponse en 20 ms)

**Capitole → Aéroport Toulouse-Blagnac, vélo** (bicycle)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 38 min, 0 corresp., bicycle 38 min
  (réponse en 122 ms)

</details>

- Graphe publié : release « graph-20261019-11 »
