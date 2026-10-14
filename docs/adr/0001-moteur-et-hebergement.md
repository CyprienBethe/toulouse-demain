# ADR 0001 — Moteur d'itinéraires, scénarios, hébergement et construction du graphe

- **Statut** : proposé, à valider par Cyprien
- **Date** : 14 octobre 2026
- **Auteur** : architecte et dev senior back-end
- **Sources** : vérifiées le 14/10/2026, liste numérotée en fin de document ([S1], [S2]…)

## Contexte

Il nous faut un serveur unique et gratuit qui calcule des itinéraires sur Tisséo et les TER de la zone (transports en commun + marche, marche seule, vélo), dans deux scénarios : « actuel » (GTFS officiels) et « 2028 » (actuel + GTFS maison `futur` : ligne C et ligne B prolongée). Le site est statique (GitHub Pages) et appelle ce serveur depuis le navigateur. MVP visé vers le 23 octobre : on prend la solution la plus simple qui marche.

## Décision en bref

| Sujet | Décision | Plan B |
| --- | --- | --- |
| Moteur | **OpenTripPlanner 2.10.0** (image Docker officielle) | MOTIS 2.11 si la mémoire mesurée d'OTP ne tient pas sur le serveur |
| Scénarios | **Un seul graphe** avec les 3 flux ; le scénario « actuel » exclut à chaque requête les agences du flux `futur` | — |
| Hébergement | **Oracle Cloud Always Free**, une instance Ampere A1 (2 OCPU, 12 Go) | **Raspberry Pi** chez Cyprien, même `docker-compose.yml` |
| HTTPS | Sous-domaine gratuit **DuckDNS** + certificat **Let's Encrypt** obtenu automatiquement par **Caddy** | — |
| Graphe | Construit **chaque semaine dans GitHub Actions**, testé, publié en **GitHub Release** ; le serveur le télécharge | Construction sur le serveur (Oracle seulement) |

## 1. Choix du moteur

### Options comparées

| Critère | OpenTripPlanner 2.10.0 | MOTIS 2.11.3 |
| --- | --- | --- |
| Plusieurs GTFS | Oui : `transitFeeds`, chaque flux reçoit un `feedId` qui remplace celui du fichier [S1] | Oui : `timetable.datasets`, une étiquette par jeu de données [S10] |
| GTFS maison | Oui (GTFS standard, même traitement que les autres) | Oui |
| Marche, vélo, TC avec OSM | Oui | Oui (`street_routing`) [S10] |
| Exclure un flux, une agence ou une ligne **par requête** | **Oui** : `planConnection(preferences: {transit: {filters: [{exclude: [{agencies: […]}, {routes: […]}]}]}})` [S2], disponible depuis la 2.8.0 [S3] | **Non** : `/api/v6/plan` ne filtre que par mode (`transitModes`) ; aucun paramètre par jeu de données, agence ou ligne [S11] |
| Mémoire | Gourmand : de moins de 1 Go à plus de 100 Go selon les données ; la Finlande entière dépasse un peu 10 Go [S4]. Zone Tisséo : **à mesurer en CI** | Annoncé « haute performance, faible mémoire » [S9]. Non mesuré |
| API pour un site statique | GraphQL (`POST /otp/gtfs/v1`) [S5] | REST JSON avec spécification OpenAPI et client JS [S9] |
| Maturité | OTP2 utilisé par Entur (Norvège) et Digitransit (Finlande) [S4] ; 2.10.0 publiée le 09/09/2026 [S3] | v2.11.3 (septembre 2026) ; utilisé par Transitous [S9] |
| Documentation | Très complète, configuration documentée paramètre par paramètre [S1] | README, un guide de configuration et l'OpenAPI [S9][S10] |
| Image Docker et ARM | Image officielle Docker Hub, amd64 **et arm64** [S6][S7] | Binaires linux-amd64 et linux-arm64 [S9] |
| Simplicité pour un débutant | Moyenne (Java, GraphQL) | Bonne (un binaire, trois commandes) [S9] |

Autres options (Navitia, Conveyal R5, Valhalla…) : écartées sans étude approfondie, faute de temps dans ce sprint. On ne les réexamine que si OTP et MOTIS échouent tous les deux.

### Décision : OpenTripPlanner

Le critère décisif est le filtre par requête : il permet **un seul graphe et un seul serveur pour les deux scénarios** (voir section 2). Avec MOTIS, il faudrait deux imports, deux processus et deux adresses d'API. Un seul graphe garantit aussi que le comparateur compare deux calculs faits sur exactement le même réseau de rues, les mêmes bus et les mêmes TER : seule la présence des lignes futures change.

**Risque principal** : la mémoire d'OTP. Elle est mesurée à chaque construction en CI (voir le rapport). Si elle dépasse ce que le serveur offre, on bascule sur MOTIS avec deux instances.

## 2. Deux scénarios : deux instances ou un seul graphe ?

| Option | Mémoire | Construction | Exploitation |
| --- | --- | --- | --- |
| A. Deux instances (un graphe par scénario) | ×2 | 2 graphes par semaine | 2 serveurs à surveiller, 2 adresses |
| **B. Un graphe, flux `futur` exclu à la requête** | ×1 | 1 graphe | 1 serveur |

Vérification dans le schéma officiel de l'API GTFS GraphQL d'OTP 2.10.0 [S2] :

- `planConnection` accepte `preferences.transit.filters`, une liste de `TransitFilterInput` avec `include` et `exclude` ;
- un sélecteur (`TransitFilterSelectInput`) désigne des **agences** (`agencies`, format `FeedId:AgencyId`) ou des **lignes** (`routes`) ; il n'existe pas de sélecteur « flux » direct, mais toutes les agences d'un flux sont listées par la requête `feeds { feedId agencies { gtfsId } }` ;
- l'ancienne requête `plan` a un argument `banned` (agences, lignes, courses), mais elle est marquée obsolète : on ne l'utilise pas.

**Décision : option B.** Le scénario « actuel » envoie :

```graphql
preferences: { transit: { filters: [ { exclude: [ { agencies: ["futur:<agency_id>"] } ] } ] } }
```

Le scénario « 2028 » n'envoie aucun filtre, sauf si le data engineer modélise une ligne B complète qui doublonne la ligne B Tisséo : on exclut alors la ligne Tisséo (`exclude_routes` dans `config/scenarios.json`). Les règles sont écrites une seule fois dans `config/scenarios.json` ; le front-end doit envoyer les mêmes filtres. Le CI vérifie qu'aucun itinéraire « actuel » n'utilise le flux `futur`.

Limite connue : les stations futures existent dans le graphe même en scénario « actuel », mais aucun véhicule ne les dessert ; elles n'ont donc pas d'effet sur les trajets (à confirmer par les trajets de référence).

## 3. Hébergement gratuit

### Oracle Cloud Always Free (conditions lues le 14/10/2026)

- **Ressources Ampere A1** : 2 OCPU et 12 Go de mémoire au total, soit 1 500 OCPU-heures et 9 000 Go-heures par mois ; une seule instance peut tout utiliser [S12]. *Attention : c'est moins que les « 4 OCPU / 24 Go » souvent cités ailleurs ; seule la page officielle fait foi.*
- Deux instances AMD « micro » de 1 Go [S12] : trop petites pour OTP.
- 200 Go de stockage bloc (disques de démarrage compris), 10 To de trafic sortant par mois [S12].
- **Carte bancaire exigée** (crédit ou débit, pas de carte prépayée ou virtuelle), pour vérifier l'identité ; Oracle peut faire une pré-autorisation temporaire, sans débit réel [S13].
- **Capacité** : l'erreur « out of host capacity » signale un manque temporaire d'instances A1 dans la région ; il faut réessayer plus tard ou dans un autre domaine de disponibilité. Oracle propose aussi de passer en compte payant (« Pay as You Go ») : les ressources Always Free restent gratuites, seul le dépassement est facturé [S12][S13]. Cela ouvre un risque de facturation : à décider par Cyprien, pas recommandé par défaut.
- **Récupération des instances inactives** : une instance est jugée inactive si, sur 7 jours, l'utilisation CPU (95e centile), réseau **et** mémoire (A1) restent sous 20 % [S12]. Parade prévue : réserver le tas Java dès le démarrage (`-Xms` = `-Xmx` et `-XX:+AlwaysPreTouch`, voir `deploy/.env.example`) pour que la mémoire utilisée reste au-dessus de 20 %. *Hypothèse* : à vérifier dans les métriques de la console Oracle après le déploiement.
- Un **compte** inactif pendant 30 jours peut être suspendu [S13] : se connecter à la console de temps en temps.
- Les instances Always Free doivent être créées dans la **région d'origine** choisie à l'inscription [S12].

### Autres offres

- Google Cloud : une instance e2-micro par mois dans le niveau gratuit [S14] ; non retenue, car c'est la plus petite gamme et OTP demande plusieurs Go (*hypothèse* à confirmer avec la mesure CI).
- Autres clouds (AWS, Azure…) : non vérifiés dans ce sprint ; les offres gratuites limitées dans le temps sont exclues par la règle « zéro euro, sans période d'essai ».

### Plan B : Raspberry Pi chez Cyprien

Même `docker-compose.yml` : les images OTP et Caddy existent en arm64 [S7][S20]. Conditions : système 64 bits, mémoire supérieure au besoin mesuré en CI, ports 80 et 443 redirigés par la box vers le Pi, mise à jour de l'adresse IP chez DuckDNS (`deploy/duckdns-update.sh`). Coûts : l'électricité, et l'achat du Pi si Cyprien n'en a pas. Risques : coupures de la connexion, exposition du réseau domestique (à revoir par l'expert cybersécurité).

**Recommandation** : Oracle A1 (2 OCPU, 12 Go, Ubuntu arm64), en gardant le Pi comme solution de repli.

## 4. HTTPS sans nom de domaine payant

- **DuckDNS** : sous-domaine gratuit `<nom>.duckdns.org`, connexion avec un compte Google, GitHub ou Twitter ; l'adresse IP se met à jour par une simple URL avec un jeton secret ; les enregistrements TXT sont aussi gérés [S15][S16].
- `duckdns.org` figure dans la **Public Suffix List** [S17]. Or Let's Encrypt compte ses limites (50 certificats par domaine enregistré et par 7 jours) par domaine enregistré au sens de cette liste [S18] : notre sous-domaine a donc son propre quota, non partagé avec les autres utilisateurs de DuckDNS.
- **Caddy** obtient et renouvelle seul le certificat Let's Encrypt ; les défis HTTP (port 80) et TLS-ALPN (port 443) sont activés par défaut [S19]. Aucune configuration de certificat n'est à écrire.
- La passerelle Caddy ajoute aussi la limitation de débit (module `caddy-ratelimit`, absent de l'image officielle : on construit une image avec `xcaddy` [S21]), le CORS restreint au site et le refus de toutes les adresses autres que l'API.

## 5. Où construire le graphe ?

| Option | Avantages | Inconvénients |
| --- | --- | --- |
| **GitHub Actions** puis téléchargement par le serveur | Gratuit pour un dépôt public : 4 CPU, 16 Go de mémoire, 14 Go de disque [S22] ; le graphe est **testé avant** d'arriver sur le serveur ; le serveur garde toute sa mémoire pour répondre | Le graphe transite par une release (fichiers de moins de 2 Gio chacun ; ni limite de taille totale ni limite de bande passante [S23]) |
| Sur le serveur | Pas de transfert | Construire demande plus de mémoire que servir (*hypothèse*, les deux valeurs sont mesurées en CI) ; impossible sur un Pi (*hypothèse*) ; pas de test avant mise en ligne |

**Décision : GitHub Actions.** Le workflow `build-graph.yml` tourne chaque lundi, à la demande et sur chaque pull request qui touche la configuration ou les scripts. Il télécharge les données, découpe OpenStreetMap à la zone (extrait Geofabrik Midi-Pyrénées, 346 Mo [S24]), filtre le GTFS SNCF, appelle le script du GTFS futur, construit le graphe, lance OTP dans le runner et calcule les trajets de référence dans les deux scénarios. Sur la branche principale, il publie ensuite le graphe en release (compressé et découpé en morceaux de 1 900 Mio). Sur le serveur, `deploy/update-graph.sh` (tâche planifiée hebdomadaire) télécharge la dernière release, vérifie les sommes de contrôle et redémarre OTP.

Un graphe ne se charge qu'avec la version d'OTP qui l'a construit : la même image (`opentripplanner:2.10.0`) est écrite dans le workflow et dans `docker-compose.yml`. Le CI et `update-graph.sh` vérifient qu'elles sont identiques.

Le graphe ne garde que les services de J−3 à J+35 (`transitServiceStart` / `transitServiceEnd` [S1]). *Hypothèse* : Tisséo publie les 3 semaines à venir, le GTFS SNCF couvre 151 jours [S25] ; au-delà de 5 semaines, les TER seuls n'ont pas d'intérêt et coûtent de la mémoire.

### Lire les résultats sans accès aux journaux

Depuis notre environnement, on voit l'état des vérifications d'un commit, les commentaires de PR et les fichiers des branches, mais ni les journaux ni les artefacts des workflows. Chaque exécution publie donc son rapport (succès de chaque étape, durée de construction, mémoire, taille du graphe, trajets, fin des journaux en cas d'échec) :

1. en **commentaire de la pull request** (un seul commentaire, mis à jour à chaque exécution) ;
2. sur la branche **`rapports`** : `latest.md` (dernière exécution), `by-branch/<branche>.md`, et l'historique dans `reports/`.

Il apparaît aussi dans le résumé de l'exécution, sur la page GitHub Actions.

## 6. Contrat d'API initial pour le front-end

- `POST https://<API_DOMAIN>/otp/gtfs/v1`, corps JSON GraphQL, requête `planConnection` [S2][S5].
- Scénario : au démarrage, le site lit `{ feeds { feedId agencies { gtfsId } } }`, puis envoie pour « actuel » le filtre d'exclusion des agences du flux `futur` (règles de `config/scenarios.json`).
- Marche seule : `modes: {directOnly: true, direct: [WALK]}` ; vélo : `direct: [BICYCLE]` ; transports en commun : `modes` omis.
- `GET https://<API_DOMAIN>/health` : 200 quand le graphe est chargé (API Actuator d'OTP [S8]).
- CORS limité à l'origine du site (`SITE_ORIGIN`) ; 30 requêtes par minute et par adresse IP, 600 au total (*hypothèses*, réglables dans `.env`).
- Exemple complet : `PLAN_QUERY` dans `scripts/reference_trips.py`.

## 7. Ce qui n'est pas testé

- **Rien n'a encore tourné dans GitHub Actions** : durée de construction, mémoire, taille du graphe et résultats des trajets sont « à mesurer en CI » au premier lancement.
- Les URL de téléchargement n'ont pas pu être testées depuis notre environnement. Point d'attention : la fiche transport.data.gouv.fr n° 83195 décrit aujourd'hui l'export **NeTEx** de la SNCF, pas le GTFS [S26] ; l'URL du GTFS utilisée est celle qu'indique la fiche data.gouv.fr « Horaires SNCF » [S25].
- `docker-compose.yml` est validé (`docker compose config`), mais il n'a pas été démarré ; le `Caddyfile` sera validé par le workflow `checks.yml` avec la vraie image Caddy.
- `update-graph.sh` et `duckdns-update.sh` n'ont pas été testés.
- Scripts Python testés sur des données synthétiques ; `run_otp.py` testé avec un faux `docker`.
- Versions : osmium vient d'apt (non épinglé, version écrite dans le rapport) ; images Docker épinglées par étiquette, pas par empreinte (`digest`), car Docker Hub n'est pas joignable depuis notre environnement.

## Ce que Cyprien doit faire

1. **Valider** cet ADR : OTP, un seul graphe, Oracle avec le Pi en repli.
2. Après la fusion de `sprint-0` dans `main` : onglet **Actions** du dépôt → « Construire le graphe » → **Run workflow**. Lire ensuite `latest.md` sur la branche `rapports`.
3. **Préparer** : une carte bancaire de crédit ou de débit (ni prépayée, ni virtuelle), un numéro de téléphone, une paire de clés SSH (on t'expliquera comment la créer).
4. **Créer le compte Oracle Cloud** (offre Free Tier), choisir une région d'origine en Europe, puis créer une instance `VM.Standard.A1.Flex` de 2 OCPU et 12 Go sous Ubuntu. En cas d'« out of host capacity », réessayer plus tard. Ouvrir les ports 80 et 443.
5. **Créer un compte DuckDNS** (avec GitHub), choisir le sous-domaine et le faire pointer vers l'adresse IP publique de l'instance. Le jeton DuckDNS est un secret : ne jamais le committer.
6. Sur le serveur, avec notre aide : installer Docker, cloner le dépôt, `cp deploy/.env.example deploy/.env`, renseigner `.env`, lancer `./update-graph.sh` puis `docker compose up -d`, et ajouter la tâche planifiée hebdomadaire.
7. **Décider** : le nom du sous-domaine ; l'acceptation (ou non) de passer en « Pay as You Go » en cas de manque de capacité ; les limites de débit.

## Ce qu'il faut retenir

- Le moteur est OpenTripPlanner : un seul serveur sert les deux scénarios ; « actuel » masque simplement les lignes futures à chaque requête.
- Le serveur gratuit est une machine Oracle (2 processeurs, 12 Go), avec un Raspberry Pi en secours ; Oracle exige une carte bancaire mais ne débite rien dans les limites gratuites.
- Le graphe est fabriqué et testé chaque semaine par GitHub Actions, puis téléchargé par le serveur.
- L'adresse HTTPS gratuite vient de DuckDNS et de Let's Encrypt, gérés automatiquement par Caddy.
- La mémoire réellement nécessaire sera connue au premier rapport du CI : c'est elle qui confirmera (ou non) ces choix.

## Sources

- [S1] OTP 2.10.0, *Build Configuration* : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/BuildConfiguration.md
- [S2] OTP 2.10.0, schéma de l'API GTFS GraphQL (`planConnection`, `TransitFilterInput`, `InputBanned`, `Feed`) : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/application/src/main/resources/org/opentripplanner/apis/gtfs/schema.graphqls
- [S3] OTP, *Changelog* (2.10.0 du 09/09/2026 ; 2.8.0 : « Transit filters for GTFS API's planConnection #6668 ») : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/Changelog.md
- [S4] OTP, *System Requirements* : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/System-Requirements.md
- [S5] OTP, *GTFS GraphQL API* : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/apis/GTFS-GraphQL-API.md
- [S6] OTP, *Container Image* : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/Container-Image.md
- [S7] OTP, `pom.xml` (image Jib amd64 et arm64, base `eclipse-temurin:25-jre`) : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/pom.xml
- [S8] OTP, *Actuator API* : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/sandbox/ActuatorAPI.md
- [S9] MOTIS v2.11.3, README : https://github.com/motis-project/motis/blob/v2.11.3/README.md
- [S10] MOTIS v2.11.3, *Advanced Setups* : https://github.com/motis-project/motis/blob/v2.11.3/docs/setup.md
- [S11] MOTIS v2.11.3, `openapi.yaml` (`/api/v6/plan`) : https://github.com/motis-project/motis/blob/v2.11.3/openapi.yaml
- [S12] Oracle, *Always Free Resources* : https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- [S13] Oracle, *Free Tier FAQ* : https://www.oracle.com/cloud/free/faq/
- [S14] Google Cloud, *Free Tier* : https://cloud.google.com/free
- [S15] DuckDNS : https://www.duckdns.org/
- [S16] DuckDNS, *spec* (mise à jour par URL, enregistrements TXT) : https://www.duckdns.org/spec.jsp
- [S17] Public Suffix List (entrée `duckdns.org`) : https://github.com/publicsuffix/list/blob/main/public_suffix_list.dat
- [S18] Let's Encrypt, *Rate Limits* : https://letsencrypt.org/docs/rate-limits/
- [S19] Caddy, *Automatic HTTPS* : https://caddyserver.com/docs/automatic-https
- [S20] Images officielles Caddy (étiquettes 2.11.7, architectures) : https://github.com/caddyserver/caddy-docker/blob/master/library/caddy
- [S21] Module de limitation de débit pour Caddy : https://github.com/mholt/caddy-ratelimit
- [S22] GitHub, *GitHub-hosted runners* : https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- [S23] GitHub, *About releases* : https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- [S24] Geofabrik, extraits France : https://download.geofabrik.de/europe/france.html
- [S25] data.gouv.fr, *Horaires SNCF* (URL du GTFS, licence ODbL, 151 jours) : https://www.data.gouv.fr/datasets/horaires-sncf
- [S26] transport.data.gouv.fr, ressource 83195 : https://transport.data.gouv.fr/resources/83195
- [S27] data.gouv.fr, *Tisséo — réseau de transport urbain toulousain* : https://www.data.gouv.fr/datasets/tisseo-reseau-transport-urbain-toulousain
