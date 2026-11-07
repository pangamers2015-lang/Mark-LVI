class BargeInDetector:
    """Require sustained, echo-filtered speech before cutting off playback."""

    def __init__(self) -> None:
        self._blocks: list[bytes] = []

    def reset(self) -> None:
        self._blocks.clear()

    def observe(self, pcm: bytes, is_user_speech: bool, required_blocks: int) -> list[bytes] | None:
        if not is_user_speech:
            self.reset()
            return None
        self._blocks.append(bytes(pcm))
        if len(self._blocks) < max(1, int(required_blocks)):
            return None
        captured = list(self._blocks)
        self.reset()
        return captured
