from core.echo import BargeInDetector


def test_barge_in_requires_sustained_confirmed_speech():
    detector = BargeInDetector()

    assert detector.observe(b"one", True, 3) is None
    assert detector.observe(b"two", True, 3) is None
    assert detector.observe(b"three", True, 3) == [b"one", b"two", b"three"]


def test_non_speech_resets_candidate_audio():
    detector = BargeInDetector()

    assert detector.observe(b"echo", True, 2) is None
    assert detector.observe(b"noise", False, 2) is None
    assert detector.observe(b"user-one", True, 2) is None
    assert detector.observe(b"user-two", True, 2) == [b"user-one", b"user-two"]


def test_required_blocks_is_never_zero():
    detector = BargeInDetector()

    assert detector.observe(b"speech", True, 0) == [b"speech"]
