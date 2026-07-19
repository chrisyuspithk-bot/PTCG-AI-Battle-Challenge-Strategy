"""
Phase 3: Baseline Heuristic Agent
Pokémon TCG AI Battle Challenge

A threat-aware, priority-ordered decision agent with:
- KO potential calculation (can I win this turn?)
- Threat assessment (will opponent KO me next turn?)
- Prize trade evaluation (am I trading favorably?)
- Energy efficiency optimization
- Survival-first retreat logic

This agent serves as the control group for all Phase 5 experiments.
Every improvement is measured as a win-rate delta against this baseline.
"""

import random
import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto

from simulator import (
    Action, ActionType, InPlayPokemon, GameState, Player,
    MAX_BENCH, load_cards_sim, create_test_deck,
    run_match, run_tournament
)


# ═══════════════════════════════════════════════════════════════════════════════
# Threat Assessment Engine
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ThreatReport:
    """Assessment of the board state from one player's perspective."""
    my_active_can_ko_opp: bool = False
    my_active_max_dmg: int = 0
    opp_active_can_ko_me: bool = False
    opp_active_max_dmg: int = 0
    my_active_will_die: bool = False       # Will be KO'd next turn if I don't act
    opp_active_will_die: bool = False      # Will be KO'd by my attack this turn
    favorable_prize_trade: bool = False    # My active gives fewer prizes than opponent's
    can_retreat: bool = False
    bench_has_survivor: bool = False       # Bench Pokémon that can survive one hit


def safe_int(s: str) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return 0


def parse_damage(dmg_str: str) -> int:
    if not dmg_str or dmg_str.strip() in ('n/a', ''):
        return 0
    base = re.sub(r'[×+].*', '', dmg_str).strip()
    try:
        return int(base)
    except ValueError:
        return 0


def calculate_max_damage(attacker: InPlayPokemon, defender: InPlayPokemon,
                          can_attach_energy: bool = True) -> int:
    """Calculate maximum damage attacker can deal to defender this turn."""
    if attacker is None or defender is None:
        return 0

    card = attacker.card
    base_dmg = card.move_damage

    # Check if attacker has enough energy (possibly after attaching one more)
    has_energy = attacker.can_use_attack(card.move_cost)
    if not has_energy and can_attach_energy:
        # Simulate attaching one energy
        needed_colorless = card.move_cost.count('●')
        needed_specific = re.findall(r'\{([^}]+)\}', card.move_cost)
        total_needed = needed_colorless + len(needed_specific)
        if attacker.total_energy + 1 >= total_needed:
            has_energy = True

    if not has_energy:
        return 0

    # Apply weakness
    if card.pokemon_type == defender.card.weakness:
        base_dmg *= 2
    # Apply resistance
    if card.pokemon_type == defender.card.resistance:
        base_dmg = max(0, base_dmg - 20)

    return base_dmg


def assess_threat(visible: dict) -> ThreatReport:
    """Analyze the board from the current player's perspective."""
    report = ThreatReport()
    my_active = visible.get('my_active')
    opp_active = visible.get('opp_active')
    my_bench = visible.get('my_bench', [])

    if my_active is None or opp_active is None:
        return report

    # Can I KO opponent this turn?
    my_dmg = calculate_max_damage(my_active, opp_active, can_attach_energy=True)
    report.my_active_max_dmg = my_dmg
    report.my_active_can_ko_opp = (my_dmg >= opp_active.current_hp)
    report.opp_active_will_die = report.my_active_can_ko_opp

    # Can opponent KO me next turn?
    opp_dmg = calculate_max_damage(opp_active, my_active, can_attach_energy=True)
    report.opp_active_max_dmg = opp_dmg
    report.opp_active_can_ko_me = (opp_dmg >= my_active.current_hp)
    report.my_active_will_die = report.opp_active_can_ko_me

    # Prize trade
    my_prizes = my_active.card.prizes_given
    opp_prizes = opp_active.card.prizes_given
    report.favorable_prize_trade = (my_prizes <= opp_prizes)

    # Can I retreat?
    report.can_retreat = (
        my_active.total_energy >= my_active.card.retreat and
        len(my_bench) > 0
    )

    # Does bench have a survivor?
    report.bench_has_survivor = any(
        bench.card.hp - bench.damage_counters * 10 > opp_dmg
        for bench in my_bench
    )

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# Action Scoring
# ═══════════════════════════════════════════════════════════════════════════════

class ActionPriority(Enum):
    """Priority levels for action selection. Lower = higher priority."""
    GUARANTEED_KO = 0       # Attack that KOs opponent AND wins game / takes last prize
    SURVIVAL_RETREAT = 1    # Retreat when active would be KO'd
    EVOLVE_ACTIVE_SURVIVE = 2  # Evolve active to survive imminent KO
    PLAY_BASIC_SURVIVAL = 3    # Play basics when active is in danger
    ATTACK_FAVORABLE = 4    # Attack when prize trade is favorable
    EVOLVE_ACTIVE = 5       # Evolve active (general development)
    EVOLVE_BENCH = 6        # Develop bench
    ATTACH_ENERGY = 7       # Attach energy to best target
    PLAY_BASIC = 8          # Fill bench
    ATTACK_ANY = 9          # Attack when nothing better to do
    RETREAT_LOW_HP = 10     # Retreat when low but not fatal
    PASS = 11


@dataclass
class ScoredAction:
    action: Action
    priority: ActionPriority
    score: float = 0.0  # tiebreaker within same priority
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Baseline Agent
# ═══════════════════════════════════════════════════════════════════════════════

class BaselineAgent:
    """
    Threat-aware heuristic agent.

    Decision flow:
    1. GUARANTEED KO → attack if it wins
    2. SURVIVAL → retreat/evolve if active dies next turn
    3. DEVELOP → evolve, play basics, attach energy
    4. ATTACK → attack when favorable or nothing left to do
    """

    def __init__(self, name: str = "BaselineAgent", seed: int = None):
        self.name = name
        self.rng = random.Random(seed)

    def select_action(self, visible: dict) -> Action:
        """Main entry point: select the best action given visible game state."""
        threat = assess_threat(visible)
        candidates = self._generate_candidates(visible, threat)

        if not candidates:
            return Action(type=ActionType.PASS)

        # Sort by priority (lower = better), then by score (higher = better)
        candidates.sort(key=lambda c: (c.priority.value, -c.score))
        return candidates[0].action

    def _generate_candidates(self, visible: dict, threat: ThreatReport) -> list[ScoredAction]:
        """Generate all valid actions and score them."""
        candidates = []
        my_active = visible.get('my_active')
        opp_active = visible.get('opp_active')
        my_bench = visible.get('my_bench', [])
        my_hand_cards = visible.get('my_hand_cards', [])
        energy_attached = visible.get('energy_attached', False)
        can_attack = visible.get('can_attack', False)

        if my_active is None:
            return candidates

        # ── GUARANTEED KO ─────────────────────────────────────────────
        if can_attack and threat.my_active_can_ko_opp:
            candidates.append(ScoredAction(
                action=Action(type=ActionType.ATTACK, attack_index=0),
                priority=ActionPriority.GUARANTEED_KO,
                score=opp_active.card.prizes_given,  # prioritize KO'ing ex
                description="KO opponent's active"
            ))

        # ── SURVIVAL RETREAT ──────────────────────────────────────────
        if threat.my_active_will_die and threat.can_retreat:
            # Find best bench survivor to retreat to
            for i, bench in enumerate(my_bench):
                bench_hp = bench.card.hp - bench.damage_counters * 10
                if bench_hp > threat.opp_active_max_dmg:
                    candidates.append(ScoredAction(
                        action=Action(type=ActionType.RETREAT, target_index=i),
                        priority=ActionPriority.SURVIVAL_RETREAT,
                        score=bench_hp,
                        description=f"Retreat to {bench.card.name} (survives hit)"
                    ))
            # If no survivor, still retreat to save the active for later
            if not any(c.priority == ActionPriority.SURVIVAL_RETREAT for c in candidates) and my_bench:
                candidates.append(ScoredAction(
                    action=Action(type=ActionType.RETREAT, target_index=0),
                    priority=ActionPriority.SURVIVAL_RETREAT,
                    score=0,
                    description="Retreat to save active (no survivor)"
                ))

        # ── EVOLVE ACTIVE ─────────────────────────────────────────────
        for i, card in enumerate(my_hand_cards):
            if 'Stage 1' in card.stage or 'Stage 2' in card.stage:
                if card.previous_stage and card.previous_stage.lower() == my_active.card.name.lower():
                    hp_gain = card.hp - my_active.card.hp
                    dmg_gain = card.move_damage - my_active.card.move_damage
                    will_survive = (my_active.current_hp + hp_gain) > threat.opp_active_max_dmg
                    will_ko = (card.move_damage > 0 and
                               calculate_max_damage(
                                   InPlayPokemon(card=card),
                                   opp_active, can_attach_energy=False
                               ) >= opp_active.current_hp)

                    priority = ActionPriority.EVOLVE_ACTIVE
                    if will_ko:
                        priority = ActionPriority.GUARANTEED_KO
                    elif will_survive and threat.my_active_will_die:
                        priority = ActionPriority.EVOLVE_ACTIVE_SURVIVE

                    candidates.append(ScoredAction(
                        action=Action(type=ActionType.EVOLVE, card_index=i, target_index=-1),
                        priority=priority,
                        score=hp_gain + dmg_gain,
                        description=f"Evolve active to {card.name} (HP+{hp_gain})"
                    ))

        # ── ATTACK (FAVORABLE) ────────────────────────────────────────
        if can_attack and threat.my_active_max_dmg > 0:
            if threat.favorable_prize_trade:
                candidates.append(ScoredAction(
                    action=Action(type=ActionType.ATTACK, attack_index=0),
                    priority=ActionPriority.ATTACK_FAVORABLE,
                    score=threat.my_active_max_dmg,
                    description="Attack (favorable prize trade)"
                ))

        # ── EVOLVE BENCH ──────────────────────────────────────────────
        for i, card in enumerate(my_hand_cards):
            if 'Stage 1' in card.stage or 'Stage 2' in card.stage:
                for j, bench in enumerate(my_bench):
                    if card.previous_stage and card.previous_stage.lower() == bench.card.name.lower():
                        hp_gain = card.hp - bench.card.hp
                        candidates.append(ScoredAction(
                            action=Action(type=ActionType.EVOLVE, card_index=i, target_index=j),
                            priority=ActionPriority.EVOLVE_BENCH,
                            score=hp_gain + card.move_damage,
                            description=f"Evolve bench to {card.name}"
                        ))

        # ── ATTACH ENERGY ─────────────────────────────────────────────
        if not energy_attached:
            has_energy_in_hand = any('Energy' in c.stage for c in my_hand_cards)
            if has_energy_in_hand:
                # Prioritize active, then bench with highest damage potential
                candidates.append(ScoredAction(
                    action=Action(type=ActionType.ATTACH_ENERGY, card_index=0, target_index=-1),
                    priority=ActionPriority.ATTACH_ENERGY,
                    score=my_active.card.move_damage,
                    description="Attach energy to active"
                ))
                # Best bench target
                for j, bench in enumerate(my_bench):
                    candidates.append(ScoredAction(
                        action=Action(type=ActionType.ATTACH_ENERGY, card_index=0, target_index=j),
                        priority=ActionPriority.ATTACH_ENERGY,
                        score=bench.card.move_damage,
                        description=f"Attach energy to bench {bench.card.name}"
                    ))

        # ── PLAY BASIC ────────────────────────────────────────────────
        if len(my_bench) < MAX_BENCH:
            for i, card in enumerate(my_hand_cards):
                if 'Basic' in card.stage and 'Pokémon' in card.stage:
                    score = card.hp + card.move_damage
                    priority = ActionPriority.PLAY_BASIC
                    # Urgent: active is in danger, no bench → prioritize bench development
                    if threat.my_active_will_die and len(my_bench) == 0:
                        priority = ActionPriority.PLAY_BASIC_SURVIVAL
                    candidates.append(ScoredAction(
                        action=Action(type=ActionType.PLAY_BASIC, card_index=i),
                        priority=priority,
                        score=score,
                        description=f"Play {card.name} to bench"
                    ))

        # ── ATTACK (FALLBACK) ─────────────────────────────────────────
        if can_attack and threat.my_active_max_dmg > 0:
            candidates.append(ScoredAction(
                action=Action(type=ActionType.ATTACK, attack_index=0),
                priority=ActionPriority.ATTACK_ANY,
                score=threat.my_active_max_dmg,
                description="Attack (fallback)"
            ))

        # ── RETREAT (LOW HP, NON-FATAL) ───────────────────────────────
        if threat.can_retreat and my_active.current_hp <= my_active.card.hp * 0.4:
            candidates.append(ScoredAction(
                action=Action(type=ActionType.RETREAT, target_index=0),
                priority=ActionPriority.RETREAT_LOW_HP,
                score=my_active.card.hp - my_active.current_hp,
                description="Retreat (low HP)"
            ))

        return candidates

    def __call__(self, visible: dict) -> Action:
        """Make the agent callable for the simulator interface."""
        return self.select_action(visible)


# ═══════════════════════════════════════════════════════════════════════════════
# Baseline vs Simple Heuristic Benchmark
# ═══════════════════════════════════════════════════════════════════════════════

def benchmark_agents(card_pool_path: str, deck_a: list, deck_b: list,
                     num_games: int = 100, seed: int = 42) -> dict:
    """
    Position-balanced comparison: BaselineAgent vs Simple Heuristic.
    Each agent plays half the games as P1 and half as P2, eliminating
    the structural P2 advantage (first-attack privilege).
    """
    half = num_games // 2

    # Baseline as P1, Simple as P2
    r1 = run_tournament(card_pool_path, deck_a, deck_b,
                        agent_a=BaselineAgent(seed=seed), agent_b=None,
                        num_games=half, seed=seed)

    # Baseline as P2, Simple as P1
    r2 = run_tournament(card_pool_path, deck_a, deck_b,
                        agent_a=None, agent_b=BaselineAgent(seed=seed + 1),
                        num_games=half, seed=seed + half)

    return {
        'baseline_wins': r1['P1'] + r2['P2'],
        'simple_wins': r1['P2'] + r2['P1'],
        'draws': r1['Draw'] + r2['Draw'],
        'total': num_games,
        'p2_win_rate': (r1['P2'] + r2['P2']) / num_games * 100,
        'baseline_win_rate': (r1['P1'] + r2['P2']) / num_games * 100,
        'games_a': r1['games'],
        'games_b': r2['games'],
    }


def mirror_match(card_pool_path: str, deck: list, num_games: int = 100,
                 seed: int = 42) -> dict:
    """BaselineAgent mirror match. Expect ~50/50 after position balancing."""
    half = num_games // 2
    agent_a = BaselineAgent(seed=seed)
    agent_b = BaselineAgent(seed=seed + 1)

    r1 = run_tournament(card_pool_path, deck, deck,
                        agent_a=agent_a, agent_b=agent_b,
                        num_games=half, seed=seed)
    r2 = run_tournament(card_pool_path, deck, deck,
                        agent_a=agent_b, agent_b=agent_a,
                        num_games=half, seed=seed + half)

    return {
        'agent_a_wins': r1['P1'] + r2['P2'],
        'agent_b_wins': r1['P2'] + r2['P1'],
        'draws': r1['Draw'] + r2['Draw'],
        'total': num_games,
        'p2_win_rate': (r1['P2'] + r2['P2']) / num_games * 100,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Deck Definitions for Testing
# ═══════════════════════════════════════════════════════════════════════════════

def build_fire_deck(card_pool: dict) -> list:
    """Fire aggro deck: Charmander line + Growlithe line."""
    return create_test_deck(card_pool, [
        'Charmander', 'Charmeleon', 'Growlithe', 'Arcanine ex',
    ], ['Basic {R} Energy'], ['Ultra Ball'])


def build_water_deck(card_pool: dict) -> list:
    """Water deck using available cards."""
    return create_test_deck(card_pool, [
        'Magikarp', 'Lapras',
    ], ['Basic {W} Energy'], ['Ultra Ball'])


def build_fighting_deck(card_pool: dict) -> list:
    """Fighting deck."""
    return create_test_deck(card_pool, [
        'Riolu', 'Lucario', 'Hitmonchan', 'Hitmonlee',
    ], ['Basic {F} Energy'], ['Ultra Ball'])


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    import time

    csv_path = sys.argv[1] if len(sys.argv) > 1 else '/workspace/EN_Card_Data.csv'
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    print("Loading card pool...")
    cards = load_cards_sim(csv_path)
    print(f"Loaded {len(cards)} cards")

    # Use verified card names from the pool
    deck_fire = create_test_deck(cards, [
        'Charmander', 'Charmeleon', 'Ponyta', 'Rapidash',
    ], ['Basic {R} Energy'], ['Ultra Ball'])

    deck_water = create_test_deck(cards, [
        'Psyduck', 'Golduck', 'Poliwag', 'Poliwhirl',
    ], ['Basic {W} Energy'], ['Ultra Ball'])

    print(f"\nFire deck: {len(deck_fire)} cards")
    print(f"Water deck: {len(deck_water)} cards")

    # ── Benchmark: Baseline vs Simple Heuristic (position-balanced) ──
    print(f"\n{'='*60}")
    print(f"BENCHMARK: BaselineAgent vs Simple Heuristic")
    print(f"Position-balanced: each agent plays P1 & P2 equally")
    print(f"Identical Fire decks, {num_games} games")
    print(f"{'='*60}")

    t0 = time.time()
    results = benchmark_agents(csv_path, deck_fire, deck_fire, num_games=num_games)
    elapsed = time.time() - t0

    print(f"\nResults ({results['total']} games in {elapsed:.1f}s):")
    print(f"  Baseline Agent:  {results['baseline_wins']} wins ({results['baseline_win_rate']:.1f}%)")
    print(f"  Simple Heuristic: {results['simple_wins']} wins ({100 - results['baseline_win_rate']:.1f}%)")
    print(f"  Draws:           {results['draws']}")
    print(f"  ⚠ P2 advantage:  {results['p2_win_rate']:.1f}% win rate (structural)")

    # ── Mirror match ──
    print(f"\n{'='*60}")
    print(f"MIRROR MATCH: BaselineAgent vs BaselineAgent (position-balanced)")
    print(f"{'='*60}")

    t0 = time.time()
    mirror = mirror_match(csv_path, deck_fire, num_games=num_games)
    elapsed = time.time() - t0

    print(f"\nResults ({mirror['total']} games in {elapsed:.1f}s):")
    print(f"  Agent A: {mirror['agent_a_wins']} wins")
    print(f"  Agent B: {mirror['agent_b_wins']} wins")
    print(f"  Draws:   {mirror['draws']}")
    print(f"  P2 win rate: {mirror['p2_win_rate']:.1f}%")
    print(f"  Expected: ~50/50 (identical agents)")
