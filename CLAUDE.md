# VoiceText - Claude Code Instructions

## UI Dialogs

This is a macOS statusbar (accessory) app. Standard `rumps.alert()` / `rumps.notification()` dialogs will not appear on screen because the app has no foreground presence.

When you need to show a user-facing dialog (error, warning, confirmation), use `self._topmost_alert()` instead. It activates the app, sets `NSStatusWindowLevel`, and runs a modal `NSAlert` so the dialog is always visible. Call `self._restore_accessory()` afterward to return to statusbar-only mode.

```python
self._topmost_alert(title="...", message="...")
self._restore_accessory()
```

`rumps.notification()` will crash with `Info.plist` / `CFBundleIdentifier` errors when running directly from the terminal (`uv run`) without app bundling. This is expected during development — wrap calls in try/except and log the error instead of crashing. In a packaged app `rumps.notification()` works normally, so it is fine to use for non-critical user feedback.

## Dark Mode Support

All UI must support macOS dark mode. Follow these rules when writing UI code:

- **Use system semantic colors** (`NSColor.labelColor()`, `NSColor.secondaryLabelColor()`, `NSColor.textBackgroundColor()`, `NSColor.windowBackgroundColor()`, etc.) instead of hardcoded RGB values. System colors adapt automatically to light/dark appearance.
- **Never use `NSColor.blackColor()` or `NSColor.whiteColor()`** for text or backgrounds — they do not adapt. Use `NSColor.labelColor()` and `NSColor.textBackgroundColor()` instead.
- **For custom colors that must differ between modes**, use a dynamic color provider:
  ```python
  def _dynamic_color(light_rgba, dark_rgba):
      def provider(appearance):
          name = appearance.bestMatchFromAppearancesWithNames_([
              NSAppearanceNameAqua, NSAppearanceNameDarkAqua
          ])
          return NSColor.colorWithSRGBRed_green_blue_alpha_(
              *(dark_rgba if name == NSAppearanceNameDarkAqua else light_rgba)
          )
      return NSColor.colorWithName_dynamicProvider_("custom", provider)
  ```
- **Avoid deprecated `colorWithCalibratedRed_green_blue_alpha_`** — use `colorWithSRGBRed_green_blue_alpha_` or system semantic colors.
- See `result_window.py` for a good reference implementation of dark mode support.

## Usage Statistics

When adding new user-facing behaviors or interactions, always add corresponding tracking to `UsageStats` (`src/voicetext/usage_stats.py`):

1. Add counter(s) to `_empty_totals()`
2. Add a `record_*()` method in `UsageStats`
3. Call the method at the appropriate point in `app.py`
4. Update the stats display in `_on_show_usage_stats()`
5. Add tests in `tests/test_usage_stats.py`

## Release Process

1. Ensure all changes are committed and tests pass (`uv run pytest tests/`)
2. Update version in `pyproject.toml` (single source of truth — all other files read from it dynamically)
3. Commit: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push && git push --tags`
