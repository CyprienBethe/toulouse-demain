# Parcours et règles d'interface — Toulouse Demain (Sprint 0)

Auteur : designer UX/UI senior · 13 octobre 2026 · statut : **à valider par Cyprien**

Maquettes : canevas « Toulouse Demain — Maquettes » (https://claude.ai/artifact/VL77jr3MAddQCLgPrABVqo).

> Toutes les durées, heures et distances des maquettes sont **illustratives**. Elles ne viennent d'aucun calcul et ne doivent pas être lues comme des temps réels.

## 1. Principe directeur

Un seul écran de travail : la carte en fond et un panneau qui se transforme (recherche → résultats → détail). Le comparateur et le panneau « Hypothèses et sources » sont les deux seuls écrans à part. Sur téléphone, le panneau est une feuille en bas de l'écran ; sur ordinateur, c'est une colonne à gauche.

Le scénario (Aujourd'hui / 2028) n'est pas un réglage caché : c'est le premier contrôle en haut de chaque écran, toujours visible.

## 2. Les écrans

| # | Écran | Ce que fait l'utilisateur | Éléments et pourquoi ils sont là |
| --- | --- | --- | --- |
| 1 | **Recherche** | Choisit le scénario, saisit Départ et Arrivée, ajuste l'heure et le mode, lance la recherche. | **Sélecteur de scénario** en haut : c'est la fonction signature. **Départ / Arrivée** : seuls champs obligatoires ; une adresse, un arrêt ou un point posé sur la carte. **Ma position** (dans le champ Départ) : évite de taper le cas le plus fréquent sur téléphone. **Inverser** : le trajet retour en un geste. **Heure** : « Maintenant » par défaut, « Partir à » et « Arriver à » à un toucher. **Mode** : trois choix exclusifs (Transports, Marche, Vélo), Transports par défaut. Un seul bouton d'action. |
| 2 | **Résultats** | Parcourt 2 à 3 trajets, en choisit un ou ouvre le comparateur. | Par trajet : **durée** (l'info la plus lue, en gros), **heures de départ et d'arrivée**, **pastilles des lignes** dans l'ordre, **correspondances** en toutes lettres (« Direct », « 1 correspondance »), **temps de marche**. Tracé du trajet choisi sur la carte. Bouton **Comparer avec aujourd'hui** sur le trajet en tête quand 2028 est actif. |
| 3 | **Détail d'un trajet** | Suit les étapes, déplie les arrêts intermédiaires. | Frise verticale : heure à gauche, étape à droite. Trois types d'étape : **Marcher** (durée, distance, jusqu'où), **Prendre** (pastille, « direction … », « monter à … »), **Descendre à …**. Une correspondance est une étape « Marcher » entre deux « Prendre », avec son temps d'attente. |
| 4 | **Comparateur** | Voit le même trajet Aujourd'hui et 2028 côte à côte. | **Temps gagné en très gros**, avec un mot (« plus rapide ») et une flèche, jamais la seule couleur. Deux colonnes alignées ligne à ligne (durée, horaires, lignes, correspondances, marche) et deux barres sur la même échelle de temps pour voir l'écart. Même demande des deux côtés (même jour, même heure de départ) ; le temps gagné est l'écart entre les **durées**, et les heures d'arrivée sont affichées à côté. |
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

**Idée** : « la ligne qui continue en pointillés ». Le logo est un trait plein, une station, puis un trait en tirets : aujourd'hui, puis demain. Ton sobre, papier chaud et encre, un clin d'œil à la brique toulousaine sans imiter aucun opérateur.

| Rôle | Valeur | Usage |
| --- | --- | --- |
| Fond | `#F6F1EB` papier chaud | Fond de l'application |
| Surface | `#FFFFFF` | Feuilles, cartes de trajet |
| Encre | `#1C1917` | Texte principal |
| Encre secondaire | `#57504A` | Textes secondaires (7,9:1 sur blanc) |
| Bordure de champ | `#8A7F76` | Contour des champs et boutons (3,9:1) |
| Brique | `#B23F26` | Action principale, scénario Aujourd'hui (5,8:1 avec texte blanc) |
| Demain | `#3730A3` indigo | Scénario 2028, temps gagné, bandeau (9,9:1 avec texte blanc) |
| Bandeau | `#ECEAFB` + tirets `#3730A3` | Bandeau projection |

**Pastilles de ligne** : rectangle arrondi de 28 px de haut, pictogramme du mode (métro, train, bus) + nom de la ligne. Aucun logo d'opérateur. Couleurs **provisoires** : métro A rouge `#C53030` (texte blanc), métro B jaune `#F2C230` (texte encre), métro C vert `#5BBF8A` (texte encre), TER ardoise `#3F4A5A` (texte blanc), bus blanc bordé d'encre. Au développement, les couleurs viendront du champ `route_color` du GTFS, corrigées si le contraste du texte passe sous 4,5:1.

**Typographies** (Google Fonts, gratuites) :
- *Bricolage Grotesque* : logo, durées, titres.
- *Atkinson Hyperlegible Next* : tout le texte d'interface. Elle a été dessinée pour la lisibilité (I, l et 1 bien distincts).
- *Atkinson Hyperlegible Mono* : heures de passage, avec des chiffres de même largeur pour que les colonnes s'alignent.

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
| Temps gagné | **Écart des durées** porte à porte ; les heures d'arrivée restent affichées à côté |
| Couleurs des lignes | **Celles du GTFS Tisséo** (`route_color`), corrigées si le contraste du texte passe sous 4,5:1 |
| Scénario à l'ouverture | **Le dernier choisi** ; « Aujourd'hui » à la toute première visite |
| Maquettes | **À revoir** : une nouvelle version suit les retours de Cyprien |

Reste ouvert : comparateur en écran à part (maquette actuelle) ou bascule intégrée à la liste de résultats.

## Ce qu'il faut retenir

- Un écran principal (carte + panneau) et deux écrans annexes : le comparateur et « Hypothèses et sources ».
- Le choix Aujourd'hui / 2028 est le premier bouton de chaque écran, et un bandeau en tirets rappelle que 2028 est une projection.
- Partout, les tirets veulent dire « pas encore construit » : sur la carte, sur les pastilles et dans le comparateur.
- Lisible d'abord : grandes durées, polices conçues pour la lisibilité, cibles de 44 px minimum, aucune info portée par la couleur seule.
- Les temps affichés dans les maquettes sont des exemples, pas des calculs.
