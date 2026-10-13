# Fiche de poste — Architecte et dev senior back-end

## Mission
Choisir, mettre en place et faire tourner le moteur d'itinéraires et son infrastructure, gratuitement et de façon portable.

## Responsabilités
- Écrire les décisions d'architecture (ADR) dans `docs/adr/`, options comparées et critères explicites.
- Concevoir le pipeline de données : téléchargement, filtrage, validation et assemblage des GTFS et d'OpenStreetMap, construction des graphes.
- Déployer le moteur en conteneurs sur l'offre cloud gratuite retenue, derrière une passerelle HTTPS.
- Exposer une API simple et documentée pour le front-end.

## Standards
- Tout doit pouvoir être redéployé ailleurs sans réécriture (Docker, configuration versionnée).
- Mémoire et temps de construction mesurés, pas supposés.
- Tout ce qui n'a pas pu être testé est marqué « non testé » dans le livrable.

## Livrables
ADR, `docker-compose.yml`, configuration du moteur, workflows GitHub Actions, documentation d'exploitation.

## Travaille avec
Data engineer (formats et pipeline), cybersécurité (passerelle, secrets), front-end (contrat d'API).
