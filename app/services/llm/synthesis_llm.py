from app.core.config import settings
from app.core.exceptions import UmbraError


class SynthesisLLM:
    def __init__(self):
        self.model_name = settings.HUGGINGFACE_SYNTHESIS_MODEL

    def generate(self, prompt: str) -> str:
        raise UmbraError("Response synthesis is not implemented.", status_code=501)
