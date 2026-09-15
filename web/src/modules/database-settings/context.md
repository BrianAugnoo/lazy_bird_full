# Context Module — database-settings

## Objectif
Permet l'inspection des adaptateurs de bases de données relationnelles (SQL) et vectorielles disponibles, la bascule à chaud entre moteurs avec validation dynamique de leurs schémas de configuration, et la déconnexion/purge des données.

## API publique exposée
- `DatabaseSettings` : composant React d'administration des bases de données.

## Dépendances
- `src/api/endpoints/databases.ts` (`getDatabases`, `getSelectedDatabases`, `selectDatabase`, `disconnectDatabase`)
- `src/core/types/api.ts` (`DatabasesCatalogResponse`, `SelectedDatabaseOut`, `DatabaseSelectionIn`, `DatabaseDisconnectIn`)

## Comment l'étendre
- Pour ajouter un nouvel adaptateur côté backend (ex: PostgreSQL, Qdrant, ChromaDB), il suffit d'ajouter le module dans `lazy_bird/database/`. Le catalogue retourné par `GET /databases/` l'exposera automatiquement avec ses schémas de paramètres dans cette interface sans modifier le code frontend.

## Limitations connues / TODO
- La modification d'adaptateur SQL réapplique les migrations Alembic côté backend.
