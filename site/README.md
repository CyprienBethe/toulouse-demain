# Le site de Toulouse Demain

Le site calcule un trajet en transports en commun (avec la marche), à pied ou à vélo, sur le réseau d'aujourd'hui ou sur le réseau 2028 (ligne C et ligne B prolongée). En 2028, chaque trajet affiche une double barre qui le compare au meilleur trajet d'aujourd'hui. Il est publié sur `https://cyprienbethe.github.io/toulouse-demain/`.

Spécification : `docs/ux/parcours.md` (écrans, accessibilité, direction « Pastel et brique », décisions de Cyprien) et la maquette « Direction B ».

## Lancer le site sur son ordinateur

Il faut seulement Python 3 (déjà installé sur Mac et Linux) :

```bash
cd site
python3 -m http.server 8000
```

puis ouvrir `http://localhost:8000/`. Ouvrir `index.html` en double-cliquant ne marche pas : le navigateur refuse de charger des modules JavaScript depuis un fichier local.

Pour voir le **mode démonstration** sans serveur, copier les données d'essai **synthétiques** à l'endroit où le site publié aura les vraies (ce fichier est ignoré par git, ne jamais le committer) :

```bash
mkdir -p demo && cp tests/fixtures/synthetic-demo-responses.json demo/demo-responses.json
```

puis ouvrir `http://localhost:8000/?demo=1`.

## La seule chose à régler : l'adresse du serveur

Dans `config.js`, remplacer `https://SOUS-DOMAINE.duckdns.org` par l'adresse réelle du serveur (par exemple `https://toulouse-demain.duckdns.org`, sans `/` final). Tant que la valeur d'exemple est là, le site affiche « Le calculateur n'est pas encore branché » et propose la démonstration.

Si un jour le serveur n'est plus sous `*.duckdns.org`, modifier aussi la ligne `connect-src` de la politique de sécurité dans `index.html` (un test vérifie que les deux concordent).

Contrat avec le serveur (préparé par l'architecte) :

| Appel | Usage |
| --- | --- |
| `POST {API}/otp/gtfs/v1` | API GraphQL d'OpenTripPlanner 2.10.0, requête `planConnection` (`PLAN_QUERY` dans `js/otp.js`) |
| `GET {API}/meta/scenario-filters.json` | Filtres de chaque scénario, avec les vrais identifiants d'agences et de lignes |

Si le serveur ne donne pas `scenario-filters.json`, le site prend la copie de `data/scenario-filters.json`, ajoutée à la publication depuis la dernière release `graph-*`.

## Ce qu'il y a dans ce dossier

| Chemin | Rôle |
| --- | --- |
| `index.html` | La page : sélecteur de scénario, bandeau « projection », formulaire, résultats, détail, panneau « Hypothèses et sources » |
| `config.js` | Adresse du serveur, zone couverte, fond de carte |
| `css/app.css` | Styles « Pastel et brique », mobile d'abord (colonne à gauche à partir de 960 px) |
| `js/app.js` | Point d'entrée : relie le formulaire, les requêtes, l'affichage et la carte |
| `js/otp.js` | Requête GraphQL et variables (jamais de `modes: null`), appel HTTP et classement des erreurs |
| `js/scenarios.js` | Lecture de `scenario-filters.json` ; un trajet est-il possible dans un scénario ? |
| `js/compare.js` | Le comparateur : liste 2028 fusionnée, barres, libellés « Arrivée N min plus tôt qu'aujourd'hui » |
| `js/itinerary.js` | Réponse d'OTP → trajet affichable (résumé, étapes du détail) |
| `js/format.js` | Heures, durées, distances et dates en français, à l'heure de Paris |
| `js/colors.js` | Couleur et texte des pastilles de ligne (contraste ≥ 4,5:1) |
| `js/geocode.js`, `js/combobox.js` | Recherche d'adresse et champ à suggestions |
| `js/map.js`, `js/polyline.js` | Carte et tracé des trajets |
| `js/demo.js` | Mode démonstration |
| `js/render.js`, `js/dom.js`, `js/icons.js`, `js/messages.js`, `js/storage.js` | Affichage, pictogrammes, messages, mémoire du scénario |
| `vendor/maplibre-gl/` | MapLibre GL JS 6.11.2, copié tel quel depuis npm (licence BSD-3-Clause) |
| `fonts/` | Schibsted Grotesk 400, 600, 800, sous-ensemble latin (licence SIL OFL 1.1) |
| `vendor/SHA256SUMS` | Empreintes des fichiers copiés (vérifiées par les tests) |
| `tests/` | Tests et données d'essai synthétiques : **jamais publiés** (le workflow les retire) |

## Les choix, et pourquoi

**Pas de framework ni d'étape de construction.** Le site est en HTML, CSS et modules JavaScript que les navigateurs récents lisent directement. Il n'y a rien à compiler : ce qui est dans le dépôt est ce qui est publié. Une étape de construction (bundler) gagnerait un peu de poids, mais ajouterait un outil à installer et à comprendre. Le site est déjà léger : 133 Ko de code (40 Ko compressés), 75 Ko de polices, et la bibliothèque de carte (1,2 Mo, 312 Ko compressés) se charge **après** l'affichage du formulaire.

**Tout est servi par le site lui-même.** MapLibre et les polices sont copiés dans le dépôt plutôt que chargés depuis un CDN ou Google Fonts : aucun service tiers ne voit les visiteurs pour cela, et le site ne dépend pas de leur disponibilité. Archives npm vérifiées contre l'empreinte d'intégrité du registre (`maplibre-gl@6.11.2`, `@fontsource/schibsted-grotesk@5.3.0`). Pour changer de version : `npm pack maplibre-gl@<version>`, copier les 4 fichiers de `dist/` (`maplibre-gl.mjs`, `maplibre-gl-shared.mjs`, `maplibre-gl-worker.mjs`, `maplibre-gl.css`) et la licence, puis refaire `vendor/SHA256SUMS` (`sha256sum … > vendor/SHA256SUMS`).

**Fond de carte : OpenFreeMap**, style « Positron ». Gratuit, sans clé ni inscription ni cookie, sans limite de vues ou de requêtes ; l'attribution est obligatoire et MapLibre l'affiche d'elle-même ; service fourni « en l'état », sans garantie ([openfreemap.org](https://openfreemap.org), [conditions](https://openfreemap.org/tos/), lues le 14/10/2026). Les tuiles d'OpenStreetMap (`tile.openstreetmap.org`) étaient l'autre option : elles conviennent à un petit site, mais ce sont des images (pas des tuiles vectorielles), sans garantie de service, et la politique d'usage exige l'en-tête Referer, que le site ne transmet pas par discrétion ([politique d'usage](https://operations.osmfoundation.org/policies/tiles/)). Si OpenFreeMap tombe, le site affiche un message et les trajets restent lisibles en texte.

**Adresses : la Géoplateforme de l'IGN** (`https://data.geopf.fr/geocodage/search` et `/reverse`). L'« API Adresse » de data.gouv.fr y a été transférée : `api-adresse.data.gouv.fr` n'est plus qu'une redirection depuis fin juin 2025 et n'était maintenue que jusqu'en janvier 2026 ([data.gouv.fr](https://www.data.gouv.fr/posts/lapi-adresse-de-la-base-adresse-nationale-est-transferee-a-lign-10)). Service ouvert, sans clé, limité à 50 requêtes par seconde et par adresse IP ([data.gouv.fr](https://www.data.gouv.fr/dataservices/api-geoplateforme-geocodage/discussions)), sous les conditions de cartes.gouv.fr ([guide](https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/geocodage/)). Le site cherche les adresses et les lieux (`index=address,poi`, ou les adresses seules si l'index combiné est refusé), près de Toulouse, et écarte les résultats hors de la zone du graphe. Il envoie au plus une recherche par pause de frappe.

**Comparateur** (règle de Cyprien, `docs/ux/parcours.md` section 6, code dans `js/compare.js`). En 2028, la même demande part vers les deux scénarios. La liste réunit les trajets 2028 et ceux d'aujourd'hui encore possibles en 2028 (aucune agence ni ligne exclue par le scénario 2028), sans doublons, triés par arrivée (par départ, le plus tardif d'abord, pour « Arriver à »). Les deux barres mesurent le temps porte à porte, attente comprise, depuis l'heure demandée ; « aujourd'hui » est le meilleur trajet d'aujourd'hui. Les écarts sont calculés sur les minutes affichées, pour qu'un libellé soit toujours d'accord avec les heures écrites à côté. À pied ou à vélo, le réseau ne change rien : le site n'envoie qu'une demande et le dit.

**Pastilles de ligne.** Fond : `route_color` du GTFS. Texte : blanc ou `#16304F`, le plus contrasté des deux ; si aucun n'atteint 4,5:1, le fond est assombri. `route_text_color` est lu mais ne l'emporte jamais sur cette règle. Ligne du flux `futur` : liseré en tirets.

## Mode démonstration

Avec `?demo=1`, le site lit `demo/demo-responses.json` et rejoue des réponses réelles d'OTP enregistrées par la CI, sous un bandeau « Démonstration : trajets enregistrés le JJ/MM ». Les trajets enregistrés sont proposés en boutons ; une autre recherche répond « Ce trajet n'a pas été enregistré ». Forme du fichier (produit par le workflow de l'architecte) :

```json
{"recorded_at": "<ISO>",
 "requests": [{"id": "…", "label": "…", "scenario": "actuel ou 2028", "variables": {}, "response": {}}],
 "scenario_filters": {}}
```

`variables` sont les variables GraphQL de la demande ; `response` est la réponse GraphQL brute, **obtenue avec la requête `PLAN_QUERY` de `js/otp.js`** (sinon des champs lus par le site manquent). Une même recherche doit être enregistrée dans les deux scénarios pour que la double barre s'affiche.

## Tests

```bash
cd site
npm ci                 # installe graphql, seule dépendance, pour les tests uniquement
npm test               # logique pure, contrôles du site publié
curl -fsSL -o otp-schema.graphqls https://raw.githubusercontent.com/opentripplanner/OpenTripPlanner/v2.10.0/application/src/main/resources/org/opentripplanner/apis/gtfs/schema.graphqls
OTP_SCHEMA=otp-schema.graphqls npm test   # + requête et variables validées contre le schéma OTP 2.10.0
```

Ce que couvrent les tests : formats français (« 1 h 18 », « 42 min », « 8:32 »), heure de Paris aux changements d'heure, contraste des pastilles (dont les ratios de `docs/ux/parcours.md`), variables GraphQL sans aucune valeur nulle, fusion des listes et libellés du comparateur (dont le cas réel Colomiers → Labège, départ 8:30 : le métro C affiche « Arrivée 9 min plus tôt qu'aujourd'hui », le TER « Comme aujourd'hui »), géocodeur, mode démonstration, mémoire du scénario sans `localStorage`, et contrôles statiques (politique de sécurité, aucun script en ligne, aucune ressource externe, fichiers copiés intacts). La CI les lance à chaque pull request (`.github/workflows/checks.yml`).

Captures et audit d'accessibilité (outil de développement, hors CI) : `npm install --no-save playwright-core@1.56.1 axe-core@4.10.3`, puis `AXE=node_modules/axe-core/axe.min.js node tests/screenshots.mjs` (captures dans `tests/screenshots/`, non versionnées). Le script remplace le serveur, le géocodeur et le fond de carte par les données synthétiques.

## Publication

`.github/workflows/pages.yml` publie le site à chaque push sur `main` qui touche `site/**`, ou à la demande (onglet Actions → « Publier le site » → Run workflow). Il copie `site/` sans `tests/`, `package.json` ni ce README, ajoute `demo-responses.json` et `scenario-filters.json` de la dernière release `graph-*` s'ils existent, puis déploie avec les actions officielles de GitHub, épinglées par SHA. Activation à faire une fois : Settings → Pages → Source : **GitHub Actions**.

## Sécurité, vie privée, accessibilité

- Aucun cookie, aucun traceur, aucune statistique. Seul le dernier scénario choisi est gardé dans le navigateur (`localStorage`, clé `toulouse-demain.scenario`) ; si le stockage est bloqué, le site marche quand même et s'ouvre sur « Aujourd'hui ».
- Politique de sécurité (balise `Content-Security-Policy` de `index.html`) : scripts, styles et polices du site uniquement ; connexions vers le serveur d'itinéraires, la Géoplateforme et OpenFreeMap seulement. Les textes reçus (noms d'arrêts, adresses) sont toujours insérés comme du texte, jamais comme du HTML. GitHub Pages ne permet pas d'autres en-têtes HTTP.
- Accessibilité (`docs/ux/parcours.md` section 5) : vrais boutons, champs avec étiquette, `aria-label` sur les boutons à pictogramme seul, focus visible, cibles de 44 px au moins, texte de 16 px (mentions de 14 px), `prefers-reduced-motion` respecté, jamais la couleur seule (coche sur le choix actif, tirets pour le projet, flèche et mots pour l'écart). Le sélecteur de scénario est le premier contrôle atteint au clavier. La carte n'est jamais indispensable : tout est aussi écrit dans la liste et le détail. Audit axe-core (WCAG 2.1 A et AA, bonnes pratiques) : aucune remarque sur les écrans capturés.

## Ce qui n'est pas testé

- **Rien n'a été testé contre le vrai serveur OTP** : les réponses utilisées sont synthétiques (`tests/fixtures/`), construites sur le modèle du schéma 2.10.0. La requête et les variables sont validées contre ce schéma, pas exécutées.
- Le géocodeur et OpenFreeMap n'ont pas été appelés (le poste de développement ne joint pas ces services) : leurs réponses sont imitées, d'après leur documentation. La forme exacte des réponses « lieux » (`index=poi`) n'est pas documentée publiquement : la lecture est défensive.
- Le type MIME des fichiers `.mjs` sur GitHub Pages n'a pas été vérifié sur ce dépôt (la démo officielle de PDF.js, sur GitHub Pages, charge des `.mjs`).
- `pages.yml` n'a pas tourné : il est validé par actionlint.

## Ce qu'il faut retenir

- Un site sans framework ni étape de construction : ce qui est dans `site/` est publié tel quel, sauf les tests.
- La seule valeur à changer avant la mise en ligne est l'adresse du serveur, dans `config.js`.
- En 2028, chaque trajet est comparé au meilleur trajet d'aujourd'hui, en minutes porte à porte, avec des mots et une flèche.
- Aucun traceur ni cookie ; la carte, les polices et le code viennent du site lui-même.
- Tout a été testé avec des données d'essai : le premier vrai test se fera quand le serveur sera en ligne.
