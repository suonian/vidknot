"""Subscription source configuration.

A subscription source describes *which* URLs or channels the research
platform should monitor or fetch. This module is the framework: it
defines the configuration schema, validates user input, and provides
loaders for common formats. Concrete account lists, cookies, and
identifiers must live in a user-supplied configuration file that is
**not** tracked by version control.
"""

from .schema import (
    SourceConfig,
    SourceKind,
    SourcesFile,
    load_sources_file,
    validate_source,
)

__all__ = [
    "SourceConfig",
    "SourceKind",
    "SourcesFile",
    "load_sources_file",
    "validate_source",
]
