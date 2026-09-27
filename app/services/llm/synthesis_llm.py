"""Hosted synthesis, kept separate from embeddings and vector storage."""
import logging

from huggingface_hub import InferenceClient

from app.core.config import settings
from app.core.exceptions import UmbraError

logger = logging.getLogger(__name__)


class SynthesisLLM:
    def __init__(self):
        self.model_name = (settings.HUGGINGFACE_SYNTHESIS_MODEL or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.model_name and (settings.HUGGINGFACE_API_TOKEN or "").strip())

    def generate(self, prompt: str, *, system_prompt: str = "Answer using only the supplied context.") -> str:
        if not self.configured:
            raise UmbraError("AI summaries are not configured.", status_code=503)
        try:
            client = InferenceClient(
                model=self.model_name, token=settings.HUGGINGFACE_API_TOKEN,
                provider=settings.HUGGINGFACE_INFERENCE_PROVIDER,
                timeout=settings.BRIEF_LLM_TIMEOUT_SECONDS,
            )
            response = client.chat_completion(
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": prompt}],
                max_tokens=384, temperature=0.2,
            )
            choice = response.choices[0]
            content = choice.message.content
            if choice.finish_reason != "stop" or not isinstance(content, str) or not content.strip():
                raise ValueError("Incomplete model response")
            text = content.strip()
            if len(text) > 2400:
                raise ValueError("Model response exceeded the brief limit")
            return text
        except Exception as exc:
            # Provider exceptions can include prompts, URLs or credentials. Never log
            # their message/traceback or return it to the browser.
            logger.warning("Brief synthesis failed (%s)", type(exc).__name__)
            raise UmbraError("AI summary unavailable. Showing your daily overview instead.", status_code=502) from None
