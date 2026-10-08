from lazy_bird.api.engine_routes import engine_router
from lazy_bird.cross_encoder import engine_family
from lazy_bird.schemas.cross_encoder_engine import PresetCrossEncoderIn, PresetCrossEncoderOut, PresetCrossEncoderUpdate

router = engine_router(
    engine_family,
    engines_prefix="/cross-encoder-engines",
    presets_prefix="/cross-encoder-presets",
    tag="cross-encoder",
    preset_in=PresetCrossEncoderIn,
    preset_update=PresetCrossEncoderUpdate,
    preset_out=PresetCrossEncoderOut,
)
