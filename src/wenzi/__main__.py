"""PyInstaller entry point - uses absolute imports."""

import os

# Ensure urllib/ssl can find CA certificates in PyInstaller bundles.
# Without this, urllib.request fails with SSL: CERTIFICATE_VERIFY_FAILED
# because the bundled Python cannot locate the system CA store.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass


def main():
    from wenzi.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
