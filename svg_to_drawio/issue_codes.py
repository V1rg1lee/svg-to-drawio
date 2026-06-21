"""Shared diagnostic issue codes used by emitters and `capability_registry.py`.

Each code used to be duplicated as a literal string at every `_record_issue`/`add_issue`
call site *and* again as a dict key in `capability_registry.py`'s `_ISSUE_MAP`. A typo or
a renamed code in only one of those places compiled and ran fine, but silently dropped the
issue from the compatibility matrix (`issue_observation_payload` falls through to `None`
for an unmapped code). Importing these constants instead means a rename that misses a call
site raises `ImportError`/`AttributeError` immediately instead of failing silently.
"""

from __future__ import annotations

CLIP_PATH_SIMPLIFIED_NATIVE = "clip-path-simplified-native"
MASK_SIMPLIFIED_NATIVE = "mask-simplified-native"
PATTERN_SIMPLIFIED_NATIVE = "pattern-simplified-native"
CLIP_PATH_FALLBACK = "clip-path-fallback"
MASK_FALLBACK = "mask-fallback"
PATTERN_FALLBACK = "pattern-fallback"
FILTER_FALLBACK = "filter-fallback"
FILTER_IGNORED_FOR_EDITABILITY = "filter-ignored-for-editability"
FILTER_SIMPLIFIED_NATIVE = "filter-simplified-native"
MULTI_STOP_GRADIENT_FALLBACK = "multi-stop-gradient-fallback"
MULTI_STOP_GRADIENT_REDUCED = "multi-stop-gradient-reduced"
TEXT_BACKEND_HEURISTIC = "text-backend-heuristic"
TEXT_BACKEND_SYSTEM = "text-backend-system"
TEXT_PATH_APPROXIMATED = "text-path-approximated"
DOMINANT_BASELINE_APPROXIMATED = "dominant-baseline-approximated"
LETTER_SPACING_IGNORED = "letter-spacing-ignored"
LETTER_SPACING_APPROXIMATED = "letter-spacing-approximated"
TEXT_LENGTH_APPROXIMATED = "text-length-approximated"
FOREIGN_OBJECT_TEXT_APPROXIMATED = "foreign-object-text-approximated"
IMAGE_SHEAR_APPROXIMATED = "image-shear-approximated"
IMAGE_REMOTE_LINKED = "image-remote-linked"
MAX_ELEMENTS_TRUNCATED = "max-elements-truncated"
FALLBACK_BOUNDS_MISSING = "fallback-bounds-missing"
USE_CYCLE_DETECTED = "use-cycle-detected"
IGNORED_UNSUPPORTED_ELEMENT = "ignored-unsupported-element"
CONVERSION_FAILED = "conversion-failed"
ANALYSIS_FAILED = "analysis-failed"
