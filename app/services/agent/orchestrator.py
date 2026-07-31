from app.services.llm.synthesis_llm import SynthesisLLM


class Orchestrator:
    def __init__(self):
        self.llm = SynthesisLLM()

    async def run_command(self, text: str) -> str:
        return self.llm.generate(text)
