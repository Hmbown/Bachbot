"""Feature exports."""

from .contour import contour_signature
from .entropy import pitch_entropy
from .intervals import melodic_intervals
from .key_profiles import estimate_key
from .motif_vectors import motif_vector
from .pitch import ambitus, pitch_class_histogram
from .rhythm import duration_histogram, onset_density
from .texture import average_active_voices

__all__ = [
    "ambitus",
    "average_active_voices",
    "contour_signature",
    "duration_histogram",
    "estimate_key",
    "melodic_intervals",
    "motif_vector",
    "onset_density",
    "pitch_class_histogram",
    "pitch_entropy",
]
