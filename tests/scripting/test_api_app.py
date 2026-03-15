"""Tests for vt.app API."""

from voicetext.scripting.api.app import AppAPI


class TestAppAPI:
    def test_launch_returns_bool(self):
        api = AppAPI()
        # In test env without real AppKit, launch returns False gracefully
        result = api.launch("NonexistentApp")
        assert isinstance(result, bool)

    def test_frontmost_returns_none_on_error(self):
        api = AppAPI()
        # In test environment without AppKit, should return None gracefully
        result = api.frontmost()
        # Either returns a string or None, should not raise
        assert result is None or isinstance(result, str)
