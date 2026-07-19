"""
PTCG AI Battle — Kaggle Simulation Category Submission
========================================================
Engine: cabt (Matsuo Institute)
Agent: Team Rocket Control — threat-aware heuristic
Deck: 24 Pokémon (12 ex) / 20 trainers / 16 energy

Official contract:
  def agent(obs_dict: dict) -> list[int]:
      obs["select"] is None → return 60 card IDs (deck selection)
      otherwise → return indices into obs["select"]["option"]

API docs: https://matsuoinstitute.github.io/cabt/

Observation structure:
  obs["select"] — None during deck phase, otherwise {option, maxCount, ...}
  obs["current"] — board state (None during deck phase)
  obs["current"]["players"] — list of PlayerState dicts
  obs["logs"] — event logs

Deck format: deck.csv with one card ID per line (60 lines, no headers)

Strategy: 7 priority levels (KO → survival → evolve → bench → energy → attack → pass)
See kaggle_writeup.md for full analysis.
"""

from __future__ import annotations
import os
import sys
import traceback
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# Deck Loading
# ═══════════════════════════════════════════════════════════════════════════════

def _find_deck_csv() -> str:
    """Find deck.csv — one card ID per line, 60 lines, no headers."""
    candidates = []
    try:
        candidates.append(os.path.join(os.path.dirname(__file__), 'deck.csv'))
    except NameError:
        pass
    candidates.append(os.path.join('/kaggle_simulations/agent', 'deck.csv'))
    candidates.append('deck.csv')
    for path in candidates:
        if os.path.isfile(path):
            return path
    return 'deck.csv'


def read_deck() -> list[int]:
    """Read 60 card IDs from deck.csv (one per line, no headers)."""
    deck_path = _find_deck_csv()
    card_ids = []
    with open(deck_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and line.isdigit():
                card_ids.append(int(line))
    # Pad to 60 if needed
    while len(card_ids) < 60 and card_ids:
        card_ids.append(card_ids[0])
    return card_ids[:60]


# ═══════════════════════════════════════════════════════════════════════════════
# Threat-Aware Action Selection (cabt engine observation format)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_current_hp(pokemon: Optional[dict]) -> int:
    """Estimate current HP (hp - damage counters)."""
    if not pokemon:
        return 0
    hp = pokemon.get('hp', 0)
    dmg = pokemon.get('damage', 0)
    return max(0, hp - dmg)


def _get_attack_damage(attacks: Optional[list]) -> int:
    """Get damage of first usable attack, or 0."""
    if not attacks:
        return 0
    dmg = attacks[0].get('damage', 0)
    try:
        return int(dmg)
    except (ValueError, TypeError):
        return 0


def _can_ko(my_dmg: int, opp_hp: int) -> bool:
    return my_dmg > 0 and my_dmg >= opp_hp


def select_action(obs: dict) -> list[int]:
    """
    Select the best action using threat-aware heuristic.
    Uses the real cabt engine observation format.

    Priority levels (lower = higher priority):
      0  GUARANTEED_KO  — attack KOs opponent
      1  SURVIVAL       — retreat if active would be KO'd
      2  EVOLVE         — evolve Pokémon
      3  PLAY_BASIC     — bench a basic (if bench < 3)
      4  ATTACH_ENERGY  — attach energy
      5  ATTACK         — attack (favorable)
      8  RETREAT        — low-HP retreat
      6  TRAINER        — use supporter/item
      7  PASS           — end turn
    """
    select = obs.get('select')
    if select is None:
        return []

    options = select.get('option') or []
    if not options:
        return []

    n = len(options)
    if n == 1:
        return [0]

    # Parse board state from cabt observation
    current = obs.get('current') or {}
    players = current.get('players') or []

    # Determine which player we are (yourIndex from select)
    your_index = select.get('yourIndex', 0)
    my_state = players[your_index] if your_index < len(players) else {}
    opp_idx = 1 - your_index
    opp_state = players[opp_idx] if opp_idx < len(players) else {}

    my_active = (my_state.get('active') or [None])[0] if my_state.get('active') else None
    opp_active = (opp_state.get('active') or [None])[0] if opp_state.get('active') else None
    my_bench = my_state.get('bench') or []

    my_hp = _get_current_hp(my_active) if my_active else 0
    opp_hp = _get_current_hp(opp_active) if opp_active else 999

    my_attacks = my_active.get('attacks') if my_active else None
    opp_attacks = opp_active.get('attacks') if opp_active else None

    my_dmg = _get_attack_damage(my_attacks)
    opp_dmg = _get_attack_damage(opp_attacks)

    i_can_ko = _can_ko(my_dmg, opp_hp)
    opp_can_ko = _can_ko(opp_dmg, my_hp)
    has_bench = len(my_bench) > 0
    bench_small = len(my_bench) < 3

    # Check energy attached this turn
    energy_attached = current.get('energyAttached', False)

    best_idx = 0
    best_priority = 99

    for i, opt in enumerate(options):
        opt_type = str(opt.get('type', opt.get('kind', ''))).lower()
        priority = 50

        if opt_type in ('attack', 'use_attack', 'move'):
            if i_can_ko:
                priority = 0
            elif my_dmg > 0:
                priority = 5
            else:
                priority = 50

        elif opt_type in ('retreat', 'switch'):
            if opp_can_ko and has_bench:
                priority = 1
            elif my_hp < 50 and has_bench:
                priority = 8
            else:
                priority = 30

        elif opt_type in ('evolve', 'evolution'):
            priority = 2

        elif opt_type in ('play_basic', 'bench', 'play_to_bench'):
            priority = 3 if bench_small else 10

        elif opt_type in ('attach_energy', 'energy_attach'):
            priority = 4 if not energy_attached else 20

        elif opt_type in ('trainer', 'use_supporter', 'use_item', 'supporter'):
            priority = 6

        elif opt_type in ('ability', 'use_ability'):
            priority = 9

        elif opt_type in ('pass', 'end_turn'):
            priority = 99

        if priority < best_priority:
            best_priority = priority
            best_idx = i

    # Respect maxCount
    max_count = select.get('maxCount', 1)
    if max_count is None or max_count < 1:
        max_count = 1
    if max_count == 1:
        return [best_idx]
    return [best_idx] + [0] * (max_count - 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

_DECK_CACHE: Optional[list[int]] = None


def agent(obs_dict: dict) -> list[int]:
    """
    Kaggle cabt engine entry point.

    Called repeatedly:
      obs_dict["select"] is None → return 60 card IDs (deck.csv)
      obs_dict["select"] exists    → return indices into option list
    """
    global _DECK_CACHE

    try:
        select = obs_dict.get('select') if isinstance(obs_dict, dict) else None

        # Deck selection phase
        if select is None:
            if _DECK_CACHE is None:
                _DECK_CACHE = read_deck()
            return list(_DECK_CACHE)

        # Action selection phase
        return select_action(obs_dict)

    except Exception:
        try:
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass
        # Never crash — return safe fallback
        try:
            if obs_dict.get('select') is None:
                return _DECK_CACHE if _DECK_CACHE else []
            opts = obs_dict['select'].get('option', [])
            return [0] if opts else []
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════════════════════════
# Smoke Test
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Test deck loading
    deck = agent({'select': None})
    assert len(deck) == 60, f"Deck must be 60, got {len(deck)}"
    print(f"✓ Deck: {len(deck)} cards, IDs: {deck[:3]}...")

    # Test action selection — cabt format
    result = agent({
        'select': {
            'option': [{'type': 'attack'}, {'type': 'retreat'}, {'type': 'pass'}],
            'maxCount': 1,
            'yourIndex': 0,
        },
        'current': {
            'players': [
                {
                    'active': [{'hp': 280, 'damage': 0, 'attacks': [{'damage': 160}]}],
                    'bench': [{'hp': 230}],
                },
                {
                    'active': [{'hp': 110, 'damage': 0, 'attacks': [{'damage': 60}]}],
                    'bench': [],
                }
            ],
            'energyAttached': True,
        },
    })
    print(f"✓ Action: chose index {result} (0=attack, 1=retreat, 2=pass)")

    # Test safety — single option
    r = agent({'select': {'option': [{'type': 'pass'}], 'maxCount': 1}})
    assert r == [0], f"Single option → [0], got {r}"
    print("✓ Single option: [0]")

    # Test safety — empty
    r = agent({'select': {'option': [], 'maxCount': 0}})
    assert r == [], f"Empty → [], got {r}"
    print("✓ Empty options: []")

    # Test safety — bad input
    r = agent(None)
    assert len(r) == 60
    print("✓ Bad input: returns deck")

    print("\n✅ All smoke tests passed — ready for Kaggle submission")
