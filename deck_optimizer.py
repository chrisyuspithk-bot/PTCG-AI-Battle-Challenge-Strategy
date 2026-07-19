"""
Phase 4: Deck Design & Optimization
Pokémon TCG AI Battle Challenge

Builds optimized 60-card decks using card pool efficiency data from Phase 1.
Supports multiple archetypes with automated cross-matchup testing.
"""

import csv
import re
import json
import random
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Optional

from simulator import (
    load_cards_sim, create_test_deck, run_match, run_tournament,
    SimCard, Player, DECK_SIZE, MAX_COPIES, validate_deck,
)
from baseline_agent import BaselineAgent


# ═══════════════════════════════════════════════════════════════════════════════
# Card Pool Extended Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def safe_int(s: str) -> int:
    try: return int(s.strip())
    except: return 0


@dataclass
class CardMeta:
    """Extended card metadata for deck building."""
    card: SimCard
    efficiency: float = 0.0      # (dmg/energy) * (HP/prizes)
    is_staple: bool = False      # Ultra Ball, Boss, etc.
    evolution_line: list = field(default_factory=list)
    line_complete: bool = False  # All stages available in pool


def _is_pokemon(card: SimCard) -> bool:
    return 'Pokémon' in card.stage

def _is_basic(card: SimCard) -> bool:
    return 'Basic' in card.stage and 'Pokémon' in card.stage

def _is_trainer(card: SimCard) -> bool:
    return card.stage.strip() in ('Item', 'Supporter', 'Pokémon Tool', 'Stadium')

def _is_energy(card: SimCard) -> bool:
    return 'Energy' in card.stage

def _energy_cost_count(cost_str: str) -> int:
    if not cost_str or cost_str.strip() in ('n/a', ''):
        return 0
    return cost_str.count('●') + len(re.findall(r'\{[^}]+\}', cost_str))


def build_card_metadata(cards: dict) -> dict[str, CardMeta]:
    """Build extended metadata for all cards."""
    meta = {}
    name_to_ids = defaultdict(list)
    for cid, card in cards.items():
        name_to_ids[card.name].append(cid)

    # Identify staples
    staples = {'Ultra Ball', "Boss's Orders", 'Rare Candy', 'Energy Search',
               'Master Ball', 'Nest Ball', 'Professor'}

    for cid, card in cards.items():
        cost = _energy_cost_count(card.move_cost)
        is_poke = _is_pokemon(card)

        if not is_poke or not (card.move_damage > 0 and cost > 0):
            eff = 0
        else:
            hp_per_prize = card.hp / card.prizes_given if card.prizes_given > 0 else card.hp
            dmg_per_energy = card.move_damage / cost
            eff = dmg_per_energy * hp_per_prize

        is_staple = any(s.lower() in card.name.lower() for s in staples)

        meta[card.name] = CardMeta(
            card=card,
            efficiency=eff,
            is_staple=is_staple,
        )

    return meta


# ═══════════════════════════════════════════════════════════════════════════════
# Archetype Definitions
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Archetype:
    name: str
    description: str
    strategy: str  # 'aggro', 'control', 'midrange', 'combo'
    attacker_names: list  # Key Pokémon to include
    energy_type: str      # Primary energy type
    trainer_names: list   # Key trainer cards
    synergy_filter: str = ""  # Filter for tribal synergy (e.g., "Team Rocket")


# Three distinct archetypes built from the card pool

ARCHETYPES = {
    'team_rocket': Archetype(
        name="Team Rocket Control",
        description="Big Basic Pokémon with dedicated tribal support engine. "
                    "Team Rocket's Mewtwo ex (280 HP, 160 dmg) as anchor. "
                    "97-card synergy pool enables consistent draw and search.",
        strategy="control",
        attacker_names=[
            "Team Rocket's Mewtwo ex", "Team Rocket's Kangaskhan ex",
            "Team Rocket's Moltres ex", "Team Rocket's Articuno",
            "Team Rocket's Zapdos", "Team Rocket's Houndoom",
        ],
        energy_type="Basic {D} Energy",
        trainer_names=[
            "Ultra Ball", "Boss's Orders",
            "Team Rocket's Ariana", "Team Rocket's Giovanni",
            "Team Rocket's Petrel", "Team Rocket's Archer",
            "Team Rocket's Proton",
        ],
        synergy_filter="Team Rocket",
    ),
    'aggro_basic': Archetype(
        name="Aggro Basics",
        description="Low-cost, high-efficiency Basic Pokémon. "
                    "Hop's Cramorant (120 dmg/1e), Sawk (90 dmg/1e), "
                    "Fan Rotom (70 dmg/1e). Single-prize attackers trade "
                    "favorably against multi-prize ex Pokémon.",
        strategy="aggro",
        attacker_names=[
            "Hop's Cramorant", "Sawk", "Fan Rotom",
            "Solrock", "Iron Boulder", "Rotom ex",
        ],
        energy_type="Basic {F} Energy",
        trainer_names=[
            "Ultra Ball", "Boss's Orders",
            "Buddy-Buddy Poffin", "Cheren",
        ],
    ),
    'evolution_power': Archetype(
        name="Evolution Power",
        description="Evolve into high-HP Stage 1/2 attackers. "
                    "Charmeleon (90 dmg), Rapidash, Arcanine ex lines. "
                    "Uses Rare Candy + Salvatore for fast evolution.",
        strategy="combo",
        attacker_names=[
            "Charmander", "Charmeleon",
            "Ponyta", "Rapidash",
            "Growlithe", "Arcanine ex",
        ],
        energy_type="Basic {R} Energy",
        trainer_names=[
            "Ultra Ball", "Boss's Orders",
            "Rare Candy", "Salvatore", "Brock's Scouting",
        ],
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Deck Builder
# ═══════════════════════════════════════════════════════════════════════════════

class DeckBuilder:
    """Builds optimized 60-card decks for a given archetype."""

    def __init__(self, cards: dict, meta: dict[str, CardMeta]):
        self.cards = cards
        self.meta = meta
        self.name_to_ids = defaultdict(list)
        for cid, card in cards.items():
            self.name_to_ids[card.name].append(cid)

    def build(self, archetype: Archetype, energy_count: int = 12) -> tuple[list, dict]:
        """
        Build a 60-card deck for the archetype.
        Returns (deck_list, build_report).
        """
        deck = []
        report = {'archetype': archetype.name, 'cards': {}}

        def _add_copies(name: str, max_count: int):
            """Add up to max_count copies of a card to deck. Uses same card ID if needed."""
            ids = self.name_to_ids.get(name, [])
            if not ids:
                return 0
            count = min(max_count, DECK_SIZE - len(deck) - energy_count)
            for i in range(count):
                deck.append(self.cards[ids[i % len(ids)]])
            if count > 0:
                report['cards'][name] = report['cards'].get(name, 0) + count
            return count

        # 1. Add key attackers (4 copies each)
        for name in archetype.attacker_names:
            _add_copies(name, 4)

        # 2. Add trainers (4 copies each, up to 20 trainer slots)
        trainer_slots = 20
        for name in archetype.trainer_names:
            if trainer_slots <= 0:
                break
            added = _add_copies(name, min(4, trainer_slots))
            trainer_slots -= added

        # 3. Add synergy basics from tribal pool (or generic filler)
        if archetype.synergy_filter and len(deck) + energy_count < DECK_SIZE:
            synergy = [
                c for c in self.cards.values()
                if archetype.synergy_filter in c.name
                and 'Basic' in c.stage and 'Pokémon' in c.stage
                and c.name not in archetype.attacker_names
            ]
            synergy.sort(key=lambda c: c.hp, reverse=True)
            target_pokemon = 20
            current_pokemon = sum(
                1 for c in deck if 'Pokémon' in c.stage
            )
            for c in synergy:
                if current_pokemon >= target_pokemon:
                    break
                added = _add_copies(c.name, min(4, target_pokemon - current_pokemon))
                current_pokemon += added

        # 3b. Generic filler for non-tribal decks
        if not archetype.synergy_filter:
            current_pokemon = sum(1 for c in deck if 'Pokémon' in c.stage)
            if current_pokemon < 15:
                filler = [
                    c for c in self.cards.values()
                    if 'Basic' in c.stage and 'Pokémon' in c.stage
                    and c.name not in archetype.attacker_names
                ]
                filler.sort(key=lambda c: c.hp, reverse=True)
                needed = 15 - current_pokemon
                for c in filler:
                    if needed <= 0:
                        break
                    added = _add_copies(c.name, min(4, needed))
                    needed -= added

        # 4. Fill remaining with energy (respect energy_count parameter)
        energy_ids = self.name_to_ids.get(archetype.energy_type, [])
        if not energy_ids:
            for cid, card in self.cards.items():
                if _is_energy(card) and card.stage != 'Special Energy':
                    energy_ids.append(cid)
                    break

        # Only add energy up to the specified energy_count
        current_energy = sum(1 for c in deck if _is_energy(c))
        while current_energy < energy_count and energy_ids:
            deck.append(self.cards[energy_ids[0]])
            current_energy += 1

        # If deck still isn't full, pad with more energy
        while len(deck) < DECK_SIZE and energy_ids:
            deck.append(self.cards[energy_ids[0]])

        deck = deck[:DECK_SIZE]
        report['total_cards'] = len(deck)
        report['pokemon_count'] = sum(1 for c in deck if _is_pokemon(c))
        report['trainer_count'] = sum(1 for c in deck if _is_trainer(c))
        report['energy_count'] = sum(1 for c in deck if _is_energy(c))
        report['basic_count'] = sum(1 for c in deck if _is_basic(c))
        report['ex_count'] = sum(1 for c in deck if c.is_ex)

        errors = validate_deck(deck)
        report['valid'] = len(errors) == 0
        report['errors'] = errors

        return deck, report


# ═══════════════════════════════════════════════════════════════════════════════
# Deck Testing & Matchup Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def test_matchup(card_pool_path: str, deck_a: list, deck_b: list,
                 name_a: str, name_b: str,
                 num_games: int = 50, seed: int = 42) -> dict:
    """
    Position-balanced matchup test.
    Returns win rates and game stats.
    """
    half = num_games // 2
    agent = BaselineAgent(seed=seed)

    # Deck A as P1, Deck B as P2
    r1 = run_tournament(card_pool_path, deck_a, deck_b,
                        agent_a=agent, agent_b=BaselineAgent(seed=seed + 1),
                        num_games=half, seed=seed)

    # Deck A as P2, Deck B as P1
    r2 = run_tournament(card_pool_path, deck_b, deck_a,
                        agent_a=BaselineAgent(seed=seed + 2), agent_b=agent,
                        num_games=half, seed=seed + half)

    wins_a = r1['P1'] + r2['P2']
    wins_b = r1['P2'] + r2['P1']
    all_games = r1['games'] + r2['games']
    avg_turns = sum(g['turns'] for g in all_games) / len(all_games) if all_games else 0

    return {
        'name_a': name_a, 'name_b': name_b,
        'wins_a': wins_a, 'wins_b': wins_b,
        'win_rate_a': wins_a / num_games * 100,
        'win_rate_b': wins_b / num_games * 100,
        'draws': r1['Draw'] + r2['Draw'],
        'total': num_games,
        'avg_turns': avg_turns,
    }


def run_matchup_matrix(card_pool_path: str, decks: dict[str, list],
                       num_games: int = 50) -> dict:
    """Run all pairwise matchups between decks."""
    results = {}
    deck_names = list(decks.keys())

    for i, name_a in enumerate(deck_names):
        for name_b in deck_names[i:]:  # Upper triangle including diagonal
            if name_a == name_b:
                # Mirror match
                half = num_games // 2
                agent = BaselineAgent(seed=42)
                r = run_tournament(card_pool_path, decks[name_a], decks[name_a],
                                   agent_a=agent, agent_b=BaselineAgent(seed=43),
                                   num_games=num_games, seed=42)
                results[f"{name_a}_mirror"] = {
                    'matchup': f"{name_a} (mirror)",
                    'p1_wins': r['P1'], 'p2_wins': r['P2'],
                    'p2_rate': r['win_rate_b'],
                    'draws': r['Draw'],
                    'total': num_games,
                }
            else:
                key = f"{name_a}_vs_{name_b}"
                r = test_matchup(card_pool_path, decks[name_a], decks[name_b],
                                 name_a, name_b, num_games=num_games)
                results[key] = r

    return results


def deck_diff_report(deck_a: list, deck_b: list) -> dict:
    """Compare two decks and report differences."""
    def count_names(deck):
        c = Counter(card.name for card in deck)
        return dict(c)

    ca = count_names(deck_a)
    cb = count_names(deck_b)
    all_names = set(ca.keys()) | set(cb.keys())

    only_a = {n: ca[n] for n in all_names if n in ca and n not in cb}
    only_b = {n: cb[n] for n in all_names if n in cb and n not in ca}
    diff = {n: (ca.get(n, 0), cb.get(n, 0)) for n in all_names if ca.get(n, 0) != cb.get(n, 0)}

    return {
        'unique_to_a': only_a,
        'unique_to_b': only_b,
        'count_diff': diff,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Card Impact Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def card_impact_analysis(card_pool_path: str, deck: list,
                         card_name: str, num_games: int = 50) -> dict:
    """
    Measure win-rate impact of removing a specific card from the deck.
    """
    # Build deck without the target card
    deck_without = [c for c in deck if c.name != card_name]
    # Pad with energy to maintain 60 cards
    energy_cards = [c for c in deck if _is_energy(c)]
    while len(deck_without) < DECK_SIZE and energy_cards:
        deck_without.append(energy_cards[0])

    r_with = test_matchup(card_pool_path, deck, deck, "With", "With", num_games=num_games // 2)
    r_without = test_matchup(card_pool_path, deck_without, deck_without,
                             "Without", "Without", num_games=num_games // 2)

    return {
        'card': card_name,
        'deck_with_win_rate': r_with['win_rate_a'],
        'deck_without_win_rate': r_without['win_rate_a'],
        'impact': r_with['win_rate_a'] - r_without['win_rate_a'],
        'games': num_games,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys

    csv_path = sys.argv[1] if len(sys.argv) > 1 else '/workspace/EN_Card_Data.csv'
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    print("Loading card pool...")
    cards = load_cards_sim(csv_path)
    meta = build_card_metadata(cards)
    print(f"Loaded {len(cards)} cards, {len(meta)} with metadata")

    builder = DeckBuilder(cards, meta)
    decks = {}

    # Build each archetype
    for key, arch in ARCHETYPES.items():
        print(f"\n{'='*60}")
        print(f"Building: {arch.name}")
        print(f"Strategy: {arch.strategy.upper()}")
        print(f"Description: {arch.description}")
        print(f"{'='*60}")

        deck, report = builder.build(arch)
        errors = validate_deck(deck)

        print(f"  Cards: {report['total_cards']}")
        print(f"  Pokémon: {report['pokemon_count']} ({report['basic_count']} basic, {report['ex_count']} ex)")
        print(f"  Trainers: {report['trainer_count']}")
        print(f"  Energy: {report['energy_count']}")
        print(f"  Valid: {report['valid']}")
        if errors:
            print(f"  ERRORS: {errors}")

        print(f"  Key attackers:")
        for name, count in report['cards'].items():
            if any(name == a for a in arch.attacker_names):
                print(f"    {count}x {name}")

        if report['valid']:
            decks[key] = deck
        else:
            print(f"  ⚠ Skipping invalid deck")

    # ── Run matchup matrix ──
    if len(decks) >= 2:
        print(f"\n{'='*60}")
        print(f"MATCHUP MATRIX ({num_games} games per matchup)")
        print(f"{'='*60}")

        t0 = time.time()
        results = run_matchup_matrix(csv_path, decks, num_games=num_games)
        elapsed = time.time() - t0

        # Print matchups
        matchups = [(k, v) for k, v in results.items() if not k.endswith('_mirror')]
        mirrors = [(k, v) for k, v in results.items() if k.endswith('_mirror')]

        for key, r in matchups:
            print(f"\n  {r['name_a']} vs {r['name_b']}:")
            print(f"    {r['name_a']}: {r['wins_a']} wins ({r['win_rate_a']:.0f}%)")
            print(f"    {r['name_b']}: {r['wins_b']} wins ({r['win_rate_b']:.0f}%)")
            print(f"    Draws: {r['draws']}, Avg turns: {r['avg_turns']:.1f}")

        for key, r in mirrors:
            name = key.replace('_mirror', '')
            print(f"\n  {name} (mirror):")
            print(f"    P2 win rate: {r['p2_rate']:.0f}%")

        print(f"\n  Total time: {elapsed:.1f}s for {len(matchups) + len(mirrors)} matchups")
