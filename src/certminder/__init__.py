"""certminder: continuous TLS certificate monitoring built on top of certinspect."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("certminder")
except PackageNotFoundError:  # running from a source checkout without an install
    __version__ = "0.0.0"
