from bachbot.analysis.fugue.answer import detect_real_or_tonal_answers
from bachbot.analysis.fugue.keyboard import normalize_keyboard_staves, separate_voices_by_pitch
from bachbot.analysis.fugue.pipeline import (
    FugueAnalysisReport,
    FugueAnswer,
    FugueEpisode,
    FugueSubject,
    StrettoEntry,
    analyze_fugue,
    find_episodes,
    find_stretto_entries,
    find_subject_entries,
    identify_answer,
    identify_subject,
)
from bachbot.analysis.fugue.subject import detect_subject_candidates

__all__ = [
    "FugueAnalysisReport",
    "FugueAnswer",
    "FugueEpisode",
    "FugueSubject",
    "StrettoEntry",
    "analyze_fugue",
    "detect_real_or_tonal_answers",
    "detect_subject_candidates",
    "find_episodes",
    "find_stretto_entries",
    "find_subject_entries",
    "identify_answer",
    "identify_subject",
    "normalize_keyboard_staves",
    "separate_voices_by_pitch",
]
