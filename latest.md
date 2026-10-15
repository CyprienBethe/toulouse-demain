<!-- toulouse-demain:graph-report -->
## Rapport de construction du graphe : SUCCÈS PARTIEL (réseau actuel seulement, GTFS futur en échec)

- Date : 2026-10-15 21:22 UTC
- Événement : `pull_request`, branche `3/merge`, commit `6e7abc3`
- Image OTP : `docker.io/opentripplanner/opentripplanner:2.10.0`
- Exécution : https://github.com/CyprienBethe/toulouse-demain/actions/runs/38809009148
- Durée depuis le début du workflow : 3 min 11 s

### Étapes

| Étape | Résultat |
| --- | --- |
| Téléchargement des sources | réussi |
| Calcul de la zone | réussi |
| Découpage OpenStreetMap | réussi |
| Filtrage du GTFS SNCF | réussi |
| Construction du GTFS futur (data engineer) | ÉCHEC (toléré : graphe construit sans le flux futur) |
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
GTFS futur : **absent** (`build/gtfs/futur.gtfs.zip` non produit).

### Moteur OpenTripPlanner (mesures de cette exécution)

| Mesure | Valeur |
| --- | --- |
| Durée de construction du graphe | 1 min 26 s |
| Mémoire max du conteneur pendant la construction (-Xmx12g) | 4,42 Go |
| Tas Java vivant max après GC, construction | 1,46 Go |
| Taille de graph.obj | 83,48 Mo |
| Démarrage du serveur (chargement du graphe) | 6 s |
| Mémoire du conteneur serveur prêt (-Xmx6g) | 1,09 Go |
| Mémoire du conteneur serveur après les trajets | 1,16 Go |
| Tas Java vivant max après GC, serveur | 723,52 Mo |

### Trajets de référence (départ 2026-10-20T08:30:00+02:00)

| Trajet | Actuel | 2028 | Écart |
| --- | --- | --- | --- |
| Capitole → Aéroport Toulouse-Blagnac | 26 min | 26 min | identique |
| Gare Matabiau → Ramonville | 21 min | 21 min | identique |
| Colomiers gare → Labège | 45 min | 45 min | identique |
| Gare de Colomiers → Diagora (Labège) | 45 min | 45 min | identique |
| La Vache (halte Route de Launaguet) → Gare Matabiau | 27 min | 27 min | identique |
| Gare Matabiau → Labège-La Cadène | 9 min | 9 min | identique |
| Capitole → Gare Matabiau, marche seule | 17 min | — |  |
| Capitole → Aéroport Toulouse-Blagnac, vélo | 38 min | — |  |

- Scénario actuel : 0 agence(s) exclue(s), lignes exclues : aucune
- Scénario 2028 : 0 agence(s) exclue(s), lignes exclues : aucune
- Modes présents dans le graphe : BUS, GONDOLA, RAIL, SUBWAY, TRAM ; modes demandés : BUS, TRAM, SUBWAY, RAIL, GONDOLA

<details><summary>Détail des trajets</summary>

**Capitole → Aéroport Toulouse-Blagnac** (transit)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 33 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 32 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- actuel : 26 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 451 ms)
- 2028 : 33 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- 2028 : 32 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
- 2028 : 26 min, 0 corresp., walk 8 min → BUS AERO (tisseo) → walk 0 min
  (réponse en 166 ms)

**Gare Matabiau → Ramonville** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Ramonville [tisseo, 11 arrêt(s), 43.555883, 1.477122]
- actuel : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min
- actuel : 32 min, 0 corresp., walk 14 min → SUBWAY B (tisseo) → walk 2 min
- actuel : 31 min, 0 corresp., walk 1 min → BUS 27 (tisseo) → walk 0 min
  (réponse en 191 ms)
- 2028 : 21 min, 1 corresp., RAIL K5 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 2 min
- 2028 : 32 min, 0 corresp., walk 14 min → SUBWAY B (tisseo) → walk 2 min
- 2028 : 31 min, 0 corresp., walk 1 min → BUS 27 (tisseo) → walk 0 min
  (réponse en 204 ms)

**Colomiers gare → Labège** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- actuel : 53 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- actuel : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 324 ms)
- 2028 : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- 2028 : 53 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- 2028 : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 260 ms)

**Gare de Colomiers → Diagora (Labège)** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- actuel : 53 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- actuel : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 236 ms)
- 2028 : 45 min, 1 corresp., RAIL C6 (sncf) → RAIL K3 (sncf)
- 2028 : 53 min, 2 corresp., RAIL C6 (sncf) → walk 4 min → SUBWAY B (tisseo) → walk 4 min → BUS 80 (tisseo) → walk 3 min
- 2028 : 68 min, 1 corresp., RAIL C6 (sncf) → RAIL C3 (sncf)
  (réponse en 242 ms)

**La Vache (halte Route de Launaguet) → Gare Matabiau** (transit)
- Départ : La Vache [tisseo, 11 arrêt(s), 43.633586, 1.434678]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 51 min, 0 corresp., walk 51 min
- actuel : 27 min, 0 corresp., walk 4 min → SUBWAY B (tisseo) → walk 14 min
- actuel : 27 min, 0 corresp., walk 4 min → SUBWAY B (tisseo) → walk 14 min
  (réponse en 116 ms)
- 2028 : 51 min, 0 corresp., walk 51 min
- 2028 : 27 min, 0 corresp., walk 4 min → SUBWAY B (tisseo) → walk 14 min
- 2028 : 27 min, 0 corresp., walk 4 min → SUBWAY B (tisseo) → walk 14 min
  (réponse en 100 ms)

**Gare Matabiau → Labège-La Cadène** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : 9 min, 0 corresp., RAIL K3 (sncf)
  (réponse en 90 ms)
- 2028 : 9 min, 0 corresp., RAIL K3 (sncf)
  (réponse en 75 ms)

**Capitole → Gare Matabiau, marche seule** (walk)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 17 min, 0 corresp., walk 17 min
  (réponse en 13 ms)

**Capitole → Aéroport Toulouse-Blagnac, vélo** (bicycle)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 38 min, 0 corresp., bicycle 38 min
  (réponse en 101 ms)

</details>

### Avertissements

- scénario actuel : le flux futur est absent du graphe (toléré : les deux scénarios sont alors identiques)
- capitole-aeroport / 2028 : contrôle ignoré, le flux futur est absent du graphe
- capitole-aeroport / 2028 : le trajet le plus rapide n'emprunte pas la ligne Aéroport (futur)
- colomiers-labege / 2028 : le trajet le plus rapide n'emprunte pas la ligne C (futur)
- colomiers-diagora / 2028 : le trajet le plus rapide n'emprunte pas la ligne C (futur)
- launaguet-matabiau / 2028 : contrôle ignoré, le flux futur est absent du graphe
- matabiau-labege-la-cadene / 2028 : contrôle ignoré, le flux futur est absent du graphe

### Fin des journaux des étapes en échec

<details><summary>Construction du GTFS futur (data engineer)</summary>

```

[notice] A new release of pip is available: 25.0.1 -> 26.2.1
[notice] To update, run: python -m pip install --upgrade pip
Stations trouvées dans OSM : 26/28 ; rapport : build/futur-osm/rapport_osm.md
ERREUR : halte TER « Route de Launaguet » : la gare voisine « Lalande-Église » n'est desservie par aucun train du GTFS SNCF sncf.gtfs.zip. Corrigez « entre » dans parametres.yaml.
```
</details>
