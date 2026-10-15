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
                                                                     Site statique site/ (GitHub Pages, MapLibre)
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
| `site/` | Le site statique (carte, recherche, comparateur 2028) et ses tests ; voir [site/README.md](site/README.md) |
| `.github/workflows/` | `build-graph.yml` (construction et test du graphe), `checks.yml` (vérifications rapides), `pages.yml` (publication du site sur GitHub Pages) |
| `deploy/` | Serveur : `bootstrap.sh` (installation complète), `docker-compose.yml`, `Caddyfile`, `caddy/Dockerfile`, `.env.example`, `update-graph.sh`, `duckdns-update.sh` |
| `docs/` | Décisions d'architecture (`adr/`), guide de création du serveur (`guide-serveur-oracle.md`), parcours et maquettes (`ux/`), équipe (`equipe/`) |

Dépendances : Python 3.12 et `osmium-tool`. Les scripts du pipeline de l'architecte n'utilisent que la bibliothèque standard ; les scripts du GTFS futur ont des dépendances externes, aux versions épinglées dans `scripts/requirements.txt` (le workflow les installe dans un environnement virtuel). Tests du pipeline : `python -m unittest discover -s scripts/tests`.

## Lancer la construction du graphe

Tout le travail sur les données tourne dans GitHub Actions (le dépôt est public, les runners sont gratuits) :

- automatiquement chaque lundi à 03 h 17 UTC ;
- à la demande : onglet **Actions** → **Construire le graphe** → **Run workflow** ;
- sur chaque pull request qui modifie `otp/`, `config/`, `scripts/` ou `data/futur/`.

Sur la branche principale, le graphe testé est publié en **release** GitHub (`graph-AAAAMMJJ-N`) ; les 4 dernières sont conservées. Si le GTFS futur ne peut pas être construit, le graphe du réseau actuel est quand même testé et publié (« succès partiel » dans le rapport). La release contient aussi, pour le front-end, `scenario-filters.json` (filtres exacts à envoyer pour chaque scénario), `scenario-2028.json` (lignes Tisséo remplacées en 2028) et `demo-responses.json` (réponses brutes d'OTP aux trajets de référence en transports en commun, pour le mode démonstration du site ; aussi sur la branche `rapports`, dossier `latest-files/`). Le contrat de `demo-responses.json` est décrit en tête de `scripts/reference_trips.py`.

En local (Linux, Docker et `osmium-tool` installés), les étapes sont celles du workflow, dans le même ordre ; les fichiers produits vont dans `build/` (ignoré par git).

## Déploiement du serveur

Pas à pas, de la création du compte Oracle à la mise en ligne du site : [docs/guide-serveur-oracle.md](docs/guide-serveur-oracle.md).

Sur une machine Ubuntu 24.04 (Oracle Cloud A1, ARM64), une seule commande, lancée depuis le compte habituel :

```bash
curl -fsSLO https://raw.githubusercontent.com/CyprienBethe/toulouse-demain/main/deploy/bootstrap.sh && sudo bash bootstrap.sh
```

`deploy/bootstrap.sh` clone le dépôt dans `~/toulouse-demain` et crée `deploy/.env` en **demandant** le sous-domaine et le jeton DuckDNS (saisie masquée). Il active ensuite les mises à jour de sécurité automatiques, n'autorise plus que les clés SSH et ouvre les ports 80 et 443 dans le pare-feu local. Il installe Docker depuis le dépôt officiel, télécharge le dernier graphe (`update-graph.sh`), lance `docker compose up -d` et installe deux minuteurs systemd : le graphe chaque lundi vers 06 h 30 UTC, DuckDNS toutes les 30 minutes. Il se relance sans risque : il saute ce qui est déjà fait et applique un `git pull`.

À la main (autre système) : `cp deploy/.env.example deploy/.env`, renseigner `.env`, puis `deploy/update-graph.sh` et `docker compose up -d` dans `deploy/`.

Ports à ouvrir : 80 et 443 (TCP), dans la liste de sécurité Oracle et sur la machine. Aucun secret n'est versionné : `.env` reste sur le serveur (droits 600).

## API

Seules ces adresses sont publiques ; tout le reste répond 404 (interface de débogage d'OTP, autres API, actuator) :

- `POST https://<API_DOMAIN>/otp/gtfs/v1` : [API GTFS GraphQL d'OpenTripPlanner](https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/apis/GTFS-GraphQL-API.md), requête `planConnection` ;
- `GET https://<API_DOMAIN>/meta/scenario-filters.json` et `/meta/scenario-2028.json` : les fichiers de la release installée sur le serveur.

CORS limité à `https://cyprienbethe.github.io`. Le contrat (scénarios, modes, limites) est décrit dans la section 6 de l'ADR 0001 ; un exemple de requête se trouve dans `scripts/reference_trips.py` (`PLAN_QUERY`).

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
