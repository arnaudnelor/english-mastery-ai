"""Minimal, self-written stand-in for the `python-multipart` package, used only by the browser preview.

It implements exactly the interface Starlette's form parser uses (MultipartParser,
QuerystringParser, parse_options_header). The request body arrives whole in the preview,
so parts are parsed as soon as the closing boundary has been received.
"""
__version__ = "0.0.99-preview"

from .multipart import MultipartParser, QuerystringParser, parse_options_header  # noqa: E402,F401
