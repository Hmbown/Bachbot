"""Core evaluation logic: pair generation, inter-rater reliability, summary statistics."""

from __future__ import annotations

import math
import random
import uuid
from pathlib import Path

from bachbot.evaluation.models import (
    EvaluationPair,
    EvaluationRating,
    EvaluationSession,
    EvaluationSummary,
)
from bachbot.exports.midi import export_midi_stub


def generate_evaluation_pairs(
    original_bundles: list[Path],
    generated_bundles: list[Path],
    *,
    count: int = 50,
    seed: int = 42,
    output_dir: Path,
) -> list[EvaluationPair]:
    """Create randomized A/B pairs from original and generated chorales.

    For each pair, randomly assign which is A and which is B.
    Export MIDI files for playback.
    """
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    n = min(count, len(original_bundles), len(generated_bundles))
    originals = rng.sample(list(original_bundles), n)
    generated = rng.sample(list(generated_bundles), n)

    pairs: list[EvaluationPair] = []
    for orig, gen in zip(originals, generated):
        pair_id = uuid.UUID(int=rng.getrandbits(128), version=4).hex[:12]
        a_is_original = rng.choice([True, False])

        if a_is_original:
            a_id, b_id = orig.stem, gen.stem
        else:
            a_id, b_id = gen.stem, orig.stem

        midi_a = output_dir / f"{pair_id}_a.mid"
        midi_b = output_dir / f"{pair_id}_b.mid"
        export_midi_stub(midi_a)
        export_midi_stub(midi_b)

        pairs.append(
            EvaluationPair(
                pair_id=pair_id,
                chorale_a_id=a_id,
                chorale_b_id=b_id,
                chorale_a_is_original=a_is_original,
                chorale_a_midi_path=str(midi_a),
                chorale_b_midi_path=str(midi_b),
            )
        )

    return pairs


def compute_krippendorff_alpha(ratings: list[EvaluationRating], dimension: str) -> float:
    """Compute Krippendorff's alpha for inter-rater reliability.

    Uses interval distance metric d(c,k) = (c-k)^2 for ordinal Likert scales.
    ``dimension`` is one of 'musicality', 'authenticity', or 'voice_leading'.
    Ratings for both A and B are included as separate items.
    """
    # Build reliability data matrix: units (pair_id x side) -> {evaluator: value}
    units: dict[str, dict[str, int]] = {}
    for r in ratings:
        key_a = f"{r.pair_id}_a"
        key_b = f"{r.pair_id}_b"
        val_a = getattr(r, f"{dimension}_a")
        val_b = getattr(r, f"{dimension}_b")
        units.setdefault(key_a, {})[r.evaluator_id] = val_a
        units.setdefault(key_b, {})[r.evaluator_id] = val_b

    # Filter units with at least 2 coders
    coded_units = {u: coders for u, coders in units.items() if len(coders) >= 2}
    if not coded_units:
        return 0.0

    # Observed disagreement (D_o)
    n_total = 0
    do_sum = 0.0
    value_counts: dict[int, int] = {}  # overall value frequency

    for _unit, coders in coded_units.items():
        vals = list(coders.values())
        m = len(vals)
        for v in vals:
            value_counts[v] = value_counts.get(v, 0) + 1
            n_total += 1
        # pairwise disagreement within this unit
        for i in range(m):
            for j in range(i + 1, m):
                do_sum += (vals[i] - vals[j]) ** 2
        # normalise by m*(m-1)/2 pairs, weighted by 1/(m-1)
        # Krippendorff: within-unit disagreement = sum d(c,k) / (m-1)
        # but we accumulate raw and normalise at the end

    # Denominator for observed disagreement
    pairable_count = sum(len(c) * (len(c) - 1) for c in coded_units.values())
    if pairable_count == 0:
        return 0.0
    d_o = (2.0 * do_sum) / pairable_count

    # Expected disagreement (D_e) — based on marginal value distribution
    de_sum = 0.0
    all_values = sorted(value_counts.keys())
    for c in all_values:
        for k in all_values:
            if c < k:
                de_sum += value_counts[c] * value_counts[k] * (c - k) ** 2
    d_e = (2.0 * de_sum) / (n_total * (n_total - 1))

    if d_e == 0.0:
        return 1.0  # perfect agreement on a single value

    return 1.0 - (d_o / d_e)


def analyze_evaluation(sessions: list[EvaluationSession]) -> EvaluationSummary:
    """Aggregate ratings across sessions, compute summary statistics."""
    all_ratings: list[EvaluationRating] = []
    all_pairs: list[EvaluationPair] = []
    evaluator_ids: set[str] = set()

    for session in sessions:
        all_ratings.extend(session.ratings)
        all_pairs.extend(session.pairs)
        evaluator_ids.add(session.evaluator_id)

    if not all_ratings:
        return EvaluationSummary(
            total_pairs=len(all_pairs),
            total_evaluators=len(evaluator_ids),
        )

    # Build a lookup: pair_id -> a_is_original
    pair_lookup: dict[str, bool] = {}
    for p in all_pairs:
        pair_lookup[p.pair_id] = p.chorale_a_is_original

    # Accumulate ratings split by original vs generated
    orig_musicality: list[int] = []
    gen_musicality: list[int] = []
    orig_authenticity: list[int] = []
    gen_authenticity: list[int] = []
    orig_voice_leading: list[int] = []
    gen_voice_leading: list[int] = []
    correct_identifications = 0
    total_identifications = 0

    for r in all_ratings:
        a_is_orig = pair_lookup.get(r.pair_id, True)
        if a_is_orig:
            orig_musicality.append(r.musicality_a)
            gen_musicality.append(r.musicality_b)
            orig_authenticity.append(r.authenticity_a)
            gen_authenticity.append(r.authenticity_b)
            orig_voice_leading.append(r.voice_leading_a)
            gen_voice_leading.append(r.voice_leading_b)
        else:
            orig_musicality.append(r.musicality_b)
            gen_musicality.append(r.musicality_a)
            orig_authenticity.append(r.authenticity_b)
            gen_authenticity.append(r.authenticity_a)
            orig_voice_leading.append(r.voice_leading_b)
            gen_voice_leading.append(r.voice_leading_a)

        if r.identified_original != "unsure":
            total_identifications += 1
            expected = "a" if a_is_orig else "b"
            if r.identified_original == expected:
                correct_identifications += 1

    def _mean(values: list[int]) -> float:
        return sum(values) / len(values) if values else 0.0

    ident_accuracy = (
        correct_identifications / total_identifications if total_identifications > 0 else 0.0
    )

    alpha = 0.0
    if len(evaluator_ids) >= 2:
        alphas = [
            compute_krippendorff_alpha(all_ratings, d)
            for d in ("musicality", "authenticity", "voice_leading")
        ]
        alpha = sum(alphas) / len(alphas)

    return EvaluationSummary(
        total_pairs=len({p.pair_id for p in all_pairs}),
        total_evaluators=len(evaluator_ids),
        total_ratings=len(all_ratings),
        avg_musicality_original=round(_mean(orig_musicality), 3),
        avg_musicality_generated=round(_mean(gen_musicality), 3),
        avg_authenticity_original=round(_mean(orig_authenticity), 3),
        avg_authenticity_generated=round(_mean(gen_authenticity), 3),
        avg_voice_leading_original=round(_mean(orig_voice_leading), 3),
        avg_voice_leading_generated=round(_mean(gen_voice_leading), 3),
        identification_accuracy=round(ident_accuracy, 3),
        krippendorff_alpha=round(alpha, 3),
    )


def compute_metric_correlation(
    ratings: list[EvaluationRating],
    algorithmic_scores: dict[str, float],
) -> dict[str, float]:
    """Pearson correlation between human ratings and algorithmic scores.

    Returns a dict mapping dimension name -> Pearson r.
    Only pairs present in ``algorithmic_scores`` are included.
    """
    results: dict[str, float] = {}

    for dimension in ("musicality", "authenticity", "voice_leading"):
        human_vals: list[float] = []
        algo_vals: list[float] = []
        for r in ratings:
            if r.pair_id in algorithmic_scores:
                # Average A and B ratings to get a single human score per pair
                a_val = getattr(r, f"{dimension}_a")
                b_val = getattr(r, f"{dimension}_b")
                human_vals.append((a_val + b_val) / 2.0)
                algo_vals.append(algorithmic_scores[r.pair_id])

        results[dimension] = _pearson(human_vals, algo_vals)

    return results


def _pearson(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if std_x == 0.0 or std_y == 0.0:
        return 0.0
    return cov / (std_x * std_y)
