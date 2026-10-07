# lazy_bird — backend

API FastAPI de lazy_bird : stockage de fichiers, découpage en chunks, embeddings et
recherche sémantique, modèles Hugging Face, tâches de fond, et équipes d'agents
(outils, hooks, skills, instructions, presets) — le tout extensible par modules.

## Démarrage

Python 3.12+ et `uv` (jamais `pip`) :

```bash
uv sync
uv run uvicorn lazy_bird.main:app --reload   # http://localhost:8000, documentation sur /docs
uv run pytest -q
```

Au démarrage, la base SQL sélectionnée est migrée automatiquement vers la dernière
révision Alembic. Pour créer une révision :

```bash
cd src/lazy_bird
uv run alembic revision --autogenerate -m "décrire le changement"
```

L'interface web se trouve dans `../web/` (`npm run dev`).

## Documentation

- [AGENTS.md](AGENTS.md) — méthode de travail, architecture, contrats d'extension,
  modèle de données, flux (fichiers, tâches, inférence), procédures de migration.
- [../web/AGENTS.md](../web/AGENTS.md) — l'interface web.
- `/docs` — le schéma OpenAPI de toutes les routes.
- `/schemas` — le diagramme du modèle de données.
