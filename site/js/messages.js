// Messages shown to the visitor: what happened, and what to do.

/** Message for an ApiError kind: {title, text}. */
export function apiErrorMessage(kind) {
  switch (kind) {
    case 'not-configured':
      return {
        title: "Le calculateur n'est pas encore branché",
        text: "Le site attend l'adresse de son serveur d'itinéraires. Revenez un peu plus tard, ou essayez la démonstration.",
      };
    case 'rate-limited':
      return {
        title: 'Beaucoup de recherches en peu de temps',
        text: 'Le serveur limite le nombre de recherches par minute. Attendez une minute, puis réessayez.',
      };
    case 'timeout':
      return {
        title: 'Le serveur met trop de temps à répondre',
        text: 'Il est peut-être très sollicité. Réessayez dans un instant.',
      };
    case 'server':
      return {
        title: 'Le serveur a rencontré un problème',
        text: "Il redémarre peut-être après la mise à jour des horaires (le lundi matin). Réessayez dans quelques minutes.",
      };
    case 'bad-response':
      return {
        title: "La recherche n'a pas abouti",
        text: "Le serveur a répondu, mais pas comme prévu. Réessayez ; si le problème continue, essayez la démonstration.",
      };
    case 'filters':
      return {
        title: 'Les réseaux ne sont pas disponibles',
        text: "Le site n'a pas pu lire la description des deux réseaux (aujourd'hui et 2028). Réessayez dans quelques minutes.",
      };
    case 'demo-missing':
      return {
        title: 'Pas de démonstration pour le moment',
        text: "Aucun trajet enregistré n'est publié avec le site. Retirez « ?demo=1 » de l'adresse pour faire une vraie recherche.",
      };
    case 'demo-unknown':
      return {
        title: "Ce trajet n'a pas été enregistré",
        text: 'En démonstration, seuls les trajets enregistrés sont disponibles : choisissez-en un dans la liste.',
      };
    case 'unreachable':
    default:
      return {
        title: "Le serveur d'itinéraires ne répond pas",
        text: 'Vérifiez votre connexion. Si elle marche, le serveur est peut-être en maintenance : réessayez dans quelques minutes, ou essayez la démonstration.',
      };
  }
}

/** Message for an OTP routing error code (when no trip is found). */
export function routingErrorMessage(code) {
  switch (code) {
    case 'OUTSIDE_BOUNDS':
      return 'Ce point est hors de la zone couverte (réseau Tisséo et TER autour de Toulouse).';
    case 'LOCATION_NOT_FOUND':
      return "Le départ ou l'arrivée est trop loin d'une rue. Choisissez un point un peu plus près.";
    case 'OUTSIDE_SERVICE_PERIOD':
      return "Pas d'horaires pour cette date : le calculateur couvre environ les trois prochaines semaines.";
    case 'NO_STOPS_IN_RANGE':
      return "Aucun arrêt à distance de marche du départ ou de l'arrivée.";
    case 'NO_TRANSIT_CONNECTION_IN_SEARCH_WINDOW':
      return 'Aucun trajet en transports en commun autour de cette heure. Essayez une autre heure.';
    case 'WALKING_BETTER_THAN_TRANSIT':
      return "À pied, c'est plus rapide : essayez le mode « Marche ».";
    case 'NO_DIRECT_MODE_CONNECTION':
    case 'NO_TRANSIT_CONNECTION':
    default:
      return 'Aucun trajet trouvé entre ces deux points. Essayez une autre heure ou un autre mode.';
  }
}
