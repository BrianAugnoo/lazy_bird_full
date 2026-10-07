from lazy_bird.api.engine_routes import engine_router
from lazy_bird.embedding import engine_family
from lazy_bird.schemas.embedding_engine import PresetEmbeddingIn, PresetEmbeddingOut, PresetEmbeddingUpdate

router = engine_router(
    engine_family,
    engines_prefix="/embedding-engines",
    presets_prefix="/embedding-presets",
    tag="embedding",
    preset_in=PresetEmbeddingIn,
    preset_update=PresetEmbeddingUpdate,
    preset_out=PresetEmbeddingOut,
)
