# Context Module — api-keys

## Objectif
Permet l'enregistrement sécurisé et la consultation des clés d'API tierces (`POST /api-keys/api-keys`, `GET /api-keys/api-keys`, `GET /api-keys/api-keys/{name}`).

## API publique exposée
- `ApiKeyManager` : composant React d'administration des clés.

## Dépendances
- `src/api/endpoints/apiKeys.ts` (`createApiKey`, `listApiKeys`, `getApiKey`)
- `src/core/types/api.ts` (`APIKeyIn`, `APIKeyOut`)

## Comment l'étendre
- Pour ajouter la suppression ou la modification de clés si l'endpoint backend est implémenté ultérieurement, compléter `apiKeys.ts` et ajouter les boutons d'action.

## Limitations connues / TODO
- Les clés dupliquées renvoient une erreur 400 gérée par le composant.
