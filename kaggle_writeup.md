# Threat-Aware Heuristic Agents for Pokémon TCG: Architecture, Experimentation, and Strategic Insight

**Track:** Main Track · **Competition:** Pokémon TCG AI Battle Challenge — Strategy Category

---

## 1. Introduction

The Pokémon Trading Card Game presents a unique challenge for AI agents: imperfect information, probabilistic draws, and the tension between short-term survival and long-term resource development. Unlike chess or Go, where all game state is visible, Pokémon TCG agents must make decisions under uncertainty — you don't know your opponent's hand, your next draw, or which prize cards you'll claim.

Our approach pairs a threat-aware heuristic agent with a custom game simulator capable of running hundreds of matches in seconds. Rather than pursuing black-box deep reinforcement learning, we built an interpretable action-scoring system where every decision can be traced to a specific strategic rationale. This transparency is essential for the Strategy Category: we can explain not just *that* our agent wins, but *why* it makes each choice.

The agent evaluates five dimensions of the game state — KO potential, threat assessment, prize trade efficiency, energy economy, and board development — then selects the highest-priority action. Three distinct deck archetypes were constructed and tested: Team Rocket Control (97-card tribal synergy), Aggro Basics (low-cost single-prize attackers), and Evolution Power (Stage 2 evolution lines). Across 8 controlled experiments totaling over 1,000 simulated matches, we identified several findings that challenge conventional Pokémon TCG wisdom.

---

## 2. Agent Architecture

### 2.1 Decision Framework

The agent operates on a priority-ordered action scoring system with 12 priority levels. At each decision point, it generates all valid actions, scores them, and selects the highest-priority candidate. The priority hierarchy is:

| Priority | Action | Trigger Condition |
|---|---|---|
| 0 | Guaranteed KO | Attack KOs opponent and wins game |
| 1 | Survival Retreat | Active would be KO'd next turn, bench survivor exists |
| 2 | Evolve to Survive | Evolution increases HP above opponent's max damage |
| 3 | Play Basic (Urgent) | Active in danger, no bench backup |
| 4 | Attack (Favorable) | Prize trade is advantageous |
| 5–11 | Development | Evolve, attach energy, play basics, fallback attack |

### 2.2 Threat Assessment Engine

Before scoring actions, the agent performs a full threat calculation:

1. **My KO potential**: Can my active KO the opponent's active this turn? Accounts for energy attachment opportunity and weakness (×2) / resistance (−20).
2. **Opponent KO potential**: Can the opponent KO my active next turn? Uses symmetric calculation.
3. **Prize trade evaluation**: Am I trading a single-prize attacker into a 2-prize ex, or vice versa?
4. **Bench survivability**: Does my bench contain a Pokémon that can survive the opponent's max damage?

This assessment drives the survival-first logic: if the active will be KO'd, the agent prioritizes retreat or evolution over attacking.

### 2.3 Position-Balanced Testing

A critical methodological decision was implementing position-balanced benchmarking. In Pokémon TCG, the player going second (P2) can attack on their first turn, while the player going first (P1) cannot. This creates a structural asymmetry. Without position balancing, win rates are inflated by 20–30 percentage points simply based on turn order. All our experiments counter-balance P1/P2 assignments, ensuring fair comparisons between agents and decks.

---

## 3. Deck Design

We built three archetypes from the 1,267-card pool using an automated deck builder that constructs 60-card decks from archetype templates, card efficiency metrics, and synergy filters.

### 3.1 Team Rocket Control (Strategy: Big Basics)

The card pool's largest synergy group (97 Team Rocket cards) provides a dense tribal engine. The deck runs 24 Pokémon (12 ex), 20 trainers, and 16 energy. Key attackers:

- **Team Rocket's Mewtwo ex** (280 HP, 160 damage, 3 energy) — anchor attacker
- **Team Rocket's Kangaskhan ex** (230 HP, 120 damage, 3 energy) — secondary threat
- Dedicated Rocket supporters (Ariana, Giovanni, Petrel) for draw power

### 3.2 Aggro Basics (Strategy: Fast Pressure)

Twenty single-prize attackers designed to trade favorably by applying early pressure. Key cards:

- **Sawk** (110 HP, 90 damage, 1 energy) — efficient attacker
- **Fan Rotom** (70 HP, 70 damage, 1 energy) — low-cost pressure
- **Iron Boulder** (140 HP, 170 damage, 2 energy) — heavy hitter

### 3.3 Evolution Power (Strategy: Scaling Threats)

Charmander→Charmeleon, Ponyta→Rapidash, and Growlithe lines supported by Rare Candy and Salvatore for accelerated evolution. This archetype proved non-viable in testing (see §4.3).

---

## 4. Experimental Results

### 4.1 Turn-Order Advantage is Archetype-Dependent

![Figure 1](figures/fig1_turn_order.png)

We measured P2 win rates across 100-game mirror matches for each archetype. Fast decks show a strong P2 advantage (70%), consistent with the first-attack privilege. However, Evolution Power reverses this pattern: P2 wins only 37% of mirror matches. Going first gives evolution decks an extra turn to set up before being attacked — a critical finding for deck selection strategy.

### 4.2 Ex Pokémon Dominate Single-Prize Attackers (Reversed Hypothesis)

![Figure 2](figures/fig2_prize_trade.png)

We hypothesized that single-prize attackers would trade favorably against 2-prize ex Pokémon by winning the prize economy. Each KO costs the single-prize player 1 prize while threatening 2 prizes in return. The data proved the opposite: ex Pokémon won 83% of games. The 280 HP / 160 damage stat line of Mewtwo ex creates a gap too large for prize-trade theory to overcome. In this card pool, raw stats dominate economic theory.

### 4.3 Evolution Strategies Are Non-Viable

![Figure 3](figures/fig3_matchup_matrix.png)

Across all cross-archetype matchups, Evolution Power recorded a 0% win rate against Team Rocket Control and 6% against Aggro Basics (100-game samples). The deck cannot establish evolved attackers before Big Basics apply lethal pressure. This finding eliminated Evolution as a competitive option early in our process, saving significant experimentation time.

### 4.4 Incremental Deck Improvement is Non-Linear

![Figure 4](figures/fig4_deck_iteration.png)

We measured win rate as cards were incrementally added to a baseline Mewtwo ex deck. The baseline (4 Mewtwo ex + energy) achieved 63% win rate. Adding Kangaskhan ex improved it to 67%. However, adding 8 bench-filler basics and 8 trainers *reduced* the win rate to 57%. Card quality matters more than card quantity: diluting the deck with weaker Pokémon makes it less likely to draw the anchor attacker when needed.

### 4.5 Attacker Quality Dominates

![Figure 5](figures/fig5_attacker.png)

Single-attacker decks (4 copies of one Pokémon + energy) were tested against a common Aggro opponent. Mewtwo ex alone achieved 63% win rate, while Articuno (120 HP, 60 damage) managed only 13%. HP and damage are the dominant predictors of success — more important than deck synergy or trainer support in this format.

### 4.6 Energy Oversaturation Reduces Performance

![Figure 6](figures/fig6_energy_ratio.png)

We tested Team Rocket variants with 16 and 24 energy cards against a fixed Aggro opponent. The 24-energy variant lost 13 percentage points of win rate (53% → 40%). Too much energy floods your hand with unplayable cards, reducing the probability of drawing attackers and support.

---

## 5. Key Insights for AI Training Agents

### 5.1 The Simulator as a Strategic Accelerator

Our lightweight simulator (933 lines, ~1,500 games/second) made rapid iteration possible. We could test a hypothesis, analyze results, and refine within minutes. The tight feedback loop was more valuable than any single algorithmic innovation.

### 5.2 Failed Hypotheses Are Valuable

Two of our initial hypotheses were disproven by data: (1) single-prize attackers would out-trade ex Pokémon, and (2) incremental card addition would produce linear win-rate gains. Both failures saved us from pursuing dead-end strategies. The Strategy Category rewards this kind of honest, data-driven iteration.

### 5.3 Position Bias is a First-Order Effect

Every experiment must control for P1/P2 position. Without position balancing, an agent that wins 55% of games as P2 against an identical agent would appear to have a 55% win rate — when it's actually at parity. This is not a detail; it's a prerequisite for valid results.

---

## 6. Performance Summary

Our final Team Rocket Control deck, piloted by the threat-aware baseline agent, achieves approximately 52% win rate against Aggro Basics and 100% against Evolution Power in 100-game position-balanced trials. The agent makes statistically sound decisions within 1ms per action, processing threat assessment, KO calculus, and action scoring entirely in-memory.

The full codebase is available at the linked GitHub repository, including the simulator, deck optimizer, experiment runner, and figure generation scripts. All experiments are reproducible with a single command: `python3 experiments.py`.

---

## 7. Conclusion

We approached the Pokémon TCG AI Battle Challenge not as a pure optimization problem, but as a strategic inquiry. By building an interpretable heuristic agent, designing distinct deck archetypes from card pool data, and running controlled experiments, we identified which strategies work (Big Basics), which don't (Evolution), and why (raw stats dominate prize economics).

The most valuable lesson is methodological: position-balanced testing, rapid simulator iteration, and the willingness to abandon disproven hypotheses were more important than any specific algorithm. These principles generalize beyond Pokémon TCG to any domain where agents must reason under uncertainty.

---

*This report was prepared for the Pokémon TCG AI Battle Challenge — Strategy Category. All experiments use position-balanced trials with the open-source simulator and agent framework developed for this competition.*
