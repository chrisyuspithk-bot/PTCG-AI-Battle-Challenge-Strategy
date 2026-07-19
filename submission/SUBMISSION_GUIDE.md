# Kaggle Simulation Category — Submission Guide

## Quick Submit (2 steps)

```bash
cd submission/
bash build_submission.sh    # creates submission.tar.gz
```

Upload `submission.tar.gz` to:
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/submit

---

## Competition Details

| Detail | Value |
|---|---|
| **Engine** | cabt (Matsuo Institute) |
| **API docs** | https://matsuoinstitute.github.io/cabt/ |
| **Entry deadline** | August 9, 2026 |
| **Final submission** | August 16, 2026 |
| **Matches end** | ~August 31, 2026 |
| **Daily limit** | 5 submissions |
| **Active agents** | Latest 2 per team |
| **Starting Elo** | μ₀ = 600 |
| **File limit** | 197.7 MiB |
| **Agent location** | /kaggle_simulations/agent/ |
| **Submission format** | .tar.gz with main.py + deck.csv at top level |

## What's Submitted

| File | Format |
|---|---|
| `main.py` | `agent(obs_dict) → list[int]` |
| `deck.csv` | 60 card IDs, one per line, no headers |

## Agent Strategy
- **Type**: Threat-aware heuristic, 7 priority levels
- **Deck**: Team Rocket Control (24p/20t/16e)
- **Anchor**: Team Rocket's Mewtwo ex (280 HP / 160 dmg)
- **Simulator WR**: 50% vs Aggro (N=200, position-balanced)

## Validation
After submission, a validation episode runs (agent vs itself). If it passes:
- Agent enters ladder at 600 Elo
- Auto-battles against similarly-rated opponents
- Rating updates after each match (Gaussian N(μ,σ²))

## Troubleshooting

| Issue | Fix |
|---|---|
| "Error" on submission page | Download agent logs, check stderr |
| deck.csv wrong format | Must be 60 lines, one card ID per line, no headers |
| Import errors | Engine is cabt, not cg. No external imports needed. |
