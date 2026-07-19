# Kaggle Ladder Submission Guide

## Step 1: Get the SDK (Required for submission)

1. Sign in to Kaggle and go to:
   https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/data

2. Accept the competition rules

3. Download the "Sample Submission" or SDK package
   - It contains the `cg/` engine bindings (compiled C++ binary)
   - The engine is x86-64 Linux only

4. Place the `cg/` directory inside `submission/`:
   ```
   submission/
   ├── main.py          ← our agent
   ├── deck.csv         ← Team Rocket Control deck
   ├── cg/              ← official engine bindings (from Kaggle)
   └── build_submission.sh
   ```

## Step 2: Build the Submission

```bash
cd submission/
bash build_submission.sh
```

This creates `submission.tar.gz`

## Step 3: Submit to Kaggle

1. Go to: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/submit
2. Upload `submission.tar.gz`
3. Wait for validation (~2-5 minutes)
4. The agent enters the ladder and starts auto-battling

## Step 4: Get Results

1. Go to: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/leaderboard
2. Find your team's Elo rating
3. Check individual match history at:
   https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/submissions

## What's in the submission

| File | Purpose |
|---|---|
| `main.py` | Entry point — `agent(obs_dict) → list[int]` |
| `deck.csv` | 60 card IDs: Team Rocket Control (24p/20t/16e) |
| `cg/` | Official engine bindings (provided by competition) |

## Agent Strategy
- **Type**: Threat-aware heuristic (12 priority levels)
- **Deck**: Team Rocket Control — Mewtwo ex anchor (280 HP/160 dmg)
- **Expected Elo**: ~1200-1220 (simulator estimate)

## Troubleshooting

### "cg/ directory not found"
→ Download the SDK from Kaggle Data tab first

### "deck.csv not found"
→ Make sure deck.csv is in the submission/ directory

### Agent crashes on Kaggle
→ Check the submission logs on Kaggle. Our agent has multi-layer
  fallback — it returns safe defaults on any error.

### Import errors on Kaggle
→ The cg/ bindings must be exactly as provided by Kaggle.
  Do not rename or modify any files in cg/.
