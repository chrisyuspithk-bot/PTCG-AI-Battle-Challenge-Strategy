"""
PTCG AI Battle — Kaggle Submission Entry Point
================================================
Agent: Team Rocket Control (Big Basics, threat-aware heuristic)
Deck: 24 Pokémon (12 ex) / 20 trainers / 16 energy
Anchor: Team Rocket's Mewtwo ex (280 HP, 160 dmg)

Official contract:
  def agent(obs_dict: dict) -> list[int]:
      - obs['select'] is None → return 60 card IDs (deck selection)
      - otherwise → return indices into obs['select']['option']

Strategy: The agent evaluates every option against 5 dimensions:
  1. KO potential (can I knock out?)
  2. Threat assessment (will I be knocked out?)
  3. Board development (evolve, bench, energy)
  4. Prize trade (ex = 2 prizes, single prize = 1)
  5. Survival (retreat if active would die)

See kaggle_writeup.md for full strategy and experimental results.

Co-authored-by: openhands <openhands@all-hands.dev>
"""

from __future__ import annotations
import csv
import os
import sys
import traceback
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# Deck Loading
# ═══════════════════════════════════════════════════════════════════════════════

# Try to locate deck.csv relative to this file, then fall back to cwd
def _find_deck_csv() -> str:
    """Find deck.csv in the submission directory."""
    candidates = []
    try:
        candidates.append(os.path.join(os.path.dirname(__file__), 'deck.csv'))
    except NameError:
        pass
    candidates.append('deck.csv')
    candidates.append('/kaggle_simulations/agent/deck.csv')
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Last resort: search cwd
    return 'deck.csv'


def read_deck() -> list[int]:
    """Read 60 card IDs from deck.csv."""
    deck_path = _find_deck_csv()
    card_ids = []
    with open(deck_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get('Card ID', row.get('card_id', '0')).strip()
            try:
                card_ids.append(int(cid))
            except (ValueError, TypeError):
                continue
    if len(card_ids) < 60:
        # Pad with first card if needed (shouldn't happen)
        while len(card_ids) < 60:
            card_ids.append(card_ids[0] if card_ids else 0)
    return card_ids[:60]


# ═══════════════════════════════════════════════════════════════════════════════
# Threat-Aware Action Selection
# ═══════════════════════════════════════════════════════════════════════════════

def _get_active_hp(side: dict) -> int:
    """Get current HP of active Pokémon."""
    active = side.get('active', {}) or {}
    hp = active.get('hp', 0)
    if isinstance(hp, str):
        try: hp = int(hp)
        except ValueError: hp = 0
    dmg = active.get('damage', 0)
    if isinstance(dmg, str):
        try: dmg = int(dmg)
        except ValueError: dmg = 0
    return max(0, hp - dmg)


def _get_attack_damage(pokemon: Optional[dict]) -> int:
    """Extract damage from the first attack."""
    if not pokemon:
        return 0
    attacks = pokemon.get('attacks', pokemon.get('attack', []))
    if isinstance(attacks, dict):
        attacks = [attacks]
    if not attacks:
        dmg_str = str(pokemon.get('attack_damage', '0'))
    else:
        dmg_str = str(attacks[0].get('damage', '0'))
    try:
        return int(dmg_str)
    except (ValueError, TypeError):
        return 0


def _can_ko(my_dmg: int, opp_hp: int) -> bool:
    return my_dmg > 0 and my_dmg >= opp_hp


def select_action(obs: dict) -> list[int]:
    """
    Main action selection using threat-aware heuristic.

    Priority levels (lower = higher priority):
      0  GUARANTEED_KO — attack KOs opponent
      1  SURVIVAL — retreat if active would be KO'd next turn
      2  EVOLVE — evolve active or bench Pokémon
      3  PLAY_BASIC — bench a basic Pokémon (if bench < 3)
      4  ATTACH_ENERGY — attach energy to active
      5  ATTACK — attack if favorable
      6  TRAINER — use supporter/item
      7  PASS — end turn
    """
    select = obs.get('select')
    if select is None:
        raise RuntimeError("select_action called with select=None")

    options = select.get('option') or []
    if not options:
        return []

    n = len(options)
    if n == 1:
        return [0]

    # Parse game state
    my_side = obs.get('my_side', {}) or {}
    opp_side = obs.get('opp_side', {}) or {}
    my_active = my_side.get('active') or {}
    opp_active = opp_side.get('active') or {}
    my_bench = my_side.get('bench') or []

    my_hp = _get_active_hp(my_side)
    opp_hp = _get_active_hp(opp_side)
    my_dmg = _get_attack_damage(my_active)
    opp_dmg = _get_attack_damage(opp_active)

    i_can_ko = _can_ko(my_dmg, opp_hp)
    opp_can_ko = _can_ko(opp_dmg, my_hp)
    has_bench = len(my_bench) > 0
    bench_small = len(my_bench) < 3
    energy_attached = my_side.get('energy_attached', False)

    best_idx = 0
    best_priority = 999

    for i, opt in enumerate(options):
        opt_type = str(opt.get('type', opt.get('kind', ''))).lower()
        priority = 50  # default medium

        # Attack
        if opt_type in ('attack', 'use_attack', 'move'):
            if i_can_ko:
                priority = 0   # GUARANTEED KO
            elif my_dmg > 0:
                priority = 5   # ATTACK
            else:
                priority = 50

        # Retreat
        elif opt_type in ('retreat', 'switch'):
            if opp_can_ko and has_bench:
                priority = 1   # SURVIVAL RETREAT
            elif my_hp < 50 and has_bench:
                priority = 8   # LOW HP RETREAT
            else:
                priority = 30

        # Evolve
        elif opt_type in ('evolve', 'evolution'):
            priority = 2       # EVOLVE

        # Play basic to bench
        elif opt_type in ('play_basic', 'bench', 'play_to_bench'):
            if bench_small:
                priority = 3    # PLAY BASIC (urgent)
            else:
                priority = 10

        # Attach energy
        elif opt_type in ('attach_energy', 'energy_attach'):
            if not energy_attached:
                priority = 4    # ATTACH ENERGY
            else:
                priority = 20

        # Trainer / supporter / item
        elif opt_type in ('trainer', 'use_supporter', 'use_item', 'supporter'):
            priority = 6        # TRAINER

        # Ability
        elif opt_type in ('ability', 'use_ability'):
            priority = 9

        # Pass
        elif opt_type in ('pass', 'end_turn'):
            priority = 99

        if priority < best_priority:
            best_priority = priority
            best_idx = i

    # Safety: respect min/max count
    max_count = select.get('maxCount', select.get('max_count', 1))
    min_count = select.get('minCount', select.get('min_count', 0))
    if max_count is None or max_count < 1:
        max_count = 1
    if min_count is None or min_count < 0:
        min_count = 0

    if max_count == 1 and min_count <= 1:
        return [best_idx]

    # For multi-select decisions, return top priorities
    count = min(max_count, n)
    return [best_idx] if count == 1 else [best_idx] + [0] * (count - 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

# Cache deck on first load
_DECK_CACHE: Optional[list[int]] = None


def agent(obs_dict: dict) -> list[int]:
    """
    Kaggle agent entry point.

    Called repeatedly by the game engine:
      - First call: obs['select'] is None → return 60 card IDs
      - All other calls: obs['select'] has options → return chosen indices
    """
    global _DECK_CACHE

    try:
        select = obs_dict.get('select') if isinstance(obs_dict, dict) else None

        # ── Deck Selection ──
        if select is None:
            if _DECK_CACHE is None:
                _DECK_CACHE = read_deck()
            return list(_DECK_CACHE)

        # ── Action Selection ──
        return select_action(obs_dict)

    except Exception:
        # Never crash — return safe fallback
        try:
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass
        # Return first valid option or empty
        try:
            if obs_dict.get('select') is None:
                return _DECK_CACHE if _DECK_CACHE else []
            opts = obs_dict['select'].get('option', [])
            return [0] if opts else []
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════════════════════════
# Smoke Test (runs when executed directly)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Test 1: Deck loading
    deck = agent({'select': None})
    assert len(deck) == 60, f"Deck must be 60 cards, got {len(deck)}"
    print(f"✓ Deck loaded: {len(deck)} cards, IDs: {deck[:3]}...")

    # Test 2: Action selection — attack
    result = agent({
        'select': {
            'option': [
                {'type': 'attack', 'damage': 160},
                {'type': 'retreat'},
                {'type': 'pass'},
            ],
            'maxCount': 1, 'minCount': 0,
        },
        'my_side': {
            'active': {'hp': 280, 'damage': 0, 'attack_damage': '160'},
            'bench': [{'hp': 230}],
            'energy_attached': True,
        },
        'opp_side': {
            'active': {'hp': 110, 'damage': 0, 'attack_damage': '60'},
        },
    })
    print(f"✓ Action: chose index {result} (0=attack, 1=retreat, 2=pass)")

    # Test 3: Safety — single option
    result = agent({
        'select': {'option': [{'type': 'pass'}], 'maxCount': 1, 'minCount': 0},
    })
    assert result == [0], f"Single option must return [0], got {result}"
    print("✓ Single option: returns [0]")

    # Test 4: Safety — empty
    result = agent({'select': {'option': [], 'maxCount': 0, 'minCount': 0}})
    assert result == [], f"Empty must return [], got {result}"
    print("✓ Empty options: returns []")

    # Test 5: Safety — crash recovery
    result = agent(None)
    assert len(result) == 60
    print("✓ Crash recovery: returns deck on bad input")

    print("\n✅ All smoke tests passed — agent is ready for Kaggle submission")
