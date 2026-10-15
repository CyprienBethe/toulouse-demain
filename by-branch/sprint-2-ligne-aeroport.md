<!-- toulouse-demain:graph-report -->
## Rapport de construction du graphe : SUCCÈS AVEC AVERTISSEMENTS

- Date : 2026-10-15 21:41 UTC
- Événement : `pull_request`, branche `3/merge`, commit `7f55cde`
- Image OTP : `docker.io/opentripplanner/opentripplanner:2.10.0`
- Exécution : https://github.com/CyprienBethe/toulouse-demain/actions/runs/38811244145
- Durée depuis le début du workflow : 4 min 14 s

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
| tisseo | 16,00 Mo | `e50e70ecc365` | ? |
| sncf | 5,52 Mo | `5599d956aa87` | Thu, 15 Oct 2026 20:00:05 GMT |
| osm | 362,95 Mo | `8d68b6c8b88c` | Thu, 15 Oct 2026 01:51:47 GMT |

Zone (rectangle WGS84 min_lon,min_lat,max_lon,max_lat) : `1.02706,43.30141,1.81453,43.83973` — calculée sur 5726 arrêts Tisséo + 10.0 km de marge.
OpenStreetMap découpé : 362,95 Mo → 82,61 Mo (osmium version 1.16.0).
GTFS SNCF filtré : 1390 courses, 22 lignes, 121 arrêts gardés ; stop_times 517476 → 7024 lignes ; route_type {'2': 20, '3': 2}.
GTFS futur : 2,92 Mo, 8 lignes (C, B, Aéroport, K1, K13, C1, C3, K11), 144 arrêts, 15260 courses.

### Moteur OpenTripPlanner (mesures de cette exécution)

| Mesure | Valeur |
| --- | --- |
| Durée de construction du graphe | 2 min 21 s |
| Mémoire max du conteneur pendant la construction (-Xmx12g) | 5,89 Go |
| Tas Java vivant max après GC, construction | 1,50 Go |
| Taille de graph.obj | 88,63 Mo |
| Démarrage du serveur (chargement du graphe) | 6 s |
| Mémoire du conteneur serveur prêt (-Xmx6g) | 1,16 Go |
| Mémoire du conteneur serveur après les trajets | 1,23 Go |
| Tas Java vivant max après GC, serveur | 654,31 Mo |

### Trajets de référence (départ 2026-10-20T08:30:00+02:00)

| Trajet | Actuel | 2028 | Écart |
| --- | --- | --- | --- |
| Capitole → Aéroport Toulouse-Blagnac | 26 min | 36 min | 10 min plus long en 2028 |
| Gare Matabiau → Ramonville | 21 min | 21 min | identique |
| Colomiers gare → Labège | 45 min | 48 min | 3 min plus long en 2028 |
| Gare de Colomiers → Diagora (Labège) | 53 min | 38 min | 15 min plus court en 2028 |
| La Vache (halte Route de Launaguet) → Gare Matabiau | 26 min | 4 min | 22 min plus court en 2028 |
| Gare Matabiau → Labège-La Cadène | 24 min | 27 min | 3 min plus long en 2028 |
| Capitole → Gare Matabiau, marche seule | 17 min | — |  |
| Capitole → Aéroport Toulouse-Blagnac, vélo | 38 min | — |  |

- Scénario actuel : 1 agence(s) exclue(s), lignes exclues : aucune
- Scénario 2028 : 0 agence(s) exclue(s), lignes exclues : tisseo:line:69, tisseo:line:99, sncf:FR:Line::0312E125-B6BC-404C-A7D1-C1600D4CACAF:, sncf:FR:Line::1CEA14EA-7F5A-4D44-A739-F6A13138F139:, sncf:FR:Line::3EA7647F-5C9C-4833-AFB5-3B9D213283B0:, sncf:FR:Line::52D5BA37-0A0E-43ED-AB0D-DAF12888D586:, sncf:FR:Line::F9BD440B-D41F-4106-B2BA-B807F0635262:
- Modes présents dans le graphe : BUS, GONDOLA, RAIL, SUBWAY, TRAM ; modes demandés : BUS, TRAM, SUBWAY, RAIL, GONDOLA

<details><summary>Détail des trajets</summary>

**Capitole → Aéroport Toulouse-Blagnac** (transit)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 33 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 32 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 26 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 786 ms)
- 2028 : 38 min, 2 corresp., walk 0 min → SUBWAY A (tisseo) → walk 6 min → SUBWAY C (futur) → TRAM Aéroport (futur) → walk 1 min
- 2028 : 36 min, 2 corresp., walk 0 min → SUBWAY A (tisseo) → walk 6 min → SUBWAY C (futur) → TRAM Aéroport (futur) → walk 1 min
- 2028 : 44 min, 1 corresp., walk 18 min → SUBWAY C (futur) → TRAM Aéroport (futur) → walk 1 min
  (réponse en 514 ms)

**Gare Matabiau → Ramonville** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Ramonville [tisseo, 11 arrêt(s), 43.555883, 1.477122]
- actuel : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min
- actuel : 32 min, 0 corresp., walk 14 min → SUBWAY B (tisseo) → walk 2 min
- actuel : 31 min, 0 corresp., walk 1 min → BUS 27 (tisseo) → walk 0 min
  (réponse en 240 ms)
- 2028 : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (futur) → walk 3 min
- 2028 : 32 min, 0 corresp., walk 13 min → SUBWAY B (futur) → walk 3 min
- 2028 : 31 min, 0 corresp., walk 1 min → BUS 27 (tisseo) → walk 0 min
  (réponse en 164 ms)

**Colomiers gare → Labège** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- actuel : 53 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- actuel : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 342 ms)
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
- 2028 : 48 min, 0 corresp., walk 4 min → SUBWAY C (futur) → walk 10 min
  (réponse en 254 ms)

**Gare de Colomiers → Diagora (Labège)** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Diagora [futur, 2 arrêt(s), 43.544148, 1.50968]
- actuel : 53 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf) → walk 8 min
- actuel : 59 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min → BUS 79 (tisseo) → walk 2 min
- actuel : 76 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf) → walk 8 min
  (réponse en 269 ms)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
- 2028 : 38 min, 0 corresp., walk 4 min → SUBWAY C (futur)
  (réponse en 214 ms)

**La Vache (halte Route de Launaguet) → Gare Matabiau** (transit)
- Départ : Route de Launaguet [futur, 2 arrêt(s), 43.633617, 1.434951]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 51 min, 0 corresp., walk 51 min
- actuel : 26 min, 0 corresp., walk 4 min → SUBWAY B (tisseo) → walk 14 min
- actuel : 26 min, 0 corresp., walk 4 min → SUBWAY B (tisseo) → walk 14 min
  (réponse en 157 ms)
- 2028 : 4 min, 0 corresp., RAIL C1 (futur)
- 2028 : 4 min, 0 corresp., RAIL C1 (futur)
  (réponse en 100 ms)

**Gare Matabiau → Labège-La Cadène** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Labège-La Cadène [futur, 2 arrêt(s), 43.53897, 1.520634]
- actuel : 48 min, 2 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- actuel : 24 min, 1 corresp., RAIL K3 (sncf) → walk 3 min → BUS 80 (tisseo) → walk 3 min
- actuel : 27 min, 0 corresp., RAIL K3 (sncf) → walk 18 min
  (réponse en 111 ms)
- 2028 : 27 min, 0 corresp., walk 7 min → SUBWAY C (futur)
- 2028 : 27 min, 0 corresp., walk 7 min → SUBWAY C (futur)
- 2028 : 27 min, 0 corresp., walk 7 min → SUBWAY C (futur)
  (réponse en 95 ms)

**Capitole → Gare Matabiau, marche seule** (walk)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 17 min, 0 corresp., walk 17 min
  (réponse en 15 ms)

**Capitole → Aéroport Toulouse-Blagnac, vélo** (bicycle)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 38 min, 0 corresp., bicycle 38 min
  (réponse en 100 ms)

</details>

### Avertissements

- matabiau-labege-la-cadene / 2028 : aucun itinéraire ne monte ni ne descend à l'arrêt « ^labege la cadene$ » (futur)
