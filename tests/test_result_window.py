"""Tests for the result preview panel."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


# Mock AppKit/Foundation before importing the module
@pytest.fixture(autouse=True)
def mock_appkit(monkeypatch):
    """Provide mock AppKit and Foundation modules for headless testing."""
    mock_nsobj = MagicMock()

    modules = {
        "AppKit": MagicMock(),
        "Foundation": MagicMock(),
        "objc": MagicMock(),
        "PyObjCTools": MagicMock(),
        "PyObjCTools.AppHelper": MagicMock(),
    }

    for name, mod in modules.items():
        monkeypatch.setitem(__import__("sys").modules, name, mod)


class TestResultPreviewPanelCallbacks:
    """Test confirm/cancel callback mechanism."""

    def test_confirm_triggers_callback_with_text(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        confirmed_text = []

        # Mock the panel build to avoid AppKit calls
        panel._build_panel = MagicMock()
        panel._final_text_view = MagicMock()
        panel._final_text_view.string.return_value = "final text"
        panel._panel = MagicMock()

        panel.show(
            asr_text="raw asr",
            show_enhance=False,
            on_confirm=lambda t, info=None: confirmed_text.append(t),
            on_cancel=MagicMock(),
        )

        panel.confirmClicked_(None)

        assert confirmed_text == ["final text"]

    def test_cancel_triggers_callback(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        cancelled = []

        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="raw asr",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=lambda: cancelled.append(True),
        )

        panel.cancelClicked_(None)

        assert cancelled == [True]

    def test_confirm_closes_panel(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        mock_panel = MagicMock()
        panel._panel = mock_panel
        panel._final_text_view = MagicMock()
        panel._final_text_view.string.return_value = "text"

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        panel.confirmClicked_(None)

        mock_panel.orderOut_.assert_called_once_with(None)

    def test_cancel_closes_panel(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        mock_panel = MagicMock()
        panel._panel = mock_panel

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        panel.cancelClicked_(None)

        mock_panel.orderOut_.assert_called_once_with(None)


class TestResultPreviewPanelCorrectionInfo:
    """Test correction_info passed via on_confirm callback."""

    def test_correction_info_when_user_edited_with_enhance(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()
        panel._final_text_view = MagicMock()
        panel._final_text_view.string.return_value = "user corrected"
        panel._enhance_text_view = MagicMock()
        panel._enhance_text_view.string.return_value = "ai enhanced"

        results = []

        panel.show(
            asr_text="raw asr",
            show_enhance=True,
            on_confirm=lambda text, info: results.append((text, info)),
            on_cancel=MagicMock(),
        )

        # Simulate user editing
        panel._on_user_edit()
        panel.confirmClicked_(None)

        assert len(results) == 1
        text, info = results[0]
        assert text == "user corrected"
        assert info is not None
        assert info["asr_text"] == "raw asr"
        assert info["enhanced_text"] == "ai enhanced"
        assert info["final_text"] == "user corrected"

    def test_correction_info_none_when_not_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()
        panel._final_text_view = MagicMock()
        panel._final_text_view.string.return_value = "text"
        panel._enhance_text_view = MagicMock()

        results = []

        panel.show(
            asr_text="raw asr",
            show_enhance=True,
            on_confirm=lambda text, info: results.append((text, info)),
            on_cancel=MagicMock(),
        )

        # No user edit
        panel.confirmClicked_(None)

        assert results[0][1] is None

    def test_correction_info_none_when_no_enhance(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()
        panel._final_text_view = MagicMock()
        panel._final_text_view.string.return_value = "text"

        results = []

        panel.show(
            asr_text="raw asr",
            show_enhance=False,
            on_confirm=lambda text, info: results.append((text, info)),
            on_cancel=MagicMock(),
        )

        panel._on_user_edit()
        panel.confirmClicked_(None)

        assert results[0][1] is None


class TestResultPreviewPanelEnhanceUpdate:
    """Test AI enhancement result update logic."""

    def test_set_enhance_result_updates_text_when_not_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = False
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_view = MagicMock()

        # Simulate callAfter executing immediately
        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("enhanced text")

        panel._enhance_text_view.setString_.assert_called_with("enhanced text")
        panel._final_text_view.setString_.assert_called_with("enhanced text")

    def test_set_enhance_result_skips_final_when_user_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = True
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_view = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("enhanced text")

        panel._enhance_text_view.setString_.assert_called_with("enhanced text")
        panel._final_text_view.setString_.assert_not_called()

    def test_set_enhance_result_updates_label(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = False
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_view = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("done")

        panel._enhance_label.setStringValue_.assert_called_with("AI Enhancement")

    def test_set_enhance_result_noop_when_no_enhance_view(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._enhance_text_view = None

        # Should not raise
        panel.set_enhance_result("text")


class TestResultPreviewPanelUserEdit:
    """Test user edit tracking."""

    def test_user_edit_flag_set_on_edit(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        assert panel._user_edited is False

        panel._on_user_edit()

        assert panel._user_edited is True

    def test_user_edit_flag_reset_on_show(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = True
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="text",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._user_edited is False


class TestResultPreviewPanelLayout:
    """Test layout switching based on show_enhance."""

    def test_show_enhance_false_hides_enhance_section(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="text",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._show_enhance is False

    def test_show_enhance_true_shows_enhance_section(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="text",
            show_enhance=True,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._show_enhance is True


class TestResultPreviewPanelThreading:
    """Test that callbacks work correctly with threading.Event pattern."""

    def test_confirm_unblocks_waiting_thread(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()
        panel._final_text_view = MagicMock()
        panel._final_text_view.string.return_value = "result"

        event = threading.Event()
        result_holder = {"text": None}

        def on_confirm(text, correction_info=None):
            result_holder["text"] = text
            event.set()

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=on_confirm,
            on_cancel=lambda: event.set(),
        )

        # Simulate confirm from another thread
        panel.confirmClicked_(None)

        assert event.wait(timeout=1)
        assert result_holder["text"] == "result"

    def test_cancel_unblocks_waiting_thread(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        event = threading.Event()
        cancelled = []

        def on_cancel():
            cancelled.append(True)
            event.set()

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=lambda t, info=None: event.set(),
            on_cancel=on_cancel,
        )

        panel.cancelClicked_(None)

        assert event.wait(timeout=1)
        assert cancelled == [True]
