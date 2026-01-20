"""Python bindings for jmespath.rs - a fast Rust implementation of JMESPath.

This module provides a high-performance JMESPath implementation written in Rust,
accessible from Python via PyO3 bindings.

Example:
    >>> from jmespath_rust import search, compile
    >>>
    >>> # One-shot search
    >>> search("foo.bar", {"foo": {"bar": "baz"}})
    'baz'
    >>>
    >>> # Compile for repeated use
    >>> expr = compile("people[*].name")
    >>> expr.search({"people": [{"name": "Alice"}, {"name": "Bob"}]})
    ['Alice', 'Bob']
"""

from jmespath_rust._internal import Expression, compile, search, search_json

__all__ = ["Expression", "compile", "search", "search_json"]
__version__ = "0.5.0"
