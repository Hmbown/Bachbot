from __future__ import annotations

from bachbot.analysis.fugue.subject import detect_subject_candidates
from bachbot.encodings.event_graph import EventGraph


def detect_real_or_tonal_answers(graph: EventGraph) -> list[dict[str, object]]:
    answers: list[dict[str, object]] = []
    for candidate in detect_subject_candidates(graph):
        occurrences = candidate["occurrences"]
        if len(occurrences) < 2:
            continue
        subject = occurrences[0]
        for answer in occurrences[1:]:
            if answer["voice_id"] == subject["voice_id"]:
                continue
            subject_pitches = subject.get("pitches", [])
            answer_pitches = answer.get("pitches", [])
            if len(subject_pitches) != len(answer_pitches) or not subject_pitches:
                continue
            transpositions = [answer_pitch - subject_pitch for subject_pitch, answer_pitch in zip(subject_pitches, answer_pitches)]
            entry_interval = transpositions[0]
            answer_type = "real_answer" if len(set(transpositions)) == 1 and abs(entry_interval) in {5, 7} else "tonal_answer"
            answers.append(
                {
                    "pattern": candidate["pattern"],
                    "subject_voice": subject["voice_id"],
                    "answer_voice": answer["voice_id"],
                    "subject_onset": subject["start_onset"],
                    "answer_onset": answer["start_onset"],
                    "entry_interval": entry_interval,
                    "transposition_profile": transpositions,
                    "answer_type": answer_type,
                }
            )
    return answers
