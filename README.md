# Toulouse Demain

Site web gratuit de calcul d'itinéraires sur le réseau Tisséo (114 communes) et les TER de la zone : transports en commun avec marche, marche seule ou vélo. Sa fonction phare : comparer un même trajet **aujourd'hui** et **en 2028**, avec la ligne C du métro et la ligne B prolongée, pour voir le temps gagné.

> Le scénario 2028 est une **projection** : les lignes futures sont simulées à partir de chiffres publics, sur le calendrier actuel. Les durées sont indicatives.

## Comment ça marche

```
 Données ouvertes            GitHub Actions (chaque lundi)                 Serveur (Oracle Cloud gratuit)
 ─────────────────           ──────────────────────────────                ─────────────────────────────
 GTFS Tisséo      ──┐        1. télécharger                                 Caddy (HTTPS, limite de débit, CORS)
 GTFS SNCF        ──┼──────▶ 2. découper OSM, filtrer SNCF à la zone          │
 OpenStreetMap    ──┘        3. construire le GTFS « futur » (ligne C, B)     ▼
                             4. construire le graphe OpenTripPlanner  ──────▶ OpenTripPlanner (un seul graphe)
                             5. tester des trajets de référence      release   ▲
                             6. publier le rapport et le graphe                │  requêtes GraphQL
                                                                     Site statique, à venir au sprint 1 (GitHub Pages, MapLibre)
```

- **Moteur** : [OpenTripPlanner](https://www.opentripplanner.org/) 2.10.0. Un seul graphe contient trois flux GTFS : `tisseo`, `sncf` et `futur`. Le scénario « actuel » exclut simplement les lignes du flux `futur` à chaque requête. Les raisons de ces choix sont dans [docs/adr/0001-moteur-et-hebergement.md](docs/adr/0001-moteur-et-hebergement.md).
- **Zone** : le rectangle qui englobe tous les arrêts Tisséo, plus 10 km de marge (`config/zone.json`). Il sert à découper OpenStreetMap et à ne garder du GTFS SNCF national que les trains qui desservent au moins deux gares de la zone.
- **Rapport** : chaque construction publie un rapport (étapes, durée, mémoire, taille du graphe, trajets de référence dans les deux scénarios) en commentaire de pull request et sur la branche [`rapports`](../../tree/rapports) (`latest.md`).

## Structure du dépôt

| Chemin | Contenu |
| --- | --- |
| `config/` | Sources de données, zone, scénarios, trajets de référence (JSON) |
| `otp/` | Configuration d'OpenTripPlanner : construction (`build-config.json`), routage (`router-config.json`), fonctionnalités (`otp-config.json`) |
| `scripts/` | Pipeline de données : `download_sources.py`, `compute_zone.py`, `clip_osm.sh`, `filter_gtfs_sncf.py`, `run_otp.py`, `reference_trips.py`, `write_report.py`, `publish_report.sh`, `package_graph.sh` ; `build_gtfs_futur.py` et `extract_futur_osm.py` (GTFS des lignes futures, par le data engineer) ; tests du pipeline dans `scripts/tests/` |
| `data/futur/` | Données sources des lignes futures (stations, hypothèses) |
| `.github/workflows/` | `build-graph.yml` (construction et test du graphe), `checks.yml` (vérifications rapides) |
| `deploy/` | Serveur : `docker-compose.yml`, `Caddyfile`, `caddy/Dockerfile`, `.env.example`, `update-graph.sh`, `duckdns-update.sh` |
| `docs/` | Décisions d'architecture (`adr/`), parcours et maquettes (`ux/`), équipe (`equipe/`) |

Dépendances : Python 3.12 et `osmium-tool`. Les scripts du pipeline de l'architecte n'utilisent que la bibliothèque standard ; les scripts du GTFS futur ont des dépendances externes, aux versions épinglées dans `scripts/requirements.txt` (le workflow les installe dans un environnement virtuel). Tests du pipeline : `python -m unittest discover -s scripts/tests`.

## Lancer la construction du graphe

Tout le travail sur les données tourne dans GitHub Actions (le dépôt est public, les runners sont gratuits) :

- automatiquement chaque lundi à 03 h 17 UTC ;
- à la demande : onglet **Actions** → **Construire le graphe** → **Run workflow** ;
- sur chaque pull request qui modifie `otp/`, `config/`, `scripts/` ou `data/futur/`.

Sur la branche principale, le graphe testé est publié en **release** GitHub (`graph-AAAAMMJJ-N`) ; les 4 dernières sont conservées. Si le GTFS futur ne peut pas être construit, le graphe du réseau actuel est quand même testé et publié (« succès partiel » dans le rapport). La release contient aussi, pour le front-end, `scenario-filters.json` (filtres exacts à envoyer pour chaque scénario) et `scenario-2028.json` (lignes Tisséo remplacées en 2028).

En local (Linux, Docker et `osmium-tool` installés), les étapes sont celles du workflow, dans le même ordre ; les fichiers produits vont dans `build/` (ignoré par git).

## Déploiement du serveur

Sur une machine Linux 64 bits (Oracle Cloud A1 ou Raspberry Pi) avec Docker :

```bash
git clone https://github.com/CyprienBethe/toulouse-demain.git
cd toulouse-demain/deploy
cp .env.example .env       # puis renseigner API_DOMAIN, SITE_ORIGIN et la mémoire
./update-graph.sh          # télécharge le dernier graphe publié par GitHub Actions
docker compose up -d       # démarre OpenTripPlanner et Caddy (HTTPS automatique)
curl https://<API_DOMAIN>/health
```

Mise à jour hebdomadaire (après la construction du lundi), avec `crontab -e` :

```
0 7 * * 1 cd /home/<utilisateur>/toulouse-demain/deploy && ./update-graph.sh >> update-graph.log 2>&1
```

Ports à ouvrir : 80 et 443. Aucun secret n'est versionné : `.env` reste sur le serveur.

## API

`POST https://<API_DOMAIN>/otp/gtfs/v1` : [API GTFS GraphQL d'OpenTripPlanner](https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/apis/GTFS-GraphQL-API.md), requête `planConnection`. Le contrat (scénarios, modes, limites) est décrit dans la section 6 de l'ADR 0001 ; un exemple de requête se trouve dans `scripts/reference_trips.py`.

## Licences et attribution

- **Code** : licence MIT (voir [LICENSE](LICENSE)).
- **Données** : sous licence [ODbL](https://opendatacommons.org/licenses/odbl/). Les données dérivées (GTFS filtrés, GTFS des lignes futures, graphe) sont aussi publiées sous ODbL.
  - Horaires du réseau urbain : **Tisséo**, [data.gouv.fr](https://www.data.gouv.fr/datasets/tisseo-reseau-transport-urbain-toulousain).
  - Horaires TER, Intercités et TGV : **SNCF**, [data.gouv.fr](https://www.data.gouv.fr/datasets/horaires-sncf).
  - Rues, chemins et pistes cyclables : **© les contributeurs d'OpenStreetMap**, [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright), extrait [Geofabrik](https://download.geofabrik.de/europe/france.html).
- Ces attributions doivent rester visibles sur le site, sur la carte.

## Ce qu'il faut retenir

- Chaque lundi, GitHub Actions fabrique gratuitement le « graphe » (le réseau complet préparé pour le calcul), le teste et le publie.
- Un seul serveur OpenTripPlanner répond aux deux scénarios ; « aujourd'hui » cache simplement les lignes futures.
- Le serveur ne fait que télécharger le graphe et répondre aux requêtes du site, derrière Caddy qui gère le HTTPS.
- Le rapport de chaque construction se lit sur la branche `rapports` (fichier `latest.md`).
