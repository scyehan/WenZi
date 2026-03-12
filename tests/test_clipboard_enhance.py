"""Tests for clipboard AI enhancement feature."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# Mock AppKit/Foundation before importing modules that use them
@pytest.fixture(autouse=True)
def mock_appkit(monkeypatch):
    """Provide mock AppKit and Foundation modules for headless testing."""
    mock_appkit_mod = MagicMock()
    mock_appkit_mod.NSCommandKeyMask = 1 << 20
    mock_appkit_mod.NSShiftKeyMask = 1 << 17
    mock_appkit_mod.NSDeviceIndependentModifierFlagsMask = 0xFFFF0000
    mock_appkit_mod.NSKeyDownMask = 1 << 10

    modules = {
        "AppKit": mock_appkit_mod,
        "Foundation": MagicMock(),
        "objc": MagicMock(),
        "PyObjCTools": MagicMock(),
        "PyObjCTools.AppHelper": MagicMock(),
    }

    for name, mod in modules.items():
        monkeypatch.setitem(__import__("sys").modules, name, mod)


class TestClipboardPublicFunctions:
    """Test public clipboard read/write functions in input.py."""

    @patch("voicetext.input.NSPasteboard")
    def test_get_clipboard_text(self, mock_pb_cls):
        from voicetext.input import get_clipboard_text

        mock_pb = MagicMock()
        mock_pb_cls.generalPasteboard.return_value = mock_pb
        mock_pb.stringForType_.return_value = "hello clipboard"

        result = get_clipboard_text()
        assert result == "hello clipboard"

    @patch("voicetext.input.NSPasteboard")
    def test_get_clipboard_text_empty(self, mock_pb_cls):
        from voicetext.input import get_clipboard_text

        mock_pb = MagicMock()
        mock_pb_cls.generalPasteboard.return_value = mock_pb
        mock_pb.stringForType_.return_value = None

        result = get_clipboard_text()
        assert result is None

    @patch("voicetext.input.NSString")
    @patch("voicetext.input.NSPasteboard")
    def test_set_clipboard_text(self, mock_pb_cls, mock_nsstr):
        from voicetext.input import set_clipboard_text

        mock_pb = MagicMock()
        mock_pb_cls.generalPasteboard.return_value = mock_pb
        mock_nsstr.stringWithString_.return_value = "enhanced text"

        set_clipboard_text("enhanced text")

        mock_pb.clearContents.assert_called_once()
        # Should set string without concealed markers
        assert mock_pb.setString_forType_.call_count == 1

    @patch("voicetext.input.NSPasteboardTypeString", "public.utf8-plain-text")
    @patch("voicetext.input.NSPasteboard")
    def test_has_clipboard_text_true(self, mock_pb_cls):
        from voicetext.input import has_clipboard_text

        mock_pb = MagicMock()
        mock_pb_cls.generalPasteboard.return_value = mock_pb
        mock_pb.availableTypeFromArray_.return_value = "public.utf8-plain-text"

        assert has_clipboard_text() is True

    @patch("voicetext.input.NSPasteboardTypeString", "public.utf8-plain-text")
    @patch("voicetext.input.NSPasteboard")
    def test_has_clipboard_text_false_for_image(self, mock_pb_cls):
        from voicetext.input import has_clipboard_text

        mock_pb = MagicMock()
        mock_pb_cls.generalPasteboard.return_value = mock_pb
        mock_pb.availableTypeFromArray_.return_value = None

        assert has_clipboard_text() is False


class TestClipboardEnhanceValidation:
    """Test clipboard content validation before enhancement."""

    @pytest.fixture(autouse=True)
    def mock_appkit(self):
        """Override the module-level autouse fixture — not needed here."""
        pass

    def _make_app(self):
        """Create a minimal mock of VoiceTextApp for testing clipboard validation."""
        from voicetext.app import VoiceTextApp

        app = MagicMock(spec=[])
        app._busy = False
        app._CLIPBOARD_MAX_CHARS = VoiceTextApp._CLIPBOARD_MAX_CHARS
        # Bind the real main-thread method to our mock
        app._on_clipboard_enhance_main = (
            VoiceTextApp._on_clipboard_enhance_main.__get__(app)
        )
        return app

    def test_non_text_clipboard_shows_alert(self):
        with patch("voicetext.app.has_clipboard_text", return_value=False):
            app = self._make_app()
            app._topmost_alert = MagicMock()
            app._restore_accessory = MagicMock()

            app._on_clipboard_enhance_main()

            app._topmost_alert.assert_called_once()
            assert "Not Supported" in app._topmost_alert.call_args[1]["title"]
            app._restore_accessory.assert_called_once()

    def test_empty_text_clipboard_shows_alert(self):
        with patch("voicetext.app.has_clipboard_text", return_value=True), \
             patch("voicetext.app.get_clipboard_text", return_value=""):
            app = self._make_app()
            app._topmost_alert = MagicMock()
            app._restore_accessory = MagicMock()

            app._on_clipboard_enhance_main()

            app._topmost_alert.assert_called_once()
            assert "Empty" in app._topmost_alert.call_args[1]["title"]
            app._restore_accessory.assert_called_once()

    def test_long_text_shows_alert_and_aborts(self):
        with patch("voicetext.app.has_clipboard_text", return_value=True), \
             patch("voicetext.app.get_clipboard_text", return_value="x" * 301):
            app = self._make_app()
            app._topmost_alert = MagicMock()
            app._restore_accessory = MagicMock()

            app._on_clipboard_enhance_main()

            app._topmost_alert.assert_called_once()
            assert "301" in app._topmost_alert.call_args[1]["message"]
            app._restore_accessory.assert_called_once()
            assert not app._busy

    def test_normal_text_proceeds_without_alert(self):
        with patch("voicetext.app.has_clipboard_text", return_value=True), \
             patch("voicetext.app.get_clipboard_text", return_value="short text"), \
             patch("voicetext.app.rumps") as mock_rumps, \
             patch("threading.Thread") as mock_thread:
            app = self._make_app()
            app._set_status = MagicMock()
            mock_thread.return_value.start = MagicMock()

            app._on_clipboard_enhance_main()

            mock_rumps.alert.assert_not_called()
            assert app._busy is True

    def test_busy_skips(self):
        app = self._make_app()
        app._busy = True
        app._on_clipboard_enhance_main()

    def test_dispatches_to_main_thread(self):
        """Verify _on_clipboard_enhance dispatches via AppHelper.callAfter."""
        from voicetext.app import VoiceTextApp

        app = MagicMock()
        app._on_clipboard_enhance = VoiceTextApp._on_clipboard_enhance.__get__(app)

        mock_helper = MagicMock()
        mock_pyobjc = MagicMock()
        mock_pyobjc.AppHelper = mock_helper
        with patch.dict("sys.modules", {
            "PyObjCTools": mock_pyobjc,
            "PyObjCTools.AppHelper": mock_helper,
        }):
            app._on_clipboard_enhance()
            mock_helper.callAfter.assert_called_once_with(app._on_clipboard_enhance_main)


class TestPreviewPanelClipboardSource:
    """Test Preview panel behavior with source='clipboard'."""

    def _setup_panel(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()
        panel._final_text_field = MagicMock()
        return panel

    def test_source_defaults_to_voice(self):
        panel = self._setup_panel()

        panel.show(
            asr_text="hello",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._source == "voice"

    def test_source_clipboard_stored(self):
        panel = self._setup_panel()

        panel.show(
            asr_text="clipboard text",
            show_enhance=True,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
            source="clipboard",
        )

        assert panel._source == "clipboard"

    def test_clipboard_source_no_wav_data(self):
        panel = self._setup_panel()

        panel.show(
            asr_text="clipboard text",
            show_enhance=True,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
            source="clipboard",
            asr_wav_data=None,
        )

        assert panel._asr_wav_data is None
        assert panel._source == "clipboard"


class TestClipboardEnhanceConfig:
    """Test clipboard_enhance config defaults."""

    def test_default_config_has_clipboard_enhance(self):
        from voicetext.config import DEFAULT_CONFIG

        assert "clipboard_enhance" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["clipboard_enhance"]["hotkey"] == "ctrl+cmd+v"
        assert DEFAULT_CONFIG["clipboard_enhance"]["output"] == "clipboard"

    def test_config_merge_preserves_clipboard_enhance(self):
        from voicetext.config import _merge_dict, DEFAULT_CONFIG

        overrides = {
            "clipboard_enhance": {
                "hotkey": "ctrl+shift+v",
                "output": "type_text",
            }
        }
        result = _merge_dict(DEFAULT_CONFIG, overrides)
        assert result["clipboard_enhance"]["hotkey"] == "ctrl+shift+v"
        assert result["clipboard_enhance"]["output"] == "type_text"
