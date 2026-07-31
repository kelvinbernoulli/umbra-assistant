from typing import Dict


class PromptTemplates:
    @staticmethod
    def morning_brief_context(events: list[Dict]) -> str:
        return "Write a concise morning brief from these events."
