# Parcours et règles d'interface — Toulouse Demain (Sprint 0)

Auteur : designer UX/UI senior · 13 octobre 2026, mis à jour le 14 octobre (direction visuelle et comparateur) · statut : **validé par Cyprien le 14/10/2026**

Maquettes : canevas « Toulouse Demain — Maquettes » (https://claude.ai/artifact/VL77jr3MAddQCLgPrABVqo).

> Toutes les durées, heures et distances des maquettes sont **illustratives**. Elles ne viennent d'aucun calcul et ne doivent pas être lues comme des temps réels.

## 1. Principe directeur

Un seul écran de travail : la carte en fond et un panneau qui se transforme (recherche → résultats → détail). Le comparateur est intégré aux résultats ; le panneau « Hypothèses et sources » est le seul écran à part. Sur téléphone, le panneau est une feuille en bas de l'écran ; sur ordinateur, c'est une colonne à gauche.

Le scénario (Aujourd'hui / 2028) n'est pas un réglage caché : c'est le premier contrôle en haut de chaque écran, toujours visible.

## 2. Les écrans

| # | Écran | Ce que fait l'utilisateur | Éléments et pourquoi ils sont là |
| --- | --- | --- | --- |
| 1 | **Recherche** | Choisit le scénario, saisit Départ et Arrivée, ajuste l'heure et le mode, lance la recherche. | **Sélecteur de scénario** en haut : c'est la fonction signature. **Départ / Arrivée** : seuls champs obligatoires ; une adresse, un arrêt ou un point posé sur la carte. **Ma position** (dans le champ Départ) : évite de taper le cas le plus fréquent sur téléphone. **Inverser** : le trajet retour en un geste. **Heure** : « Maintenant » par défaut, « Partir à » et « Arriver à » à un toucher. **Mode** : trois choix exclusifs (Transports, Marche, Vélo), Transports par défaut. Un seul bouton d'action. |
| 2 | **Résultats** | Parcourt les trajets proposés et en choisit un. | Par trajet : **heures de départ et d'arrivée** et **durée** en gros, **pastilles des lignes** dans l'ordre, **correspondances** en toutes lettres (« Direct », « 1 correspondance »), **temps de marche**. Tracé du trajet choisi sur la carte. Quand 2028 est actif, le **comparateur est intégré** à chaque trajet (voir 4) et la liste réunit les trajets 2028 **et** les trajets d'aujourd'hui encore possibles en 2028, comme Google Maps ou Citymapper : le voyageur choisit. |
| 3 | **Détail d'un trajet** | Suit les étapes, déplie les arrêts intermédiaires. | Frise verticale : heure à gauche, étape à droite. Trois types d'étape : **Marcher** (durée, distance, jusqu'où), **Prendre** (pastille, « direction … », « monter à … »), **Descendre à …**. Une correspondance est une étape « Marcher » entre deux « Prendre », avec son temps d'attente. |
| 4 | **Comparateur** (intégré aux résultats) | Voit, sur chaque trajet 2028, ce qu'il change par rapport à aujourd'hui. | **Double barre** sur une même échelle de temps : aujourd'hui (hachurée, pastel) et 2028 (pleine, brique). En dessous, l'écart en mots et avec une flèche, jamais la seule couleur : « Arrivée 9 min plus tôt qu'aujourd'hui », ou « Comme aujourd'hui » pour un trajet qui existe déjà. Règle : même demande des deux côtés (même jour, même heure de départ) ; l'écart compare l'**heure d'arrivée** du trajet à celle du meilleur trajet d'aujourd'hui ; la **durée** de chaque trajet reste affichée. Un appui sur la double barre ouvre le détail côte à côte. |
| 5 | **Hypothèses et sources** | Lit ce que le scénario 2028 suppose et d'où viennent les chiffres. | Ce qui est simulé (lignes, stations, dates annoncées), comment on calcule (calendrier actuel, bus inchangés), les sources avec date de consultation, les attributions de licence. |
| 6 | **Bureau** (écran principal) | Même parcours que 1 + 2, en un seul écran. | Colonne de gauche (scénario, bandeau, formulaire, résultats), carte à droite avec légende, zoom, attribution et un encart « Comparé à aujourd'hui » qui ouvre le comparateur. |

### Bandeau « projection »

- Visible sur **tout écran où le scénario 2028 s'applique** (recherche, résultats, détail, comparateur, bureau), juste sous le sélecteur de scénario. Il ne se ferme pas.
- Texte : « Projection 2028 : réseau simulé, durées indicatives. » + lien « Hypothèses et sources ».
- Repères non colorés : bordure en tirets et pictogramme, comme les lignes futures.

### Codage « ligne en projet »

Une même convention partout : **les tirets signalent ce qui n'existe pas encore**. Lignes futures en tirets sur la carte, pastille de ligne future entourée d'un liseré en tirets, bandeau en tirets, colonne 2028 du comparateur en tirets. La légende de la carte le dit en toutes lettres.

## 3. Contenu des maquettes

- Trajet d'exemple : **Gare de Colomiers → Labège, Innopole**.
- Aujourd'hui (illustratif) : TER jusqu'à Toulouse-Matabiau puis TER jusqu'à Labège-Innopole ; ou TER jusqu'aux Arènes, métro A, métro B, bus 79.
- 2028 (illustratif) : métro C direct de Colomiers Gare à Labège La Cadène ; ou TER + métro A + métro B prolongée.
- Noms de stations repris de la page de Toulouse Métropole « La Ligne C embarque ses voyageurs fin 2028 » (metropole.toulouse.fr/3e-ligne, consultée le 13/10/2026) : Colomiers - Gare, Matabiau Gare, François-Verdier, Montaudran Gare, Labège La Cadène. Cette page indique aussi 21 stations, 27 km et une mise en service fin 2028. Les noms peuvent encore changer.
- **Point à vérifier par le data engineer** : la desserte ferroviaire Arènes–Colomiers a longtemps porté le nom « ligne C ». Les maquettes l'affichent « TER » pour éviter toute confusion avec la future ligne C du métro.
- Les lignes de bus et les correspondances d'exemple sont plausibles mais non vérifiées : le vrai GTFS fera foi.

## 4. Identité visuelle

**Direction retenue le 14/10/2026 : B, « Pastel et brique »** (artboard « Direction B » du canevas ; la version 1 et les directions A et C sont écartées). L'idée : les deux couleurs historiques de Toulouse, le bleu du pastel, la plante tinctoriale qui a fait la fortune de la ville, et la brique de la ville rose. Le pastel porte le réseau d'aujourd'hui et l'interface, la brique porte 2028. Aucun opérateur n'est imité. Les tirets gardent leur sens partout : ce qui n'est pas encore construit.

| Rôle | Valeur | Usage | Contraste |
| --- | --- | --- | --- |
| Fond | `#F4F6F9` | Fond de l'application | — |
| Pastel clair | `#D8E3F0` | En-tête de recherche, zones de saisie | — |
| Pastel profond | `#24476F` | Texte principal, scénario actif, boutons | 8,8:1 sur le fond ; blanc dessus 9,5:1 |
| Pastel secondaire | `#4F6585` | Textes secondaires | 5,5:1 sur le fond, 4,6:1 sur pastel clair |
| Contour de champ | `#6F84A3` | Contours des champs et boutons secondaires | 3,5:1 sur le fond |
| Filet | `#C3D0E0` | Séparateurs décoratifs uniquement | — |
| Brique | `#A8473C` | 2028 : barre pleine, écart, bandeau en tirets, liens | 5,3:1 sur le fond, 5,8:1 sur blanc |

**Comparateur intégré** : barre « aujourd'hui » hachurée à 135° en pastel profond, barre « 2028 » pleine en brique, même échelle pour tous les trajets de la liste.

**Pastilles de ligne** : rectangle arrondi de 28 px de haut, nom de la ligne (pictogramme du mode à ajouter au développement). Aucun logo d'opérateur. Ligne future ou section future (B prolongée) : liseré en tirets. Couleurs : celles du champ `route_color` du GTFS (provisoires pour le flux futur : C `#5BBF8A`, B `#F2C230`). Texte de la pastille : blanc ou `#16304F`, le plus contrasté des deux ; si aucun n'atteint 4,5:1, on assombrit le fond. Exemple : `#24476F` sur le vert de C ne fait que 4,2:1, alors que `#16304F` fait 5,9:1.

**Typographie** (Google Fonts, gratuite) : *Schibsted Grotesk* seule, en 400, 600 et 800. Les heures et les durées utilisent ses chiffres tabulaires (`font-variant-numeric: tabular-nums`), pour que les colonnes s'alignent sans police à chasse fixe.

## 5. Règles d'accessibilité

1. **Contraste** : texte ≥ 4,5:1 (≥ 3:1 à partir de 24 px), contours de champs et boutons ≥ 3:1. Aucun gris clair pour du texte utile.
2. **Cibles tactiles** ≥ 44 × 44 px, 48 px pour les actions principales, 8 px minimum entre deux cibles.
3. **Jamais la couleur seule** : chaque ligne porte son nom, chaque scénario son libellé et une coche, chaque projection ses tirets, le temps gagné une flèche et un mot.
4. **Vrais composants** : `<button>`, `<a>`, `<input>` avec `<label>` ; boutons à pictogramme seul avec `aria-label` (« Ma position », « Inverser départ et arrivée »).
5. **Texte** : 16 px minimum pour le corps, 14 px minimum pour les mentions. Le zoom du navigateur ne doit rien casser.
6. **Carte** : jamais indispensable. Tout ce qu'elle montre (tracé, arrêts) existe aussi en texte dans la liste et le détail. Attribution OpenStreetMap, Tisséo et SNCF toujours visible.
7. **Mouvement** : pas d'animation obligatoire ; on respecte `prefers-reduced-motion`.

## 6. Décisions de Cyprien (14 octobre 2026)

| Question | Décision |
| --- | --- |
| Couleurs des lignes | **Celles du GTFS Tisséo** (`route_color`), corrigées si le contraste du texte passe sous 4,5:1 |
| Scénario à l'ouverture | **Le dernier choisi** ; « Aujourd'hui » à la toute première visite |
| Maquettes | Version 1 jugée trop générique (« effet vibe coding ») ; trois directions proposées, **B « Pastel et brique » retenue** |
| Comparateur | **Intégré à la liste de résultats** |
| Temps gagné | **Toutes les options affichées, comme Google Maps ou Citymapper** : la liste 2028 réunit les trajets 2028 et ceux d'aujourd'hui encore possibles, chacun avec départ, arrivée, durée et écart d'arrivée avec aujourd'hui. Remplace l'« écart des durées » choisi le matin même : le premier calcul réel a montré qu'avec cette règle, Colomiers → Labège afficherait « 3 min de plus » en 2028 alors que le métro C fait arriver 9 min plus tôt (départ 8:31, arrivée 9:19, contre un TER à 8:43 arrivé à 9:28) |

## Ce qu'il faut retenir

- Un écran principal (carte + panneau), le comparateur intégré à chaque trajet 2028, et un écran annexe « Hypothèses et sources ».
- Style « Pastel et brique » : le bleu du pastel pour l'interface et le réseau d'aujourd'hui, la brique pour 2028.
- Le choix Aujourd'hui / 2028 est le premier bouton de chaque écran, et un bandeau en tirets rappelle que 2028 est une projection.
- Partout, les tirets veulent dire « pas encore construit » : sur la carte, sur les pastilles et dans le comparateur.
- Lisible d'abord : grandes durées, polices conçues pour la lisibilité, cibles de 44 px minimum, aucune info portée par la couleur seule.
- Les temps affichés dans les maquettes sont des exemples, pas des calculs.
