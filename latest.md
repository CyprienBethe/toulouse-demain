<!-- toulouse-demain:graph-report -->
## Rapport de construction du graphe : ÉCHEC

- Date : 2026-10-14 06:10 UTC
- Événement : `pull_request`, branche `1/merge`, commit `3f2e1ba`
- Image OTP : `docker.io/opentripplanner/opentripplanner:2.10.0`
- Exécution : https://github.com/CyprienBethe/toulouse-demain/actions/runs/38520238846
- Durée depuis le début du workflow : 4 min 02 s

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
| Trajets de référence | ÉCHEC |

### Données

| Source | Taille | SHA-256 (début) | Last-Modified |
| --- | --- | --- | --- |
| tisseo | 16,00 Mo | `c8cee6784dec` | ? |
| sncf | 5,48 Mo | `a2456c6e95a1` | Tue, 13 Oct 2026 19:46:43 GMT |
| osm | 362,90 Mo | `503210075995` | Tue, 13 Oct 2026 23:44:10 GMT |

Zone (rectangle WGS84 min_lon,min_lat,max_lon,max_lat) : `1.02706,43.30141,1.81453,43.83973` — calculée sur 5721 arrêts Tisséo + 10.0 km de marge.
OpenStreetMap découpé : 362,90 Mo → 82,60 Mo (osmium version 1.16.0).
GTFS SNCF filtré : 1373 courses, 22 lignes, 121 arrêts gardés ; stop_times 511818 → 6937 lignes ; route_type {'2': 20, '3': 2}.
GTFS futur : 318,95 ko, 2 lignes (C, B), 47 arrêts, 2496 courses.

### Moteur OpenTripPlanner (mesures de cette exécution)

| Mesure | Valeur |
| --- | --- |
| Durée de construction du graphe | 2 min 07 s |
| Mémoire max du conteneur pendant la construction (-Xmx12g) | 4,22 Go |
| Tas Java vivant max après GC, construction | 1,46 Go |
| Taille de graph.obj | 84,45 Mo |
| Démarrage du serveur (chargement du graphe) | 6 s |
| Mémoire du conteneur serveur prêt (-Xmx6g) | 1,14 Go |
| Mémoire du conteneur serveur après les trajets | 1,17 Go |
| Tas Java vivant max après GC, serveur | 865,08 Mo |

### Trajets de référence (départ 2026-10-20T08:30:00+02:00)

| Trajet | Actuel | 2028 | Écart |
| --- | --- | --- | --- |
| Capitole → Aéroport Toulouse-Blagnac | — | — |  |
| Gare Matabiau → Ramonville | — | — |  |
| Colomiers gare → Labège | — | — |  |
| Capitole → Gare Matabiau, marche seule | 17 min | — |  |
| Capitole → Aéroport Toulouse-Blagnac, vélo | 38 min | — |  |

<details><summary>Détail des trajets</summary>

**Capitole → Aéroport Toulouse-Blagnac** (transit)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : aucun itinéraire ['Exception while fetching data (/planConnection) : Cannot invoke "java.util.Map.containsKey(Object)" because "modesArgs" is null']
  (réponse en 40 ms)
- 2028 : aucun itinéraire ['Exception while fetching data (/planConnection) : Cannot invoke "java.util.Map.containsKey(Object)" because "modesArgs" is null']
  (réponse en 9 ms)

**Gare Matabiau → Ramonville** (transit)
- Départ : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- Arrivée : Ramonville [tisseo, 11 arrêt(s), 43.555883, 1.477122]
- actuel : aucun itinéraire ['Exception while fetching data (/planConnection) : Cannot invoke "java.util.Map.containsKey(Object)" because "modesArgs" is null']
  (réponse en 8 ms)
- 2028 : aucun itinéraire ['Exception while fetching data (/planConnection) : Cannot invoke "java.util.Map.containsKey(Object)" because "modesArgs" is null']
  (réponse en 8 ms)

**Colomiers gare → Labège** (transit)
- Départ : Colomiers [sncf, 3 arrêt(s), 43.603734, 1.334221]
- Arrivée : Labège Innopole [sncf, 3 arrêt(s), 43.547467, 1.512964]
- actuel : aucun itinéraire ['Exception while fetching data (/planConnection) : Cannot invoke "java.util.Map.containsKey(Object)" because "modesArgs" is null']
  (réponse en 8 ms)
- 2028 : aucun itinéraire ['Exception while fetching data (/planConnection) : Cannot invoke "java.util.Map.containsKey(Object)" because "modesArgs" is null']
  (réponse en 8 ms)

**Capitole → Gare Matabiau, marche seule** (walk)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Toulouse Matabiau [sncf, 4 arrêt(s), 43.611206, 1.453616]
- actuel : 17 min, 0 corresp., walk 17 min
  (réponse en 121 ms)

**Capitole → Aéroport Toulouse-Blagnac, vélo** (bicycle)
- Départ : Capitole [tisseo, 3 arrêt(s), 43.604465, 1.445537]
- Arrivée : Aéroport [tisseo, 4 arrêt(s), 43.631247, 1.374752]
- actuel : 38 min, 0 corresp., bicycle 38 min
  (réponse en 188 ms)

</details>

### Contrôles en échec

- capitole-aeroport / actuel : erreur GraphQL
- capitole-aeroport / actuel : aucun itinéraire
- capitole-aeroport / 2028 : erreur GraphQL
- capitole-aeroport / 2028 : aucun itinéraire
- matabiau-ramonville / actuel : erreur GraphQL
- matabiau-ramonville / actuel : aucun itinéraire
- matabiau-ramonville / 2028 : erreur GraphQL
- matabiau-ramonville / 2028 : aucun itinéraire
- colomiers-labege / actuel : erreur GraphQL
- colomiers-labege / actuel : aucun itinéraire
- colomiers-labege / 2028 : erreur GraphQL
- colomiers-labege / 2028 : aucun itinéraire

### Fin des journaux des étapes en échec

<details><summary>Trajets de référence</summary>

```
FAIL: capitole-aeroport / actuel : erreur GraphQL
FAIL: capitole-aeroport / actuel : aucun itinéraire
FAIL: capitole-aeroport / 2028 : erreur GraphQL
FAIL: capitole-aeroport / 2028 : aucun itinéraire
FAIL: matabiau-ramonville / actuel : erreur GraphQL
FAIL: matabiau-ramonville / actuel : aucun itinéraire
FAIL: matabiau-ramonville / 2028 : erreur GraphQL
FAIL: matabiau-ramonville / 2028 : aucun itinéraire
FAIL: colomiers-labege / actuel : erreur GraphQL
FAIL: colomiers-labege / actuel : aucun itinéraire
FAIL: colomiers-labege / 2028 : erreur GraphQL
FAIL: colomiers-labege / 2028 : aucun itinéraire
5 reference trips computed, 12 failure(s)
```
</details>
