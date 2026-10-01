# Introduction

lazy-bird est une plateforme open-source designer pour etre extension driven, pour vous faire une image mental ca devrait un peu etre le WordPress des workflow AI. la plateforme et designer pour etre tres flexible et modulable. Une des Core principale est le stockage de ficher et document, puis l'utilisation de divers technique de retrieve pour les deep-search, trouver les coorelation entres chaque information, implementer un systeme de memorication et context injection tres precis pour les agents AI.

nous nous trouvons actuelement dans le root lazy_bird_full/ la codebase actuel est diviser en 3 partie:
- lazy_bird/ la partie backend ou ce trouve toutes la machinerie (fastapi)
- web/ tout le frontend si trouve (vite, react, typescript)
- lazy_bird/sandbox/ il s'agit d'une partie independante du reste qui sert juste a faire des experimentation

## lazy_bird
location: lazy_bird/src/lazy_bird
evironement: uv (never use pip or uv pip)

### Qu'est ce qu'une interface?
dans notre cas c'est un terme inspirer des interfaces du language de programmation go, en gros un je sais qu'un element a X function, variable, classe... je n'ai pas besoin de savoir comment elle fonctionne je sais juste quel paramettre ils ont besoin et quel sont ces valeur de retour. dans notre cas une interface est un module situer a un path precis et qui doit respecter un contrat precis. un __init__ va souvent les importer dynamiquement; les ficher commencant par "_" sont ignorer.

### database

location: lazy_bird/database/
le programme possede deux type de database: sql, et vector. les database. celles cis sont designer pour etre plug and play, et on devrait pourvoir basculer d'une database a l'autre dynamiquement a l'ouverture du serveur. contrairement au reste du projet leur configuration sont definis dans un ficher JSON: database/config.json , mais pas dans une database comme les autres (ce qui est assez logique).

#### sql

chaque interface ce trouve dans database/sql_db/, voici le contrat: elle doivent posseder une variable name, une variable messages qui est une dict qui contient les keys "initialize": un message afficher a l'utilisateur avant la connection pour donner des instruction suplementaire, "disconnect": informer de ce qui va se passser si l'utillisateur tente de se deconnecter la db. default_url (optionel) une variable avec une valeur predefinit qui serat utiliser si l'utilisateur ne precise pas; une Class Setting qui est un BaseModel pydantic qui represente les attribut necessaire a la db pour s'initialiser, on peut donner une valeur par defaut si l'attribut ne pas obligatoire. elle possede ensuite une fonction initialize qui prend en argument **kwargs qui doivent etre les key value definit dans Settings, initialise la db puis retourne une instance d'Engine de slqlalchemy.engine; une fonction disconnect qui prend en params une instance d'Engine, et drop: bool pour specifier si il faut vider ou pas le contenue de la DB

#### vector
interface: database/vector_db/
contrat: name, messages, Settings simillaire a ceux des interface sql, initialize(**kwargs) ici la valeur la valeur de retour est negligeable car toutes les db vectoriel ont des convention tres differentes contrairement au db sql, disconnect(drop: bool). comme les db vectoriel ont toutes differentes maniere d'effectuer des transaction ils doivent aussi gerer eux meme leur fonction crud:
- create:
Args: model_name: utiliser pour definir le nom de la table (chaque model ont des hidden-layer differentes mais au moment de la creation de la table la taille des columns embedding sont fix donc il faut les isoler par model), embedded_id il s'agit d'une foreign key simuler relier a une table sql pour savoir quels chunks sont relier a un document, chunks: une liste de dict, pas besoin de connaitre son contenue ont le stock tel quel.
Return: retourn le nombre de column ayant ete ajouter
- delete:
Args: model_name, embedded_id, la fonction doit suprimer toutes les instance possedant avec la column embedded_id = emdedded_id (params) dans la table model_name
Return: retourn 1 si tout c'est bien passer, 0 si la table model_name n'existe pas
- retrieve
Args: model_name, top_k: nombre d'instance a retourner, vector: liste de float representant un query vectoriser
return: renvoie la liste de colums retrouver par la recherche vectoriel avec une longuer top_k sauf si nombre d'instance total < top_k, revoie une liste vide si le model_name n'est pas trouver

#### __init__.py

`database/__init__.py` est le chef d'orchestre du module. Il ne contient aucune logique propre à une base de données précise. Il découvre les interfaces (`sql_db/` et `vector_db/`), charge la configuration, expose la connexion active au reste de l'application, gère les migrations Alembic et permet de basculer d'une base à l'autre.

##### Découverte des interfaces

`_discover(package_name)` parcourt un package avec `pkgutil`, importe chaque module dont le nom ne commence pas par `_` et vérifie qu'il respecte le contrat minimal :

- SQL : `name`, `initialize`, `disconnect`
- Vector : les mêmes, plus `create`, `delete`, `retrieve`

S'il manque un attribut, un `ImportError` est levé dès l'import, ce qui empêche le serveur de démarrer avec une interface cassée. Le résultat est un dict `{module.name: module}`, stocké dans `SQL_ADAPTERS` et `VECTOR_ADAPTERS`. Ajouter une base de données revient donc à déposer un fichier dans le bon dossier, sans rien enregistrer ailleurs.

##### Configuration

La config vit dans `database/config.json` (et non dans une base, voir plus haut). Elle est validée par deux modèles pydantic :

- `DatabaseEntry` : `enabled` et `settings` (dict de valeurs pour la classe `Settings` de l'interface)
- `DatabaseConfig` : `sql_databases`, `vector_databases`, `selected_sql_database` (défaut `"sqlite"`) et `selected_vector_database` (défaut `"lancedb"`). `extra="forbid"` rejette toute clé inconnue.

`initialize_database_config()` s'exécute à l'import et :

1. lit le fichier s'il existe, sinon part d'une config vide ;
2. ajoute une entrée par défaut pour chaque interface découverte ;
3. corrige la sélection si elle pointe vers une interface inexistante (retour à `sqlite`, ou première interface vectorielle disponible) ;
4. réécrit le fichier normalisé.

Le fichier est donc auto-généré et s'auto-répare.

`_settings(module, values)` valide un dict de settings avec la classe `Settings` de l'interface (`exclude_none=True`). Si l'interface n'a pas de `Settings`, il retourne `{}`.

##### État global

À l'import, le module initialise :

| Variable | Description |
|---|---|
| `config` | la `DatabaseConfig` chargée |
| `engine` | l'`Engine` SQLAlchemy de la base SQL sélectionnée |
| `db_url` / `db_type` | URL et nom de la base active |
| `test_engine` | engine SQLite séparé (`storage/lazy_bird_test.db`) pour les tests |
| `status` | `DatabaseStatus(ready, error, revision)`, **non prêt** tant que les migrations n'ont pas été appliquées |

##### Migrations Alembic

- `alembic_config_for(url)` construit la configuration Alembic (`alembic.ini`, dossier `migration/`) pour une URL donnée. L'attribut `url_from_code` indique à `env.py` de ne pas retomber sur l'URL statique de l'ini. C'est la seule façon supportée de créer une config Alembic.
- `selected_sql_url()` retourne l'URL de connexion de l'interface sélectionnée, dans cet ordre de priorité : `url` dans les settings, puis `default_url` du module, puis `db_url`.
- `initialize_selected_sql_database()` :
  1. initialise un nouvel engine à partir de la config ;
  2. exécute `alembic upgrade head` ;
  3. vérifie que la révision courante correspond au head ;
  4. remplace l'engine global (l'ancien est `dispose`) et met `status` à jour.

  En cas d'échec, l'exception est capturée et `status` passe à `ready=False` avec le message d'erreur. La fonction ne lève pas d'exception, elle retourne le `DatabaseStatus`.

##### Accès aux données

- `db()` est un context manager qui fournit une `Session` sur l'engine actif. Il lève une `RuntimeError` si `status.ready` est faux, afin qu'aucune requête ne parte sur une base non migrée.
- `test_db()` fournit une session sur `test_engine`. Les tables sont créées avec `SQLModel.metadata.create_all`, sans passer par Alembic.

```python
with db() as session:
    session.exec(select(Document))
```

##### Basculer et déconnecter

- `switch_database(kind, name, settings)` (`kind` vaut `"sql"` ou `"vector"`) valide les settings puis initialise la nouvelle base.
  - SQL : les migrations ne sont pas appliquées, elles sont seulement **vérifiées**. Si la révision n'est pas au head, l'engine est fermé et une `RuntimeError` est levée. La nouvelle base doit donc être déjà migrée.
  - Dans tous les cas, la sélection est enregistrée dans `config.json`, et la fonction retourne le nom choisi ainsi que les `messages` de l'interface.
- `disconnect_database(kind, name, drop=False)` appelle le `disconnect` de l'interface (`drop=True` vide la base), puis retombe sur la valeur par défaut (`sqlite` ou `lancedb`), réinitialisée et sauvegardée dans la config. Côté SQL, seule la base actuellement sélectionnée peut être déconnectée.
- `adapter_catalog()` retourne pour chaque interface son schéma JSON de `Settings` et ses `messages`. Il sert à construire dynamiquement le formulaire de connexion côté frontend.

##### Vector

`vector_adapter()` retourne le module vectoriel sélectionné et `initialize_selected_vector_database()` l'initialise. `vector_create`, `vector_delete` et `vector_retrieve` délèguent à l'interface active (voir le contrat dans la section vector). Le reste de l'application n'a jamais besoin de savoir quelle base vectorielle est utilisée.

#### Limites 

- 1. __init__.py:
- messages non vérifié : _discover ne vérifie pas messages, alors que switch_database et adapter_catalog l'utilisent. Une interface sans messages passera la découverte et plantera plus tard avec un AttributeError. Ajouter "messages" à required règlerait ça.
- status après bascule : switch_database et disconnect_database ne mettent pas à jour status. Après un changement, status.revision peut donc être périmé.
- 2. db vector interface:
. create: dans le code actuel il retourn 0 si chunks est vide, mais cette fonction ne devrait jamais etre appeler avec des chunks vide, si c'est le cas c'est que les couches superieur du code ont fait une incoherence, dans ce cas on devrait lever une err pour etre plus explicite si chunks est vide
. delete: cette fonction ne devrait jamais appeller avec un model_name qui ne possede aucune table, si c'est le cas c'est une incoherences venant venant des couches superieur, lever une erreur a la place. apres la supression la fonction doit renvoyer le nombre de chunk suprimer a la place

### Migration, Model, Controller, API

#### Model
location: models/
ce sont des ORM represantant une table, en utilisant sqlmodel et sqlalchemy; le ficher __init__.py importe dynamiquement touts les modules ce trouvant dans le repertoire

#### Migration
location: migration/
env.py: il est deja configurer pour etre compatible avec sqlmodel. comme les database du programme peuvent changer dynamiquement rien n'est coder en dur, _resolve_url() permet de recuperer l'url de la db utiliser. le ficher importe aussi models/__init__.py pour pouvoir voir la difference entre l'etat des ORM actuele et le shemas de la db ce qui permet d'utiliser --autogenerate (ne jamais utiliser si les column d'une table sont atypique et toujours verifier le resultat)
remarque: ne JAMAIS ajouter une revision pendant que le server est en marche, car il applique automatiquement les migrations ce qui fait que le ficher de migrations va etre appliquer encore alors qu'il seras encore vide et meme si vous le modifier alembic ne va plus passer dessus, toujours s'assurer de fermer le server.

### Controller

#### Shemas
location: shemas/
ils contient des BaseModel qui represente le format d'entrer et sortit pour les actions crud: NomDuModelIn, NomDuModelOut et NomDuModelUpdate pour les cas plus particulier, toujours ajouter model_config = ConfigDict(from_attrbutes=True)

#### Crud
location: crud/
regroupe toutes le fonction qui servent a effectuer des transaction vers la db, et toutes la logique propre a un model. pour effectuer des requette vers la db on importe la fonction db depuis database/__init__.py, c'est un @contextmanager qui charge une Session sans que les controller ait a ce soucier de quel engine utiliser (utilisation: with db() as session:). toujours utiliser NomDuModelIn ou NomDuModelUpdate comme format d'entrer et NomDuModelOut en sortie ne jamais rien coder en dur:
 - mauvaise pratique:
 ```python
 def create(title, agent_id):
    with db() as session:
        conversation = ConversationORM(title=title, agent_id=agent_id)
    #...
```
```python
def create(conversation_in: ConversationIn):
    with db() as session:
        conversation = ConversationORM(title=conversation_in.title, agent_id=conversation_in.agent_id)
    #...
```
```python
def create(title, agent_id):
  #...
    return {"id": conversation.id, "title": conversation.title}
```

- Bonne pratique:
```python
def create(conversation_in: ConversationIn):
    with db() as session:
        conversation = ConversationORM(**conversation_in.model_dump())
        #...
    return ConversationOut.model_validate(conversation)
```

#### api
location: api/
un module __init__.py importe dynamique toutes les interface ce trouvant dans enpoints/, celles cis doivent avoir une variable router qui est une instance de APIRouter de fastapi et qu'il va inclure dans sont propre router avec include_router()
- interface:
location: api/endpoints
contrat: variable router, instance d'APIrouter avec les attribut prefix et tags
fonctionement: creer des routes pour exposer les fonction crud

#### limites:
- api:
gestion des erreur tres limiter, peut d'enpoint possede des codes d'erreur assez explicite
- controller:
manque des transparance au niveau des erreurs, ce qui resultes a des erreurs silencieuse ou internal server error tres dur a indentifier, ceux doivent contenir des Erreurs custom propre a chaque model et qui recouvre au maximium tout les cas d'usage.

### Models: File, LLMModel et le package embedding/

#### File Model
**Location:** `models/file.py`

Le modèle `File` représente un fichier stocké dans le système. C'est l'entité centrale autour de laquelle s'articule le traitement de documents.

**Champs principaux:**
- `id` : Clé primaire
- `name` : Nom du fichier (sans extension)
- `path` : Chemin absolu vers le fichier stocké
- `extension` : Extension du fichier (ex: `.pdf`, `.txt`, `.md`)
- `size` : Taille en octets
- `status` : État du traitement (`pending`, `processing`, `format-error`, `chunck-error`, `incomplete-vectors`, `done`, `embedding-error`)

**Cycle de vie du status:**
1. `pending` : Fichier uploadé, en attente de traitement
2. `processing` : Chunking en cours
3. `format-error` / `chunck-error` : Échec lors du chunking (format non supporté ou erreur technique)
4. `incomplete-vectors` : Chunking réussi mais embedding partiel/échoué
5. `done` : Traitement complet (chunking + embedding vectoriel)
6. `embedding-error` : Échec lors de la génération d'embeddings

Le modèle `File` est lié aux modèles `Embedded` (relation 1:N) qui représentent les embeddings générés pour ce fichier avec différents modèles LLM.

#### LLMModel
**Location:** `models/llm_model.py`

Le modèle `LLMModel` représente un modèle de langage/embedding disponible dans le système. Il stocke les métadonnées nécessaires pour charger et utiliser le modèle.

**Champs principaux:**
- `id` : Clé primaire
- `name` : Nom lisible du modèle
- `hf_path` : Identifiant Hugging Face (ex: `sentence-transformers/all-MiniLM-L6-v2`)
- `local_path` : Chemin local où le modèle est stocké (cache HF ou téléchargement manuel)
- `dimension` : Dimension des vecteurs d'embedding (ex: 384, 768, 1024)
- `max_context_length` : Longueur maximale de contexte en tokens
- `selected_context` : Contexte réellement utilisé (peut être < max_context_length)
- `formats` : Liste des formats supportés (ex: `["safetensors", "ONNX"]`) - stocké en JSON
- `selected_format` : Format actuellement sélectionné pour l'inférence

**Particularités:**
- La table utilise une contrainte d'unicité implicite sur `hf_path` + `local_path` via la logique métier
- `selected_format` doit être l'un des formats listés dans `formats`
- Le modèle est découvert soit par téléchargement HF (`download_model`), soit par scan du cache local (`hf_cache_worker`)

#### Package embedding/
**Location:** `embedding/`

Le package `embedding` gère la génération de vecteurs d'embedding à partir de chunks de texte. Il suit le pattern d'interface dynamique du projet.

**Architecture:**
```
embedding/
├── __init__.py           # Point d'entrée: initialize_embedding_engines, generate_embeddings, generate_query_embedding
└── engines/
    ├── __init__.py       # detect_device() - détection automatique CUDA/MPS/CPU
    └── sentence_transformers.py  # Implémentation actuelle (seule engine)
```

**Fonctionnement:**
1. **Découverte des engines** : `initialize_embedding_engines()` scanne `embedding/engines/` via `pkgutil`, importe chaque module (ignorant ceux préfixés `_`), et enregistre le moteur via `engine_crud.upsert(name, file_path, formats)`.

2. **Contrat d'un engine** : Chaque module dans `engines/` doit exposer:
   - `name` : Identifiant unique (ex: `"sentence-transformers"`)
   - `formats` : Liste des formats supportés (ex: `["safetensors", "ONNX"]`)
   - `EngineSettings` : Pydantic BaseModel pour valider la configuration
   - `validate_kwargs(kwargs)` : Validation de la config
   - `embed(docs, ctx_size, batch_size, settings)` : Fonction principale retournant `list[list[float]]`

3. **Génération d'embeddings** : `generate_embeddings(chunks)` :
   - Récupère le moteur sélectionné + le modèle LLM sélectionné + sa config
   - Injecte `model_path` (local_path du LLMModel) dans les settings
   - Traite les chunks par batchs (`batch_size` configurable)
   - Retourne `[{**chunk, "vector": vector}, ...]`

4. **Embedding de requête** : `generate_query_embedding(query)` utilise le même contexte pour vectoriser une requête utilisateur.

**Extensibilité :** Ajouter un nouvel engine = créer un fichier dans `engines/` respectant le contrat. Aucune modification du code central n'est nécessaire.

### Tools: model_extraction et hf_cache_worker

#### model_extraction.py
**Location:** `tools/model_extraction.py`

Module utilitaire pour télécharger et inspecter des modèles Hugging Face.

**Fonctions:**
- `download_model(hf_path, local_dir=None)` : Télécharge un modèle via `huggingface_hub.snapshot_download`. Retourne le chemin local.
- `extract(local_path)` : Lit `config.json` du modèle local et extrait les métadonnées clés:
  - `formats` : Détecte `safetensors` (toujours) + `ONNX` (si dossier `onnx/` existe)
  - `name` : `_name_or_path` du config
  - `dimension` : `hidden_size`
  - `max_context_length` : `max_position_embeddings`

**Utilisation :** Appelé par `llm_model_crud.create()` (téléchargement + extraction) et `llm_model_crud.create_from_local_path()` (extraction seule). Sert à peupler automatiquement les champs du modèle `LLMModel`.

#### hf_cache_worker.py
**Location:** `tools/hf_cache_worker.py`

Worker de synchronisation qui scanne le cache Hugging Face local (`~/.cache/huggingface/hub`) et importe automatiquement les modèles trouvés dans la base de données.

**Fonctionnement:**
1. `find_cached_model_paths(cache_path)` : Parcourt le cache HF, identifie les dossiers `models--*`, extrait le `repo_id` (ex: `sentence-transformers/all-MiniLM-L6-v2`), et trouve le snapshot unique dans `snapshots/`. Retourne `[(hf_path, local_path), ...]`.

2. `sync_cached_models(cache_path)` : 
   - Récupère les `local_path` déjà connus en base (`llm_model_crud.get_all()`)
   - Pour chaque modèle du cache non encore en base : appelle `llm_model_crud.create_from_local_path(hf_path, local_path)`
   - Gère les erreurs silencieusement (log warning) : modèle corrompu, config.json manquant, etc.
   - Retourne le nombre de modèles nouvellement créés

**Intégration :** Peut être appelé manuellement via API/CLI, ou planifié comme tâche périodique pour maintenir la base à jour avec les modèles téléchargés en dehors de l'application.

### Préférences: preference.yaml, preferences.py et task_queue.py

#### preference.yaml
**Location:** `preference.yaml` (à la racine de `src/lazy_bird/`)

Fichier de configuration YAML simple pour les préférences globales de l'application.

**Structure actuelle:**
```yaml
auto-embedding:
  enable: true
```

**Design :** Extensible - de nouvelles sections peuvent être ajoutées sans migration de schéma. Le fichier est lu/écrit atomiquement par `preferences.py`.

#### preferences.py
**Location:** `preferences.py`

Module de gestion des préférences - façade unique pour lire/écrire `preference.yaml`.

**Fonctions principales:**
- `_read_preferences()` : Lecture brute du YAML, retourne `dict`
- `get_preferences()` : Accès lecture complet
- `update_preferences(values)` : Écriture atomique (écrase le fichier), retourne `True` si modifié
- `auto_embedding_enabled()` : Accès typé à `auto-embedding.enable` (gère aussi l'alias `enabled`), validation booléenne
- `auto_embedding()` : Si activé, appelle `file_crud.enqueue_files_requiring_embedding()` pour mettre en file d'attente les fichiers nécessitant un (ré)embedding
- `apply_preferences()` : Point d'entrée unique - applique toutes les préférences actives (actuellement seulement auto-embedding), retourne la liste des `file_id` enfileés

**Pattern :** Séparation lecture/écriture, validation stricte des types, valeurs par défaut sensées. Sert de "source of truth" pour la configuration runtime.

#### task_queue.py
**Location:** `task_queue.py`

Système de file d'attente asynchrone basé sur **Huey** (backend SQLite) pour le traitement lourd (chunking + embedding) en arrière-plan.

**Composants:**
- `huey` : Instance `SqliteHuey` configurée avec `LAZY_BIRD_QUEUE_DB` ou chemin par défaut (`database/storage/lazy_bird_queue.db`)
- `process_file_task(file_id)` : Tâche Huey principale
  1. Initialise la DB SQL (migrations incluses)
  2. Initialise les engines d'embedding
  3. Initialise la DB vectorielle + populate les tables
  4. Exécute `process_file(file_id)` (async) via `asyncio.run()`
- `enqueue_file(file_id)` : Enfile une tâche, retourne le `Task` Huey
- `queued_file_ids()` : Retourne l'ensemble des `file_id` actuellement en attente dans la queue
- `start_worker()` : Lance un process `multiprocessing.Process` exécutant le consumer Huey (1 worker thread)
- `stop_worker(worker)` : Arrêt propre (terminate + join timeout 5s)

**Flux complet (auto-embedding) :**
1. `preferences.apply_preferences()` → `file_crud.enqueue_files_requiring_embedding()`
2. `file_crud.files_requiring_embedding()` identifie les fichiers `pending` + `done` sans embedding valide pour le modèle sélectionné + DB vectorielle active
3. `enqueue_file()` ajoute chaque fichier à la queue Huey (déduplication via `queued_file_ids()`)
4. Worker Huey (processus séparé) défile et exécute `process_file_task`
5. `process_file` (dans `crud/file_processing.py`) : chunking → embedding → stockage vectoriel → MAJ statuts

**Avantages :** Découplage total API ↔ traitement lourd, résilience (retry Huey), scalabilité (workers multiples possibles), persistance SQLite (survit au redémarrage).

###