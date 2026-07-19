"""
Phase 1: Card Pool Analysis & Game Mechanics Foundation
Pokémon TCG AI Battle Challenge — Strategy Category

Parses EN_Card_Data.csv, classifies all cards by role, computes efficiency
metrics, and maps built-in synergies for deck construction.
"""

import csv
import re
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ─── Data Model ────────────────────────────────────────────────────────────

@dataclass
class Card:
    card_id: int
    name: str
    expansion: str
    collection_no: str
    stage: str           # Basic Pokémon, Stage 1, Stage 2, Item, Supporter, etc.
    rule: str            # Pokémon ex, ACE SPEC, Mega Pokémon ex, etc.
    category: str        # Trainer's Pokémon, Ancient, Future, Tera, Fossil, etc.
    previous_stage: str
    hp: int
    pokemon_type: str    # {G}, {R}, {W}, etc.
    weakness: str
    resistance: str
    retreat: int
    move_name: str
    cost: str
    damage: int
    effect: str

    # ── derived ──
    is_pokemon: bool = False
    is_basic: bool = False
    is_stage1: bool = False
    is_stage2: bool = False
    is_ex: bool = False
    is_mega_ex: bool = False
    is_ace_spec: bool = False
    is_trainer: bool = False
    is_item: bool = False
    is_supporter: bool = False
    is_tool: bool = False
    is_stadium: bool = False
    is_energy: bool = False
    is_special_energy: bool = False
    prizes_given: int = 1   # 2 for ex/Mega ex, 1 otherwise
    has_ability: bool = False
    has_rule_box: bool = False

    # ── computed metrics ──
    energy_cost_count: int = 0
    colorless_cost: int = 0
    specific_cost: int = 0
    damage_per_energy: float = 0.0
    hp_per_prize: float = 0.0
    damage_efficiency: float = 0.0       # (damage / energy) * (hp / prizes)
    attack_count: int = 1                 # number of attacks

    # ── role classification ──
    roles: list = field(default_factory=list)


# ─── Card Loader ────────────────────────────────────────────────────────────

def safe_int(s: str) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return 0


def parse_energy_cost(cost_str: str) -> tuple[int, int, int]:
    """Returns (total, colorless, specific)."""
    if not cost_str or cost_str.strip() in ('n/a', ''):
        return 0, 0, 0
    colorless = cost_str.count('●')
    specific = len(re.findall(r'\{[^}]+\}', cost_str))
    return colorless + specific, colorless, specific


def parse_damage(dmg_str: str) -> int:
    """Extract base damage, stripping modifiers like × or +."""
    if not dmg_str or dmg_str.strip() in ('n/a', ''):
        return 0
    base = re.sub(r'[×+].*', '', dmg_str).strip()
    try:
        return int(base)
    except ValueError:
        return 0


def load_cards(csv_path: str) -> list[Card]:
    """Load and classify all cards from the English CSV."""
    cards = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stage = row['Stage (Pokémon)/Type (Energy and Trainer)'].strip()
            rule = row.get('Rule', '').strip()
            category = row.get('Category', '').strip()
            hp = safe_int(row.get('HP', '0'))
            retreat = safe_int(row.get('Retreat', '0'))
            cost_str = row.get('Cost', 'n/a')
            dmg_str = row.get('Damage', 'n/a')
            effect = row.get('Effect Explanation', '') or ''

            total_cost, colorless, specific = parse_energy_cost(cost_str)
            damage = parse_damage(dmg_str)

            c = Card(
                card_id=safe_int(row['Card ID']),
                name=row['Card Name'].strip(),
                expansion=row.get('Expansion', '').strip(),
                collection_no=row.get('Collection No.', '').strip(),
                stage=stage,
                rule=rule,
                category=category,
                previous_stage=row.get('Previous stage', '').strip(),
                hp=hp,
                pokemon_type=row.get('Type', '').strip(),
                weakness=row.get('Weakness', '').strip(),
                resistance=row.get('Resistance (Type)', '').strip(),
                retreat=retreat,
                move_name=row.get('Move Name', '').strip(),
                cost=cost_str,
                damage=damage,
                effect=effect,
                energy_cost_count=total_cost,
                colorless_cost=colorless,
                specific_cost=specific,
            )

            # ── type classification ──
            c.is_pokemon = 'Pokémon' in stage
            c.is_basic = 'Basic' in stage
            c.is_stage1 = 'Stage 1' in stage
            c.is_stage2 = 'Stage 2' in stage
            c.is_ex = rule in ('Pokémon ex', 'Mega Pokémon ex')
            c.is_mega_ex = rule == 'Mega Pokémon ex'
            c.is_ace_spec = rule == 'ACE SPEC'
            c.is_trainer = stage in ('Item', 'Supporter', 'Pokémon Tool', 'Stadium')
            c.is_item = stage == 'Item'
            c.is_supporter = stage == 'Supporter'
            c.is_tool = stage == 'Pokémon Tool'
            c.is_stadium = stage == 'Stadium'
            c.is_energy = 'Energy' in stage
            c.is_special_energy = stage == 'Special Energy'
            c.has_ability = '[Ability]' in (effect + c.move_name)
            c.has_rule_box = c.is_ex or c.is_mega_ex
            c.prizes_given = 2 if c.has_rule_box else 1

            # ── metrics ──
            if c.is_pokemon and c.hp > 0:
                c.hp_per_prize = c.hp / c.prizes_given
            if c.energy_cost_count > 0:
                c.damage_per_energy = c.damage / c.energy_cost_count
            if c.hp_per_prize > 0 and c.damage_per_energy > 0:
                c.damage_efficiency = c.damage_per_energy * c.hp_per_prize

            # ── role classification ──
            classify_role(c)

            cards.append(c)

    return cards


# ─── Role Classification ────────────────────────────────────────────────────

def classify_role(c: Card):
    """Assign roles based on card text and attributes."""
    effect_lower = (c.effect + c.move_name).lower()

    if c.is_energy:
        if c.is_special_energy:
            c.roles.append('special_energy')
        else:
            c.roles.append('basic_energy')
        return

    if c.is_trainer:
        if c.is_supporter:
            c.roles.append('supporter')
        elif c.is_item:
            c.roles.append('item')
        elif c.is_tool:
            c.roles.append('tool')
        elif c.is_stadium:
            c.roles.append('stadium')

    # Energy acceleration
    energy_patterns = [
        'attach', 'energy from your discard', 'energy from your hand',
        'search your deck for', 'attach a basic',
    ]
    if any(p in effect_lower for p in energy_patterns) and any(
        p in effect_lower for p in ['to 1 of your', 'to your', 'to this pokémon']
    ):
        if 'opponent' not in effect_lower.split('attach')[0] if 'attach' in effect_lower else True:
            c.roles.append('energy_acceleration')

    # Draw/search engine
    draw_patterns = ['draw', 'search your deck']
    if any(p in effect_lower for p in draw_patterns):
        c.roles.append('draw_engine')

    # Disruption
    disrupt_patterns = ['discard', 'opponent', 'shuffle', 'switch in 1 of your opponent']
    if any(p in effect_lower for p in disrupt_patterns):
        c.roles.append('disruption')

    # Healing
    if 'heal' in effect_lower:
        c.roles.append('healing')

    # Bench manipulation (switch/retreat)
    if any(p in effect_lower for p in ['switch', 'retreat', 'bench']):
        c.roles.append('mobility')

    # Prize manipulation
    if 'prize card' in effect_lower:
        c.roles.append('prize_manipulation')

    # Pokémon roles
    if c.is_pokemon and c.damage > 0:
        if c.energy_cost_count <= 2 and c.damage >= 80:
            c.roles.append('efficient_attacker')
        if c.damage >= 150:
            c.roles.append('heavy_hitter')
        if c.hp >= 200:
            c.roles.append('wall')
        elif c.hp >= 130:
            c.roles.append('midrange')

    if c.is_pokemon and c.retreat <= 1:
        c.roles.append('pivot')

    if c.has_ability:
        c.roles.append('ability_user')

    if c.is_pokemon and c.is_basic and c.hp <= 70 and c.damage >= 60 and c.energy_cost_count <= 1:
        c.roles.append('aggro_basic')


# ─── Synergy Mapping ────────────────────────────────────────────────────────

SYNERGY_GROUPS = {
    'Team Rocket': 'Trainer\'s Pokémon（Team Rocket）',
    'N': 'Trainer\'s Pokémon（N）',
    'Hop': 'Trainer\'s Pokémon（Hop）',
    'Ethan': 'Trainer\'s Pokémon（Ethan）',
    'Cynthia': 'Trainer\'s Pokémon（Cynthia）',
    'Marnie': 'Trainer\'s Pokémon（Marnie）',
    'Larry': 'Trainer\'s Pokémon（Larry）',
    'Erika': 'Trainer\'s Pokémon（Erika）',
    'Misty': 'Trainer\'s Pokémon（Misty）',
    'Steven': 'Trainer\'s Pokémon（Steven）',
    'Arven': 'Trainer\'s Pokémon（Arven）',
    'Iono': 'Trainer\'s Pokémon（Iono）',
    'Lillie': 'Trainer\'s Pokémon（Lillie）',
    'Ancient': 'Ancient',
    'Future': 'Future',
    'Tera': 'Tera',
}


def build_synergy_map(cards: list[Card]) -> dict:
    """Group cards by built-in synergy categories."""
    synergy_map = defaultdict(lambda: defaultdict(list))

    for c in cards:
        for group_name, cat_value in SYNERGY_GROUPS.items():
            if cat_value.startswith('Trainer'):
                # Trainer's Pokémon: match category field exactly
                if c.category == cat_value:
                    synergy_map[group_name]['pokemon'].append(c)
                # Also match supporters/items referencing this trainer
                if group_name in c.name and c.is_trainer:
                    synergy_map[group_name]['trainers'].append(c)
            elif cat_value == 'Tera':
                if 'Tera' in c.category:
                    synergy_map[group_name]['pokemon'].append(c)
            elif cat_value in ('Ancient', 'Future'):
                if c.category == cat_value:
                    synergy_map[group_name]['pokemon'].append(c)

    return synergy_map


# ─── Efficiency Rankings ────────────────────────────────────────────────────

def rank_pokemon(cards: list[Card], top_n: int = 30) -> dict:
    """Rank Pokémon by damage efficiency: (dmg/energy) * (HP/prizes)."""
    pokemon = [c for c in cards if c.is_pokemon and c.damage > 0 and c.energy_cost_count > 0]
    ranked = sorted(pokemon, key=lambda c: c.damage_efficiency, reverse=True)
    return {
        'by_efficiency': [
            {
                'name': c.name,
                'hp': c.hp,
                'damage': c.damage,
                'cost': c.energy_cost_count,
                'dmg_per_energy': round(c.damage_per_energy, 1),
                'hp_per_prize': round(c.hp_per_prize, 1),
                'efficiency': round(c.damage_efficiency, 1),
                'type': c.pokemon_type,
                'stage': c.stage,
                'prizes': c.prizes_given,
                'roles': c.roles,
            }
            for c in ranked[:top_n]
        ],
        'by_damage': [
            {
                'name': c.name,
                'damage': c.damage,
                'cost': c.energy_cost_count,
                'hp': c.hp,
                'type': c.pokemon_type,
                'stage': c.stage,
            }
            for c in sorted(pokemon, key=lambda c: c.damage, reverse=True)[:top_n]
        ],
        'by_hp': [
            {
                'name': c.name,
                'hp': c.hp,
                'damage': c.damage,
                'type': c.pokemon_type,
                'stage': c.stage,
                'prizes': c.prizes_given,
            }
            for c in sorted(pokemon, key=lambda c: c.hp, reverse=True)[:top_n]
        ],
    }


# ─── Statistics ─────────────────────────────────────────────────────────────

def compute_statistics(cards: list[Card]) -> dict:
    """Compute aggregate statistics about the card pool."""
    pokemon = [c for c in cards if c.is_pokemon]
    trainers = [c for c in cards if c.is_trainer]
    energies = [c for c in cards if c.is_energy]

    role_counts = Counter()
    for c in cards:
        for r in c.roles:
            role_counts[r] += 1

    stage_counts = Counter(c.stage for c in cards)
    rule_counts = Counter(c.rule for c in cards if c.rule not in ('n/a', ''))
    type_counts = Counter(c.pokemon_type for c in pokemon if c.pokemon_type not in ('n/a', ''))

    hp_values = [c.hp for c in pokemon if c.hp > 0]
    dmg_values = [c.damage for c in pokemon if c.damage > 0]
    cost_values = [c.energy_cost_count for c in pokemon if c.damage > 0]

    return {
        'total_cards': len(cards),
        'pokemon_count': len(pokemon),
        'trainer_count': len(trainers),
        'energy_count': len(energies),
        'basic_count': sum(1 for c in pokemon if c.is_basic),
        'stage1_count': sum(1 for c in pokemon if c.is_stage1),
        'stage2_count': sum(1 for c in pokemon if c.is_stage2),
        'ex_count': sum(1 for c in pokemon if c.is_ex),
        'mega_ex_count': sum(1 for c in pokemon if c.is_mega_ex),
        'ace_spec_count': sum(1 for c in cards if c.is_ace_spec),
        'ability_count': sum(1 for c in pokemon if c.has_ability),
        'stage_distribution': dict(stage_counts.most_common()),
        'rule_distribution': dict(rule_counts.most_common()),
        'type_distribution': dict(type_counts.most_common()),
        'role_distribution': dict(role_counts.most_common()),
        'hp': {
            'min': min(hp_values) if hp_values else 0,
            'max': max(hp_values) if hp_values else 0,
            'avg': round(sum(hp_values) / len(hp_values), 1) if hp_values else 0,
        },
        'damage': {
            'min': min(dmg_values) if dmg_values else 0,
            'max': max(dmg_values) if dmg_values else 0,
            'avg': round(sum(dmg_values) / len(dmg_values), 1) if dmg_values else 0,
        },
        'energy_cost': {
            'min': min(cost_values) if cost_values else 0,
            'max': max(cost_values) if cost_values else 0,
            'avg': round(sum(cost_values) / len(cost_values), 1) if cost_values else 0,
        },
    }


# ─── Energy Acceleration Cards ──────────────────────────────────────────────

def find_energy_accelerators(cards: list[Card]) -> list[dict]:
    """Extract all energy acceleration cards with details."""
    return [
        {
            'name': c.name,
            'stage': c.stage,
            'type': c.pokemon_type,
            'effect': c.effect[:200],
            'is_ability': c.has_ability,
        }
        for c in cards if 'energy_acceleration' in c.roles
    ]


# ─── Comeback / Prize Mechanics ─────────────────────────────────────────────

def find_prize_mechanics(cards: list[Card]) -> list[dict]:
    """Extract all cards that interact with prize cards."""
    return [
        {
            'name': c.name,
            'stage': c.stage,
            'type': c.pokemon_type,
            'effect': c.effect[:200],
        }
        for c in cards if 'prize_manipulation' in c.roles
    ]


# ─── Archetype Summary ──────────────────────────────────────────────────────

def archetype_summary(synergy_map: dict) -> dict:
    """Summarize each archetype with counts and key cards."""
    summary = {}
    for group, sub in synergy_map.items():
        pokemon_cards = sub.get('pokemon', [])
        trainer_cards = sub.get('trainers', [])
        ex_count = sum(1 for c in pokemon_cards if c.is_ex)
        summary[group] = {
            'pokemon_count': len(pokemon_cards),
            'trainer_support_count': len(trainer_cards),
            'ex_count': ex_count,
            'total_support': len(pokemon_cards) + len(trainer_cards),
            'key_pokemon': [c.name for c in sorted(pokemon_cards, key=lambda c: c.hp, reverse=True)[:5]],
            'key_trainers': [c.name for c in trainer_cards[:5]],
        }
    return summary


# ─── Main Analysis ──────────────────────────────────────────────────────────

def run_analysis(csv_path: str, output_path: str = None):
    """Run full Phase 1 analysis and output results."""
    print("Loading cards...")
    cards = load_cards(csv_path)
    print(f"Loaded {len(cards)} cards")

    print("\nComputing statistics...")
    stats = compute_statistics(cards)

    print("\nBuilding synergy map...")
    synergy_map = build_synergy_map(cards)
    archetypes = archetype_summary(synergy_map)

    print("\nRanking Pokémon...")
    rankings = rank_pokemon(cards)

    print("\nFinding key cards...")
    energy_accel = find_energy_accelerators(cards)
    prize_mechs = find_prize_mechanics(cards)

    # ── Print Summary ──
    print("\n" + "=" * 60)
    print("CARD POOL SUMMARY")
    print("=" * 60)
    print(f"Total: {stats['total_cards']}  |  Pokémon: {stats['pokemon_count']}")
    print(f"Basic: {stats['basic_count']}  |  Stage 1: {stats['stage1_count']}  |  Stage 2: {stats['stage2_count']}")
    print(f"Pokémon ex: {stats['ex_count']}  |  Mega ex: {stats['mega_ex_count']}")
    print(f"ACE SPEC: {stats['ace_spec_count']}  |  With Abilities: {stats['ability_count']}")
    print(f"HP range: {stats['hp']['min']}–{stats['hp']['max']} (avg {stats['hp']['avg']})")
    print(f"Damage range: {stats['damage']['min']}–{stats['damage']['max']} (avg {stats['damage']['avg']})")
    print(f"Energy cost range: {stats['energy_cost']['min']}–{stats['energy_cost']['max']} (avg {stats['energy_cost']['avg']})")

    print("\n" + "=" * 60)
    print("TOP 10 POKÉMON BY DAMAGE EFFICIENCY (dmg/energy × HP/prize)")
    print("=" * 60)
    for i, p in enumerate(rankings['by_efficiency'][:10], 1):
        print(f"  {i}. {p['name']} — Dmg:{p['damage']} Cost:{p['cost']} HP:{p['hp']} "
              f"Type:{p['type']} Eff:{p['efficiency']} Roles:{p['roles']}")

    print("\n" + "=" * 60)
    print("ARCHETYPE SUPPORT SUMMARY")
    print("=" * 60)
    for group in sorted(archetypes.keys(), key=lambda g: archetypes[g]['total_support'], reverse=True):
        a = archetypes[group]
        print(f"\n  {group} — {a['total_support']} cards ({a['pokemon_count']} Pokémon, {a['trainer_support_count']} trainers, {a['ex_count']} ex)")
        print(f"    Key Pokémon: {', '.join(a['key_pokemon'][:3])}")
        print(f"    Key Trainers: {', '.join(a['key_trainers'][:3])}")

    print(f"\n  Energy Acceleration cards: {len(energy_accel)}")
    print(f"  Prize manipulation cards: {len(prize_mechs)}")

    # ── Export ──
    result = {
        'statistics': stats,
        'archetypes': archetypes,
        'rankings': rankings,
        'energy_accelerators': energy_accel,
        'prize_mechanics': prize_mechs,
        'synergy_groups': {g: {'pokemon': [c.name for c in m['pokemon']],
                               'trainers': [c.name for c in m['trainers']]}
                          for g, m in synergy_map.items()},
    }

    if output_path:
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nAnalysis exported to {output_path}")

    return result


if __name__ == '__main__':
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else '/workspace/EN_Card_Data.csv'
    output_path = sys.argv[2] if len(sys.argv) > 2 else '/workspace/project/phase1_analysis.json'
    run_analysis(csv_path, output_path)
