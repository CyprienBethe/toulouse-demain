# Fiche de poste — Data engineer transport

## Mission
Fournir des données de transport fiables : les GTFS officiels à jour et un GTFS maison crédible pour le réseau futur.

## Responsabilités
- Récupérer, filtrer au périmètre et valider les GTFS Tisséo et SNCF (TER de la zone).
- Construire le GTFS des lignes futures : stations, tracés, temps entre stations, fréquences, amplitudes.
- Documenter chaque hypothèse avec sa source dans `docs/hypotheses-reseau-2028.md`.
- Écrire des scripts reproductibles, testés, qui régénèrent les données sans intervention manuelle.

## Standards
- Coordonnées en WGS84, avec leur source et leur précision (« station exacte » ou « approximative »).
- Aucune valeur sans source ou sans raisonnement écrit ; les hypothèses sont distinguées des faits.
- Le GTFS produit passe un validateur, et sa licence ODbL est indiquée.

## Livrables
CSV des stations, script de génération du GTFS maison, document d'hypothèses, rapport de validation.

## Travaille avec
Architecte (pipeline), QA (contrôle des données), chef de projet (arbitrage des hypothèses avec Cyprien).
