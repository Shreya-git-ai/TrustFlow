class FakeProvider:
    name = "fake"

    def __init__(self, responses: list):
        self.responses = list(responses)  # strings, or Exceptions to raise
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, timeout_s: float = 30.0) -> str:
        self.calls.append((system, user))
        if not self.responses:
            raise RuntimeError("FakeProvider ran out of responses")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r