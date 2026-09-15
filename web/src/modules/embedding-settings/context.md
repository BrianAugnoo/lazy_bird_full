# Context Module — embedding-settings

## Objectif
Permet l'inspection, la configuration fine des paramètres spécifiques (`kwargs`) et l'activation d'un moteur d'embedding au sein de l'écosystème Lazy Bird.

## API publique exposée
- `EmbeddingSettings` : composant React de configuration des moteurs.

## Dépendances
- `src/api/endpoints/embeddings.ts` (`getEmbeddingEngines`, `updateEngineKwargs`, `getSelectedEmbeddingEngine`, `setSelectedEmbeddingEngine`)
- `src/core/types/api.ts` (`EmbeddingEngine`, `SelectedEmbeddingEngine`)

## Comment l'étendre
- La génération des champs de saisie est dynamique et déduite de `kwargs_keys` retourné par le backend. Tout nouveau moteur implémentant le contrat backend `EngineSettings` s'affichera automatiquement avec ses types et validations.

## Limitations connues / TODO
- Les types complexes (tableaux ou dictionnaires imbriqués dans les kwargs) sont saisis sous forme de texte / JSON.
