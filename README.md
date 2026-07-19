# Pokémon TCG AI Battle Challenge — Strategy Category

Kaggle competition submission for the Pokémon TCG AI Battle Challenge.
Building an AI Training Agent and documenting the strategic reasoning behind it.

## Competition Overview

- **Simulation Category**: AI agent win rate and battle performance
- **Strategy Category** (this repo): Analysis, explanation, and documentation of the strategic approach

### Scoring Rubric (Strategy Category)

| Category | Weight |
|---|---|
| Model Score — clarity, originality, consistency, generalization, performance | 70% |
| Deck Score — deck concept articulation, card selection logic | 20% |
| Report Score — structure, clarity, visual elements | 10% |

## Project Phases

| Phase | Status | Description |
|---|---|---|
| [Phase 1](https://github.com/chrisyuspithk-bot/PTCG-AI-Battle-Challenge-Strategy/tree/phase-1-card-analysis) | ✅ Done | Card pool analysis, efficiency metrics, synergy mapping, game rules |
| Phase 2 | 🚧 In Progress | Game simulator engine |
| Phase 3 | ⬜ Todo | Baseline heuristic agent |
| Phase 4 | ⬜ Todo | Deck design & optimization |
| Phase 5 | ⬜ Todo | Hypothesis testing & iteration |
| Phase 6 | ⬜ Todo | Kaggle writeup & figures |

## Card Pool Summary

| Metric | Value |
|---|---|
| Total cards | 2,022 |
| Pokémon | 1,833 (958 Basic, 618 Stage 1, 229 Stage 2) |
| Pokémon ex | 324 (54 Mega) |
| ACE SPEC | 29 |
| Avg HP / Damage / Energy Cost | 131.7 / 67.8 / 2.0 |

### Top Archetypes by Support

| Archetype | Cards | Verdict |
|---|---|---|
| Team Rocket | 97 | Dominant tribal synergy |
| Tera | 96 | Flexible type coverage, 8-bench |
| N | 35 | Solid mid-tier engine |
| Ancient | 26 | Aggro with Awakening Drum draw |
| Future | 17 | Energy via Reboot Pod |

## Usage

```bash
# Run card pool analysis
python card_analyzer.py /path/to/EN_Card_Data.csv

# Run simulator (Phase 2)
python simulator.py deck_a.json deck_b.json --games 100
```

## Timeline

- **Start**: June 16, 2026
- **Entry Deadline**: September 6, 2026
- **Final Submission**: September 13, 2026
- **Judging**: September 14 – October 11, 2026
