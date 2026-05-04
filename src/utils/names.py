"""
Human-readable random name generator.

Produces adjective-noun pairs like "silent-ember" or "lucid-tide".
~200 adjectives × ~200 nouns = ~40,000 combinations — low collision
probability for experiment IDs, run labels, and ephemeral identifiers.

Usage:
    from src.utils.names import generate_name
    name = generate_name()           # e.g. "hollow-ridge"
    name = generate_name(sep="_")    # e.g. "hollow_ridge"
"""

from __future__ import annotations

import random

_ADJECTIVES = [
    "able", "amber", "ancient", "arctic", "ardent", "arid", "ashen", "astral",
    "austere", "azure", "bare", "bleak", "blind", "bold", "bright", "brittle",
    "broken", "calm", "candid", "cardinal", "careful", "carved", "ceaseless",
    "cerulean", "charged", "cinder", "civil", "clear", "cleft", "close",
    "clouded", "coarse", "cold", "collected", "common", "cool", "copper",
    "coral", "countless", "crisp", "crystalline", "curved", "dark", "dead",
    "deep", "desolate", "diffuse", "dim", "distant", "drifting", "dull",
    "dusky", "earthen", "elemental", "empty", "endless", "errant", "even",
    "exact", "faint", "fallen", "far", "feral", "fierce", "fixed", "flat",
    "fleeting", "fluid", "forgotten", "fragile", "free", "frosted", "full",
    "grave", "grey", "hallowed", "hard", "harsh", "hollow", "honest", "hushed",
    "idle", "immense", "iron", "jade", "keen", "known", "laconic", "languid",
    "latent", "lean", "level", "liminal", "limpid", "linear", "literal",
    "lone", "lost", "low", "lucid", "lunar", "muted", "naked", "narrow",
    "natural", "neutral", "noble", "null", "oblique", "obsidian", "old",
    "open", "pale", "patient", "plain", "primal", "pure", "quiet", "radiant",
    "rare", "raw", "receding", "remote", "resolute", "rough", "runic", "sealed",
    "serene", "sharp", "silent", "silver", "simple", "singular", "slow",
    "smooth", "soft", "solar", "solid", "somber", "sparse", "static", "steady",
    "steep", "stern", "still", "stoic", "strange", "sunken", "taut", "temperate",
    "thin", "tidal", "timeless", "tired", "translucent", "true", "twilight",
    "unlit", "untamed", "vacant", "vast", "veiled", "verdant", "vigilant",
    "void", "wandering", "weathered", "white", "wide", "wild", "windless",
    "worn", "woven", "ancient", "zero",
]

_NOUNS = [
    "alcove", "altar", "anchor", "apex", "arc", "archive", "ash", "atoll",
    "basin", "beacon", "bedrock", "bell", "blank", "bloom", "bone", "border",
    "breach", "bridge", "brine", "canopy", "cavern", "channel", "cipher",
    "circuit", "cliff", "cloud", "column", "compass", "conduit", "core",
    "corridor", "crest", "crossing", "current", "delta", "depth", "descent",
    "drift", "dune", "dusk", "dust", "echo", "edge", "ember", "epoch",
    "estuary", "event", "expanse", "eye", "field", "fissure", "flame",
    "flare", "flint", "fog", "fold", "forge", "form", "fracture", "frontier",
    "gate", "glyph", "grain", "gulf", "harbor", "haze", "hollow", "horizon",
    "hull", "index", "interval", "island", "junction", "key", "ladder",
    "lamp", "layer", "ledge", "lens", "light", "line", "log", "loop",
    "mantle", "margin", "mark", "marsh", "mass", "membrane", "meridian",
    "mirror", "mist", "mode", "node", "notch", "null", "ocean", "orbit",
    "order", "origin", "passage", "path", "peak", "pillar", "plain", "plane",
    "plateau", "point", "pool", "portal", "pulse", "range", "reach", "record",
    "reed", "reef", "relay", "remnant", "ridge", "rift", "rim", "ring",
    "root", "rune", "salt", "shard", "shore", "signal", "silence", "slate",
    "slope", "source", "span", "spool", "spring", "stack", "stone", "strand",
    "stream", "stratum", "surface", "surge", "terminus", "threshold", "tide",
    "timber", "trace", "track", "trail", "trench", "vessel", "void", "vortex",
    "wake", "wall", "wave", "well", "wind", "window", "wire", "witness",
    "zone",
]


def generate_name(sep: str = "-") -> str:
    """Return a random adjective-noun name, e.g. 'silent-ember'."""
    return f"{random.choice(_ADJECTIVES)}{sep}{random.choice(_NOUNS)}"
