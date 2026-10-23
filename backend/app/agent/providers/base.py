from typing import Protocol


class ModelProvider(Protocol):
    name: str

    def complete_json(self, system: str, user: str, timeout_s: float = 30.0) -> str:
        """Return the model's raw text. Parsing and validation happen in the orchestrator."""
        ...