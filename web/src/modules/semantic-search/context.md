# Context Module — semantic-search

## Objectif
Expose une recherche sémantique sur l'index vectoriel et présente les chunks trouvés avec leur distance, leurs lignes source et leurs métadonnées.

## API publique exposée
- `SemanticSearch` : composant autonome de recherche avec requête et top-k.

## Dépendances
- `src/api/endpoints/search.ts` (`searchChunks`)
- `src/core/types/api.ts` (`SearchResult`)

## Comment l'étendre
Pour ajouter un filtre ou une stratégie de tri, étendre `SearchPayload` et `searchChunks`, puis ajouter le contrôle dans le formulaire.

## Limitations connues / TODO
Le backend ne documente pas encore de pagination ni de filtre de fichier pour la recherche.
