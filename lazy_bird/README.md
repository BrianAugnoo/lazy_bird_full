# Lazy Bird

Guide de developpement pour l'API FastAPI de gestion de fichiers, de modeles
d'embedding et d'index vectoriels.

## Demarrage

Le projet utilise Python 3.12+ et `uv`:

```bash
uv sync
uv run uvicorn lazy_bird.main:app --reload
uv run pytest
```

La commande Alembic doit etre lancee depuis `src/lazy_bird`:

```bash
cd src/lazy_bird
uv run alembic upgrade head
```

## Architecture

Une requete suit le flux `endpoint -> schema -> CRUD/service -> session -> modele`.
Les endpoints traduisent HTTP, les schemas definissent les contrats publics, les
CRUD orchestrent la persistance et les adaptateurs isolent les integrations externes.
Les cles API sont acceptees par `APIKeyIn` mais ne sont jamais renvoyees par `APIKeyOut`.

## Contrats d'extension

La decouverte dynamique des modules reste volontaire pour permettre d'ajouter un
adaptateur ou un moteur sans modifier le routeur. Elle est encadree par des contrats
explicites:

- Un adaptateur SQL fournit `name`, `initialize(**settings)` et
	`disconnect(engine, drop=False)`. Ses settings utilisent `url`. SQLite transforme
	ensuite son URL `sqlite:///...` en chemin local; ce detail ne remonte pas au contrat.
- Un adaptateur vectoriel fournit `name`, `initialize`, `disconnect`, `create`,
	`delete` et `retrieve`.
- Un moteur d'embedding fournit `name`, `formats`, `EngineSettings` et `embed`.
- Une extension de format fournit `async Chunck(file, max_token)`.
- Un module d'endpoint fournit un `router` FastAPI.

Les contrats SQL et vectoriels sont formalises dans
`src/lazy_bird/database/contracts.py`. Les appels Alembic utilisent
`database.alembic_config_for(url)` afin que l'URL choisie soit explicite et stable.

## API database

`GET /databases/` liste le catalogue des adaptateurs et la selection courante.
`GET /databases/selected_db` renvoie uniquement:

```json
{"sql": "sqlite", "vector": "lancedb"}
```

La selection et la deconnexion passent par `PUT /databases/select` et
`PUT /databases/disconnect`. Les settings sont valides par le schema de chaque
adaptateur avant connexion.

## Tests

Les tests suivent la convention standard `test_*.py` et utilisent des bases SQLite
temporaires migrees par Alembic. Les integrations reseau et Hugging Face sont
remplacees par des doublures dans `tests/conftest.py`; la suite ne doit pas dependre
d'un reseau ou de la base de developpement.
