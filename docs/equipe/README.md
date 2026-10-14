# Équipe projet — Toulouse Demain

Le chef de projet (Claude) coordonne six agents spécialisés. Chaque agent est lancé avec sa fiche de poste et les règles communes ci-dessous. Cyprien est Product Owner : il priorise et valide, et apprend en route.

| Rôle | Fiche |
| --- | --- |
| Architecte et dev senior back-end | [architecte.md](architecte.md) |
| Data engineer transport | [data-engineer.md](data-engineer.md) |
| UX/UI designer senior | [ux-designer.md](ux-designer.md) |
| Dev senior front-end | [front-end.md](front-end.md) |
| Expert cybersécurité | [cybersecurite.md](cybersecurite.md) |
| QA / testeur indépendant | [qa.md](qa.md) |

## Contexte du projet

Site web gratuit (0 €) de calcul d'itinéraires sur tout le réseau Tisséo (114 communes) et les TER de la zone. Modes : transports en commun avec marche, marche seule, vélo perso.

Deux scénarios dans le MVP :

- **Réseau actuel** : GTFS officiels Tisséo et SNCF, mis à jour automatiquement.
- **Réseau 2028** : réseau actuel + ligne B prolongée jusqu'à Labège (ouverture annoncée en septembre 2027) + ligne C (27 km, 21 stations, fin 2028), via un GTFS construit par l'équipe.

Fonction signature : le comparateur avant/après sur un même trajet, avec le temps gagné. Le scénario SERM vient en V2.

## Règles communes à tous les agents

1. **Langue** : français pour la documentation et les messages de commit ; anglais pour le code et les noms techniques.
2. **Aucune donnée inventée** : toute donnée factuelle (coordonnée, horaire, fréquence, date) a une source citée. Une estimation est marquée « hypothèse » avec son raisonnement.
3. **Zéro euro** : aucun service payant, aucune clé d'API payante, aucune période d'essai.
4. **Simplicité d'abord** : la solution la plus simple qui marche, expliquée pour un débutant.
5. **Sécurité par défaut** : aucun secret dans le dépôt, aucun traceur, versions des dépendances épinglées.
6. **Licences** : code sous MIT ; données dérivées des GTFS sous ODbL, avec attribution affichée.
7. **Ce qu'il faut retenir** : chaque livrable se termine par 3 à 5 lignes en langage simple, pour Cyprien.
8. **Environnement** : le shell de l'espace de travail n'atteint que les registres de paquets et GitHub. Pour lire le web, utiliser les outils de recherche et de lecture de pages, jamais curl vers un autre site.

## Modélisation du réseau futur

1. Les lignes futures roulent sur le calendrier actuel : on simule « et si la ligne C existait aujourd'hui ».
2. Le réseau de bus reste celui d'aujourd'hui.
3. Les horaires sont construits à partir des chiffres publics, revérifiés, et documentés.
4. À l'ouverture réelle de la B prolongée, elle passe dans le réseau actuel et sort du GTFS maison.
