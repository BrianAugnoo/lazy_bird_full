# Context Module — app-header

## Objectif
Affiche l'état de santé du système Lazy Bird (`GET /`), la révision courante des migrations de la base de données SQL (Alembic), et permet le rafraîchissement global des données.

## API publique exposée
- `AppHeader` : composant React acceptant la prop optionnelle `onRefreshAll?: () => void`.

## Dépendances
- `src/api/endpoints/health.ts` (`getHealth`)
- `src/core/types/api.ts` (`HealthResponse`)

## Comment l'étendre
- Pour ajouter un indicateur d'état supplémentaire (ex: latence réseau, nombre de workers de tâches actifs), étendre `AppHeaderProps` et consommer les endpoints correspondants.

## Limitations connues / TODO
- Le polling actuel est de 30 secondes ; une notification push via WebSocket pourrait être envisagée si un endpoint de statut temps réel est ajouté.
