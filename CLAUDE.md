# VoiceText - Claude Code Instructions

## UI Dialogs

This is a macOS statusbar (accessory) app. Standard `rumps.alert()` / `rumps.notification()` dialogs will not appear on screen because the app has no foreground presence.

When you need to show a user-facing dialog (error, warning, confirmation), use `self._topmost_alert()` instead. It activates the app, sets `NSStatusWindowLevel`, and runs a modal `NSAlert` so the dialog is always visible. Call `self._restore_accessory()` afterward to return to statusbar-only mode.

```python
self._topmost_alert(title="...", message="...")
self._restore_accessory()
```

`rumps.notification()` will crash with `Info.plist` / `CFBundleIdentifier` errors when running directly from the terminal (`uv run`) without app bundling. This is expected during development — wrap calls in try/except and log the error instead of crashing. In a packaged app `rumps.notification()` works normally, so it is fine to use for non-critical user feedback.

## Release Process

1. Ensure all changes are committed and tests pass (`uv run pytest tests/`)
2. Update version in `pyproject.toml` (single source of truth — all other files read from it dynamically)
3. Commit: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push && git push --tags`
