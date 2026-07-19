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
    floods your hand with unplayable cards; too little means you can't attack.

    Tests Team Rocket deck at 3 energy levels: 8, 16, 24 energy cards.
    """
    builder = DeckBuilder(cards, build_card_metadata(cards))
    arch = ARCHETYPES['team_rocket']

    results = {}
    for energy_count in [8, 16, 24]:
        deck, report = builder.build(arch, energy_count=energy_count)
        # Mirror match
        r = run_tournament(card_pool_path, deck, deck,
                           agent_a=BaselineAgent(seed=42),
                           agent_b=BaselineAgent(seed=43),
                           num_games=num_games, seed=42)

        avg_turns = sum(g['turns'] for g in r['games']) / max(1, len(r['games']))
        results[f"energy_{energy_count}"] = {
            'energy_count': report['energy_count'],
            'pokemon_count': report['pokemon_count'],
            'trainer_count': report['trainer_count'],
            'p2_win_rate': r['win_rate_b'],
            'avg_turns': avg_turns,
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
    print("EXPERIMENT 4: Energy-to-Draw Ratio")
    print(f"{'='*60}")
    t0 = time.time()
    all_results['energy_ratio'] = experiment_energy_ratio(
        card_pool_path, cards, num_games // 2)
    print(f"  Done in {time.time()-t0:.1f}s")
    for key, r in all_results['energy_ratio'].items():
        print(f"  {key}: {r['energy_count']}e/{r['pokemon_count']}p/{r['trainer_count']}t "
              f"— P2 wins {r['p2_win_rate']:.0f}%, avg {r['avg_turns']:.1f} turns")

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
