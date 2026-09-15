# Context Module — model-manager

## Objectif
Permet le téléchargement, l'enregistrement, la sélection du format (safetensors, etc.) et l'activation d'un modèle d'embedding Hugging Face dans Lazy Bird.

## API publique exposée
- `ModelManager` : composant React d'administration des modèles.

## Dépendances
- `src/api/endpoints/models.ts` (`getModels`, `createModel`, `setModelFormat`, `destroyAllModels`, `getSelectedModel`, `setSelectedModel`)
- `src/core/types/api.ts` (`LLMModel`, `SelectedModel`)

## Comment l'étendre
- Pour ajouter la gestion de modèles locaux personnalisés ou d'autres registres (Ollama, vLLM), adapter le formulaire d'enregistrement et ajouter les endpoints nécessaires.

## Limitations connues / TODO
- Le téléchargement Hugging Face initial peut prendre plusieurs dizaines de secondes selon la bande passante du serveur.
