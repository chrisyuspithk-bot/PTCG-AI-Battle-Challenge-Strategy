"""
Phase 5: Hypothesis Testing & Agent Iteration
Pokémon TCG AI Battle Challenge

Controlled experiments to generate data for the Strategy Category writeup.
Each experiment tests a specific hypothesis with position-balanced trials.
"""

import time
import json
from collections import defaultdict

from simulator import (
    load_cards_sim, create_test_deck, run_tournament,
    DECK_SIZE, MAX_COPIES,
)
from baseline_agent import BaselineAgent
from deck_optimizer import (
    DeckBuilder, ARCHETYPES, build_card_metadata, test_matchup,
    _is_pokemon, _is_basic, _is_trainer, _is_energy,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 1: Turn Order Advantage
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_turn_order(card_pool_path: str, decks: dict[str, list],
                          num_games: int = 100) -> dict:
    """
    Hypothesis: P2 (going second) has a structural advantage, but the
    magnitude varies by deck archetype speed.

    Measures P2 win rate for each deck in mirror matches.
    """
    results = {}
    for name, deck in decks.items():
        half = num_games // 2
        agent = BaselineAgent(seed=42)

        r = run_tournament(card_pool_path, deck, deck,
                           agent_a=agent, agent_b=BaselineAgent(seed=43),
                           num_games=num_games, seed=42)

        results[name] = {
            'p1_wins': r['P1'],
            'p2_wins': r['P2'],
            'p2_win_rate': r['win_rate_b'],
            'draws': r['Draw'],
            'total': num_games,
            'deck_pokemon': sum(1 for c in deck if _is_pokemon(c)),
            'deck_ex': sum(1 for c in deck if c.is_ex),
            'avg_hp': sum(c.hp for c in deck if _is_pokemon(c)) /
                      max(1, sum(1 for c in deck if _is_pokemon(c))),
        }

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 2: Prize Trade Efficiency
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_prize_trade(card_pool_path: str, cards: dict,
                           num_games: int = 50) -> dict:
    """
    Hypothesis: Single-prize attackers trade favorably against multi-prize
    ex Pokémon because each KO costs the opponent only 1 prize while
    threatening 2 prizes in return.

    Builds two variants of the Aggro deck:
    - Variant A: Only single-prize attackers
    - Variant B: Mixed with ex attackers (same deck otherwise)
    """
    builder = DeckBuilder(cards, build_card_metadata(cards))

    # Single-prize only aggro
    single_prize_names = ['Sawk', 'Fan Rotom', 'Solrock', 'Iron Boulder']
    sp_deck = []
    for name in single_prize_names:
        ids = builder.name_to_ids.get(name, [])
        if ids:
            for _ in range(min(4, (DECK_SIZE - len(sp_deck) - 12) // len(single_prize_names))):
                sp_deck.append(cards[ids[0]])

    # Multi-prize aggro (add ex attackers)
    mp_names = single_prize_names + ['Rotom ex', "Team Rocket's Mewtwo ex"]
    mp_deck = []
    for name in mp_names:
        ids = builder.name_to_ids.get(name, [])
        if ids:
            for _ in range(min(4, (DECK_SIZE - len(mp_deck) - 12) // len(mp_names))):
                mp_deck.append(cards[ids[0]])

    # Fill both with same trainers and energy
    trainer_names = ["Ultra Ball", "Boss's Orders", "Cheren"]
    for deck in (sp_deck, mp_deck):
        for tname in trainer_names:
            ids = builder.name_to_ids.get(tname, [])
            if ids:
                for _ in range(min(4, 20)):
                    deck.append(cards[ids[0]])
        # Fill with energy
        eids = builder.name_to_ids.get('Basic {F} Energy', [])
        if not eids:
            for cid, c in cards.items():
                if _is_energy(c) and c.stage != 'Special Energy':
                    eids.append(cid)
                    break
        while len(deck) < DECK_SIZE and eids:
            deck.append(cards[eids[0]])
        deck[:] = deck[:DECK_SIZE]

    # Test: single-prize deck vs multi-prize deck
    result = test_matchup(card_pool_path, sp_deck, mp_deck,
                          "Single-Prize", "Multi-Prize", num_games=num_games)

    result['single_prize_ex_count'] = sum(1 for c in sp_deck if c.is_ex)
    result['multi_prize_ex_count'] = sum(1 for c in mp_deck if c.is_ex)
    result['single_prize_avg_hp'] = sum(c.hp for c in sp_deck if _is_pokemon(c)) / \
                                     max(1, sum(1 for c in sp_deck if _is_pokemon(c)))
    result['multi_prize_avg_hp'] = sum(c.hp for c in mp_deck if _is_pokemon(c)) / \
                                    max(1, sum(1 for c in mp_deck if _is_pokemon(c)))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 3: Card Impact Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_card_impact(card_pool_path: str, deck: list,
                           test_cards: list[str], num_games: int = 50) -> list:
    """
    Hypothesis: Some cards have disproportionate impact on win rate.
    Measures win-rate delta when removing each specified card.

    For each card: play deck_with vs deck_without, measure difference.
    """
    results = []
    energy_cards = [c for c in deck if _is_energy(c)]

    for card_name in test_cards:
        # Build deck without target card
        removed = 0
        deck_without = []
        for c in deck:
            if c.name == card_name and removed < 4:  # Remove up to 4 copies
                removed += 1
            else:
                deck_without.append(c)

        # Pad with energy
        while len(deck_without) < DECK_SIZE and energy_cards:
            deck_without.append(energy_cards[0])

        # Run position-balanced test
        r = test_matchup(card_pool_path, deck, deck_without,
                         "With", "Without", num_games=num_games)

        results.append({
            'card': card_name,
            'copies_removed': removed,
            'deck_with_win_rate': r['win_rate_a'],
            'deck_without_win_rate': r['win_rate_b'],
            'win_rate_delta': r['win_rate_a'] - r['win_rate_b'],
            'games': num_games,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 4: Energy-to-Draw Ratio
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_energy_ratio(card_pool_path: str, cards: dict,
                            num_games: int = 50) -> dict:
    """
    Hypothesis: There's an optimal energy-to-draw ratio. Too much energy
    floods your hand; too little means you can't attack.

    Builds 3 variants of TR deck (8/16/24 energy) and tests each against
    a fixed Aggro opponent for comparable results.
    """
    arch = ARCHETYPES['team_rocket']
    agg_arch = ARCHETYPES['aggro_basic']
    builder = DeckBuilder(cards, build_card_metadata(cards))

    # Reference opponent (fixed)
    opp_deck, _ = builder.build(agg_arch)

    results = {}
    for energy_count in [8, 16, 24]:
        deck, report = builder.build(arch, energy_count=energy_count)
        # Test against fixed Aggro opponent
        r = test_matchup(card_pool_path, deck, opp_deck,
                         f"TR({energy_count}e)", "Aggro",
                         num_games=num_games)

        results[f"energy_{energy_count}"] = {
            'energy_count': report['energy_count'],
            'pokemon_count': report['pokemon_count'],
            'trainer_count': report['trainer_count'],
            'win_rate': r['win_rate_a'],
            'avg_turns': r['avg_turns'],
            'total_games': num_games,
        }

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 5: Archetype Cross-Matchup Matrix
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_archetype_matrix(card_pool_path: str, cards: dict,
                                 num_games: int = 100) -> dict:
    """
    Full cross-matchup matrix with larger sample size for statistical
    significance. Tests all pairwise matchups between archetypes.
    """
    builder = DeckBuilder(cards, build_card_metadata(cards))
    decks = {}
    for key, arch in ARCHETYPES.items():
        deck, report = builder.build(arch)
        errors = __import__('simulator').validate_deck(deck)
        if not errors:
            decks[key] = deck

    results = {}
    deck_names = list(decks.keys())

    for i, name_a in enumerate(deck_names):
        for name_b in deck_names[i:]:
            if name_a == name_b:
                continue
            key = f"{name_a}_vs_{name_b}"
            r = test_matchup(card_pool_path, decks[name_a], decks[name_b],
                             name_a, name_b, num_games=num_games)
            results[key] = {
                'name_a': name_a,
                'name_b': name_b,
                'wins_a': r['wins_a'],
                'wins_b': r['wins_b'],
                'win_rate_a': r['win_rate_a'],
                'win_rate_b': r['win_rate_b'],
                'draws': r['draws'],
                'avg_turns': r['avg_turns'],
            }

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 6: Deck Iteration Cycle
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_deck_iteration(card_pool_path: str, cards: dict,
                               num_games: int = 50) -> dict:
    """
    Hypothesis: Incremental deck improvements produce measurable win-rate gains.
    Starts with a minimal Team Rocket deck, then adds cards one layer at a time,
    measuring win rate against a fixed Aggro opponent at each step.
    """
    builder = DeckBuilder(cards, build_card_metadata(cards))
    agg_deck, _ = builder.build(ARCHETYPES['aggro_basic'])

    results = []
    deck = []
    energy_ids = builder.name_to_ids.get('Basic {D} Energy', [])

    def _current_deck():
        d = list(deck)
        while len(d) < DECK_SIZE and energy_ids:
            d.append(cards[energy_ids[0]])
        return d[:DECK_SIZE]

    def _has_basic(d):
        return any('Basic' in c.stage and 'Pokémon' in c.stage for c in d)

    # Step 0: Add Mewtwo ex (4 copies) — baseline with one attacker
    for name in ["Team Rocket's Mewtwo ex"]:
        ids = builder.name_to_ids.get(name, [])
        if ids:
            for _ in range(4):
                deck.append(cards[ids[0]])
    r = test_matchup(card_pool_path, _current_deck(), agg_deck,
                     "Step 0: Base (Mewtwo)", "Aggro", num_games=num_games)
    results.append({'step': 0, 'change': 'Mewtwo ex (4x) baseline',
                    'win_rate': r['win_rate_a'], 'avg_turns': r['avg_turns']})

    # Step 1: Add Kangaskhan ex (4 copies)
    for name in ["Team Rocket's Kangaskhan ex"]:
        ids = builder.name_to_ids.get(name, [])
        if ids:
            for _ in range(4):
                deck.append(cards[ids[0]])
    r = test_matchup(card_pool_path, _current_deck(), agg_deck,
                     "Step 1: +Kangaskhan ex", "Aggro", num_games=num_games)
    results.append({'step': 1, 'change': '+ Kangaskhan ex (4x)',
                    'win_rate': r['win_rate_a'], 'avg_turns': r['avg_turns']})

    # Step 2: Add more Rocket basics (fill bench)
    for name in ["Team Rocket's Houndour", "Team Rocket's Larvitar",
                 "Team Rocket's Nidoran♀", "Team Rocket's Ekans"]:
        ids = builder.name_to_ids.get(name, [])
        if ids:
            for _ in range(2):
                deck.append(cards[ids[0]])
    r = test_matchup(card_pool_path, _current_deck(), agg_deck,
                     "Step 2: +Bench fillers", "Aggro", num_games=num_games)
    results.append({'step': 2, 'change': '+ 8 bench basics',
                    'win_rate': r['win_rate_a'], 'avg_turns': r['avg_turns']})

    # Step 3: Add trainers (Ultra Ball + Boss)
    for name in ["Ultra Ball", "Boss's Orders"]:
        ids = builder.name_to_ids.get(name, [])
        if ids:
            for _ in range(4):
                deck.append(cards[ids[0]])
    r = test_matchup(card_pool_path, _current_deck(), agg_deck,
                     "Step 3: +Trainers", "Aggro", num_games=num_games)
    results.append({'step': 3, 'change': '+ Ultra Ball (4x) + Boss (4x)',
                    'win_rate': r['win_rate_a'], 'avg_turns': r['avg_turns']})

    return {'iterations': results, 'opponent': 'Aggro Basics'}


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 7: Attacker Efficiency Breakdown
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_attacker_breakdown(card_pool_path: str, cards: dict,
                                   num_games: int = 50) -> dict:
    """
    Hypothesis: Individual attacker quality (HP, damage, energy cost)
    determines win rate more than deck synergy.

    Builds single-attacker decks (4 copies of one Pokémon + energy) and
    measures each against the same Aggro opponent.
    """
    builder = DeckBuilder(cards, build_card_metadata(cards))
    agg_deck, _ = builder.build(ARCHETYPES['aggro_basic'])

    # Test attackers individually — only the top 2 (others have 0 dmg)
    attackers = [
        "Team Rocket's Mewtwo ex",    # 280 HP, 160 dmg, 3e — anchor
        "Team Rocket's Kangaskhan ex", # 230 HP, 120 dmg, 3e — secondary
        "Team Rocket's Articuno",      # 120 HP, 60 dmg, 3e — budget
    ]

    results = []
    energy_ids = builder.name_to_ids.get('Basic {D} Energy', [])

    for atk_name in attackers:
        ids = builder.name_to_ids.get(atk_name, [])
        if not ids:
            continue
        card = cards[ids[0]]

        # Build deck: 4 copies + energy
        deck = [cards[ids[0]] for _ in range(4)]
        while len(deck) < DECK_SIZE and energy_ids:
            deck.append(cards[energy_ids[0]])

        r = test_matchup(card_pool_path, deck, agg_deck,
                         atk_name, "Aggro", num_games=num_games)

        results.append({
            'attacker': atk_name,
            'hp': card.hp,
            'damage': card.move_damage,
            'energy_cost': card.move_move_cost if hasattr(card, 'move_move_cost') else 'n/a',
            'prizes_given': card.prizes_given,
            'is_ex': card.is_ex,
            'win_rate': r['win_rate_a'],
            'avg_turns': r['avg_turns'],
        })

    # Sort by win rate
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    return {'attackers': results, 'opponent': 'Aggro Basics'}


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 8: Win Rate Stability
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_stability(card_pool_path: str, deck: list,
                          num_trials: int = 10, num_games: int = 100) -> dict:
    """
    Hypothesis: Win rates stabilize within 100 games. Measures variance
    across repeated tournament runs to establish confidence intervals.

    Runs `num_trials` independent tournaments of `num_games` each,
    tracking P1 win rate distribution.
    """
    rates = []
    for trial in range(num_trials):
        r = run_tournament(card_pool_path, deck, deck,
                           agent_a=BaselineAgent(seed=42 + trial),
                           agent_b=BaselineAgent(seed=142 + trial),
                           num_games=num_games, seed=42 + trial * 100)
        rates.append(r['win_rate_a'])

    import statistics
    return {
        'num_trials': num_trials,
        'games_per_trial': num_games,
        'mean_win_rate': statistics.mean(rates),
        'std_dev': statistics.stdev(rates) if len(rates) > 1 else 0,
        'min_rate': min(rates),
        'max_rate': max(rates),
        'range': max(rates) - min(rates),
        'all_rates': [round(r, 1) for r in rates],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_all_experiments(card_pool_path: str, output_path: str = None,
                         num_games: int = 50) -> dict:
    """Run all Phase 5 experiments and return results."""
    print("Loading card pool...")
    cards = load_cards_sim(card_pool_path)
    builder = DeckBuilder(cards, build_card_metadata(cards))
    print(f"Loaded {len(cards)} cards")

    # Build reference decks
    decks = {}
    for key, arch in ARCHETYPES.items():
        deck, report = builder.build(arch)
        errors = __import__('simulator').validate_deck(deck)
        if not errors:
            decks[key] = deck
            print(f"  {arch.name}: {report['pokemon_count']}p/{report['trainer_count']}t/"
                  f"{report['energy_count']}e")

    all_results = {}

    # ── Experiment 1: Turn Order ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 1: Turn Order Advantage")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['turn_order'] = experiment_turn_order(card_pool_path, decks, num_games)
    print(f"  Done in {time.time()-t0:.1f}s")
    for name, r in all_results['turn_order'].items():
        print(f"  {name}: P2 wins {r['p2_win_rate']:.0f}% ({r['total']} games)")

    # ── Experiment 2: Prize Trade ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 2: Prize Trade Efficiency")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['prize_trade'] = experiment_prize_trade(card_pool_path, cards, num_games)
    print(f"  Done in {time.time()-t0:.1f}s")
    pt = all_results['prize_trade']
    print(f"  Single-Prize ({pt['single_prize_ex_count']} ex): {pt['win_rate_a']:.0f}%")
    print(f"  Multi-Prize ({pt['multi_prize_ex_count']} ex): {pt['win_rate_b']:.0f}%")

    # ── Experiment 3: Card Impact ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 3: Card Impact Analysis")
    print(f"{'='*60}")
    t0 = time.time()
    team_rocket_deck = decks.get('team_rocket', list(decks.values())[0])
    test_cards = ["Team Rocket's Mewtwo ex", "Ultra Ball", "Boss's Orders"]
    all_results['card_impact'] = experiment_card_impact(
        card_pool_path, team_rocket_deck, test_cards, num_games // 2)
    print(f"  Done in {time.time()-t0:.1f}s")
    for ci in all_results['card_impact']:
        direction = "lost" if ci['win_rate_delta'] > 0 else "gained"
        print(f"  Remove {ci['card']}: {direction} {abs(ci['win_rate_delta']):.0f}% win rate")

    # ── Experiment 4: Energy Ratio ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 4: Energy-to-Draw Ratio (vs Aggro)")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['energy_ratio'] = experiment_energy_ratio(
        card_pool_path, cards, num_games // 2)
    print(f"  Done in {time.time()-t0:.1f}s")
    for key, r in all_results['energy_ratio'].items():
        print(f"  {key}: {r['energy_count']}e/{r['pokemon_count']}p/{r['trainer_count']}t "
              f"— win rate {r['win_rate']:.0f}%, avg {r['avg_turns']:.1f} turns")

    # ── Experiment 5: Archetype Matrix ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 5: Archetype Cross-Matchup Matrix")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['archetype_matrix'] = experiment_archetype_matrix(
        card_pool_path, cards, num_games)
    print(f"  Done in {time.time()-t0:.1f}s")
    for key, r in all_results['archetype_matrix'].items():
        print(f"  {r['name_a']} vs {r['name_b']}: "
              f"{r['win_rate_a']:.0f}% / {r['win_rate_b']:.0f}%")

    # ── Experiment 6: Deck Iteration ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 6: Deck Iteration Cycle")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['deck_iteration'] = experiment_deck_iteration(
        card_pool_path, cards, num_games)
    print(f"  Done in {time.time()-t0:.1f}s")
    for step in all_results['deck_iteration']['iterations']:
        bar = '█' * int(step['win_rate'] / 5)
        print(f"  Step {step['step']}: {step['change']:30s} → {step['win_rate']:5.0f}% {bar}")

    # ── Experiment 7: Attacker Breakdown ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 7: Attacker Efficiency Breakdown")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['attacker_breakdown'] = experiment_attacker_breakdown(
        card_pool_path, cards, num_games)
    print(f"  Done in {time.time()-t0:.1f}s")
    for a in all_results['attacker_breakdown']['attackers']:
        print(f"  {a['attacker']:35s} HP:{a['hp']:3d} Dmg:{a['damage']:3d} "
              f"→ {a['win_rate']:.0f}%")

    # ── Experiment 8: Stability ──
    print(f"\n{'='*60}")
    print("EXPERIMENT 8: Win Rate Stability (TR mirror)")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['stability'] = experiment_stability(
        card_pool_path, team_rocket_deck, num_trials=5, num_games=100)
    print(f"  Done in {time.time()-t0:.1f}s")
    s = all_results['stability']
    print(f"  Mean P1 rate: {s['mean_win_rate']:.1f}% ± {s['std_dev']:.1f}% (σ)")
    print(f"  Range: {s['min_rate']:.1f}% – {s['max_rate']:.1f}%")
    print(f"  Rates: {s['all_rates']}")

    # ── Export ──
    if output_path:
        # Convert to serializable format
        serializable = {}
        for exp_name, exp_data in all_results.items():
            if isinstance(exp_data, dict):
                serializable[exp_name] = {
                    k: v for k, v in exp_data.items()
                    if not callable(v)
                }
            elif isinstance(exp_data, list):
                serializable[exp_name] = exp_data
        with open(output_path, 'w') as f:
            json.dump(serializable, f, indent=2, default=str)
        print(f"\nResults exported to {output_path}")

    return all_results


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else '/workspace/EN_Card_Data.csv'
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    output = sys.argv[3] if len(sys.argv) > 3 else '/workspace/project/experiment_results.json'

    run_all_experiments(csv_path, output, num_games=num_games)
