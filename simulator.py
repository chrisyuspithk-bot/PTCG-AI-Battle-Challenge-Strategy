"""
Phase 2: Game Simulator Engine
Pokémon TCG AI Battle Challenge

Implements the core game loop: setup, turn structure, attack resolution,
KO/prize mechanics, win conditions. Two agents play head-to-head.
"""

import csv
import random
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
# Game Constants
# ═══════════════════════════════════════════════════════════════════════════════

MAX_BENCH = 5
PRIZE_CARDS = 6
STARTING_HAND = 7
MAX_COPIES = 4
DECK_SIZE = 60
MAX_HP = 9999      # cap for damage counter tracking


class Player(Enum):
    P1 = 0
    P2 = 1

    def opponent(self):
        return Player.P2 if self == Player.P1 else Player.P1


class GamePhase(Enum):
    SETUP = auto()
    DRAW = auto()
    ACTION = auto()
    ATTACK = auto()
    BETWEEN_TURNS = auto()
    GAME_OVER = auto()


# ═══════════════════════════════════════════════════════════════════════════════
# Card Model (lightweight for simulation)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SimCard:
    card_id: int
    name: str
    stage: str           # Basic Pokémon, Stage 1 Pokémon, etc.
    category: str        # Trainer's Pokémon, Ancient, Future, Tera, etc.
    rule: str            # Pokémon ex, ACE SPEC, Mega Pokémon ex
    hp: int
    pokemon_type: str
    weakness: str
    resistance: str
    retreat: int
    move_name: str
    move_cost: str
    move_damage: int
    move_effect: str
    previous_stage: str
    is_ex: bool = False
    is_mega_ex: bool = False
    prizes_given: int = 1
    has_ability: bool = False
    ability_text: str = ""

    # Derived from text
    can_draw: int = 0           # draw N cards on play/attack
    can_search: bool = False    # search deck for cards
    can_energy_accel: bool = False
    can_heal: int = 0           # heal amount
    can_switch_opponent: bool = False
    can_discard_energy: bool = False
    damage_modifier: int = 0    # bonus damage conditionally
    self_damage: int = 0        # recoil damage

    def __hash__(self):
        return hash(self.card_id)

    def __eq__(self, other):
        return isinstance(other, SimCard) and self.card_id == other.card_id


# ═══════════════════════════════════════════════════════════════════════════════
# In-Play Pokémon State
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class InPlayPokemon:
    card: SimCard
    damage_counters: int = 0
    attached_energy: dict = field(default_factory=lambda: defaultdict(int))
    attached_tool: Optional[SimCard] = None
    is_evolved: bool = False
    evolution_chain: list = field(default_factory=list)  # [basic, stage1, stage2]
    can_evolve_this_turn: bool = False
    turn_played: int = 0

    @property
    def current_hp(self) -> int:
        return max(0, self.card.hp - self.damage_counters * 10)

    @property
    def is_ko(self) -> bool:
        return self.current_hp <= 0

    @property
    def total_energy(self) -> int:
        return sum(self.attached_energy.values())

    def can_use_attack(self, attack_cost: str) -> bool:
        """Check if this Pokémon has enough energy to use the given attack."""
        if not attack_cost or attack_cost == 'n/a':
            return False
        needed_colorless = attack_cost.count('●')
        needed_specific = re.findall(r'\{([^}]+)\}', attack_cost)

        # Count available energy by type
        available = dict(self.attached_energy)
        available_colorless = sum(available.values())

        # Check specific requirements
        for spec in needed_specific:
            if available.get(spec, 0) > 0:
                available[spec] -= 1
                available_colorless -= 1
            else:
                return False

        return available_colorless >= needed_colorless


# ═══════════════════════════════════════════════════════════════════════════════
# Action Types
# ═══════════════════════════════════════════════════════════════════════════════

class ActionType(Enum):
    PLAY_BASIC = auto()       # Play basic Pokémon from hand to bench
    EVOLVE = auto()           # Evolve a Pokémon in play
    ATTACH_ENERGY = auto()    # Attach energy from hand
    PLAY_ITEM = auto()        # Play an item card
    PLAY_SUPPORTER = auto()   # Play a supporter card
    PLAY_STADIUM = auto()     # Play a stadium card
    PLAY_TOOL = auto()        # Attach a Pokémon tool
    ATTACK = auto()           # Attack with active Pokémon
    RETREAT = auto()          # Retreat active to bench
    USE_ABILITY = auto()      # Use a Pokémon ability
    PASS = auto()             # End action phase


@dataclass
class Action:
    type: ActionType
    card_index: int = -1          # Index of card in hand
    source_index: int = -1        # Bench index for evolve/retreat source
    target_index: int = -1        # Bench/active index for target
    energy_type: str = ""         # Energy type for attach
    attack_index: int = 0         # Which attack (0 = first, 1 = second)


# ═══════════════════════════════════════════════════════════════════════════════
# Game State
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GameState:
    # Card data
    all_cards: dict = field(default_factory=dict)  # card_id -> SimCard

    # Player states
    decks: dict = field(default_factory=lambda: {Player.P1: [], Player.P2: []})
    hands: dict = field(default_factory=lambda: {Player.P1: [], Player.P2: []})
    active: dict = field(default_factory=lambda: {Player.P1: None, Player.P2: None})
    benches: dict = field(default_factory=lambda: {Player.P1: [], Player.P2: []})
    prizes: dict = field(default_factory=lambda: {Player.P1: [], Player.P2: []})
    discard: dict = field(default_factory=lambda: {Player.P1: [], Player.P2: []})

    # Turn tracking
    current_player: Player = Player.P1
    turn_number: int = 0
    phase: GamePhase = GamePhase.SETUP
    first_turn: bool = True
    energy_attached_this_turn: bool = False
    supporter_played_this_turn: bool = False
    can_attack: bool = False   # Only player going second attacks turn 1

    # Game log
    log: list = field(default_factory=list)

    def copy(self):
        """Shallow copy for search/tree algorithms."""
        import copy
        return copy.deepcopy(self)

    def get_visible_state(self, player: Player) -> dict:
        """Return the game state visible to a given player (hidden info masked)."""
        opp = player.opponent()
        can_attack = (self.turn_number > 1 or player == Player.P2)
        return {
            'my_hand': [c.name for c in self.hands[player]],
            'my_hand_cards': self.hands[player],
            'my_active': self.active[player],
            'my_bench': self.benches[player],
            'my_prizes_remaining': len(self.prizes[player]),
            'my_discard': [c.name for c in self.discard[player]],
            'my_deck_size': len(self.decks[player]),
            'opp_active': self.active[opp],
            'opp_bench': self.benches[opp],
            'opp_hand_size': len(self.hands[opp]),
            'opp_prizes_remaining': len(self.prizes[opp]),
            'opp_discard': [c.name for c in self.discard[opp]],
            'opp_deck_size': len(self.decks[opp]),
            'turn_number': self.turn_number,
            'phase': self.phase,
            'current_player': self.current_player,
            'energy_attached': self.energy_attached_this_turn,
            'supporter_played': self.supporter_played_this_turn,
            'can_attack': can_attack,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Card Loader (reuses card_analyzer logic, simplified)
# ═══════════════════════════════════════════════════════════════════════════════

def safe_int(s: str) -> int:
    try: return int(s.strip())
    except (ValueError, AttributeError): return 0


def load_cards_sim(csv_path: str) -> dict:
    """Load all cards as lightweight SimCard objects."""
    cards = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stage = row['Stage (Pokémon)/Type (Energy and Trainer)'].strip()
            rule = row.get('Rule', '').strip()
            effect = row.get('Effect Explanation', '') or ''
            move_name = row.get('Move Name', '').strip()
            move_effect = effect  # The effect text often describes the move

            is_pokemon = 'Pokémon' in stage
            is_ex = rule in ('Pokémon ex', 'Mega Pokémon ex')
            hp = safe_int(row.get('HP', '0')) if is_pokemon else 0

            c = SimCard(
                card_id=safe_int(row['Card ID']),
                name=row['Card Name'].strip(),
                stage=stage,
                category=row.get('Category', '').strip(),
                rule=rule,
                hp=hp,
                pokemon_type=row.get('Type', '').strip(),
                weakness=row.get('Weakness', '').strip(),
                resistance=row.get('Resistance (Type)', '').strip(),
                retreat=safe_int(row.get('Retreat', '0')),
                move_name=move_name,
                move_cost=row.get('Cost', 'n/a'),
                move_damage=safe_int(row.get('Damage', '0')) if '×' not in (row.get('Damage', '') or '') else safe_int(re.sub(r'[×+].*', '', row.get('Damage', '')).strip()),
                move_effect=move_effect,
                previous_stage=row.get('Previous stage', '').strip(),
                is_ex=is_ex,
                is_mega_ex=(rule == 'Mega Pokémon ex'),
                prizes_given=2 if is_ex else 1,
                has_ability=('[Ability]' in (effect + move_name)),
                ability_text=effect if '[Ability]' in (effect + move_name) else '',
            )

            # Parse effects for simulator
            eff_lower = (effect + move_name).lower()
            if 'draw' in eff_lower and 'card' in eff_lower:
                m = re.search(r'draw\s+(\d+)\s+card', eff_lower)
                if m:
                    c.can_draw = int(m.group(1))
                elif 'draw cards until' in eff_lower:
                    c.can_draw = -1  # special: draw until count
                elif 'draw a card' in eff_lower:
                    c.can_draw = 1
            if 'search your deck' in eff_lower:
                c.can_search = True
            if any(p in eff_lower for p in ['attach', 'energy']) and 'opponent' not in eff_lower:
                c.can_energy_accel = True
            if 'heal' in eff_lower:
                m = re.search(r'heal\s+(\d+)', eff_lower)
                if m:
                    c.can_heal = int(m.group(1))
            if 'switch in 1 of your opponent' in eff_lower:
                c.can_switch_opponent = True
            if 'discard' in eff_lower and 'energy' in eff_lower:
                c.can_discard_energy = True

            cards[c.card_id] = c
    return cards


# ═══════════════════════════════════════════════════════════════════════════════
# Deck Builder
# ═══════════════════════════════════════════════════════════════════════════════

def validate_deck(deck: list[SimCard]) -> list[str]:
    """Validate a decklist. Returns list of error messages (empty = valid)."""
    errors = []
    if len(deck) != DECK_SIZE:
        errors.append(f"Deck must have {DECK_SIZE} cards, got {len(deck)}")

    counts = defaultdict(int)
    ace_spec_count = 0
    has_basic = False

    for c in deck:
        if c.is_ex and c.is_mega_ex:
            pass  # Mega Pokémon are Pokémon
        if c.rule == 'ACE SPEC':
            ace_spec_count += 1
        if 'Basic' in c.stage and 'Pokémon' in c.stage:
            has_basic = True

    if not has_basic:
        errors.append("Deck must contain at least 1 Basic Pokémon")
    if ace_spec_count > 1:
        errors.append(f"Deck can have at most 1 ACE SPEC card, got {ace_spec_count}")

    return errors


def build_deck_from_names(card_pool: dict, name_counts: dict) -> list[SimCard]:
    """Build a deck from a dict of {card_name: count}."""
    name_to_ids = defaultdict(list)
    for cid, card in card_pool.items():
        name_to_ids[card.name].append(cid)

    deck = []
    for name, count in name_counts.items():
        ids = name_to_ids.get(name, [])
        if not ids:
            raise ValueError(f"Card not found: {name}")
        for i in range(min(count, len(ids))):
            deck.append(card_pool[ids[i]])

    return deck


# ═══════════════════════════════════════════════════════════════════════════════
# Game Simulator
# ═══════════════════════════════════════════════════════════════════════════════

class GameSimulator:
    """Core Pokémon TCG game engine."""

    def __init__(self, card_pool: dict, deck_a: list[SimCard], deck_b: list[SimCard],
                 agent_a: Callable = None, agent_b: Callable = None,
                 seed: int = None, verbose: bool = False):
        self.card_pool = card_pool
        self.deck_a = list(deck_a)
        self.deck_b = list(deck_b)
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.verbose = verbose
        if seed is not None:
            random.seed(seed)

        self.state = GameState(all_cards=card_pool)

    # ── Setup ────────────────────────────────────────────────────────────

    def setup(self) -> GameState:
        """Initialize the game: shuffle decks, draw hands, place basics, set prizes."""
        s = self.state

        # Shuffle and deal
        s.decks[Player.P1] = list(self.deck_a)
        s.decks[Player.P2] = list(self.deck_b)
        random.shuffle(s.decks[Player.P1])
        random.shuffle(s.decks[Player.P2])

        # Mulligan handling
        for player in (Player.P1, Player.P2):
            while True:
                s.hands[player] = s.decks[player][:STARTING_HAND]
                s.decks[player] = s.decks[player][STARTING_HAND:]
                basics = [c for c in s.hands[player] if 'Basic' in c.stage and 'Pokémon' in c.stage]
                if basics:
                    break
                # Mulligan: reshuffle and redraw
                self._log(f"{player.name} mulligans (no Basic Pokémon)")
                s.decks[player].extend(s.hands[player])
                random.shuffle(s.decks[player])
                s.hands[player] = []

        # Place Active + Bench (agent decides or auto)
        for player in (Player.P1, Player.P2):
            basics = [c for c in s.hands[player] if 'Basic' in c.stage and 'Pokémon' in c.stage]
            # Place first basic as active
            active_card = basics[0]
            s.hands[player].remove(active_card)
            s.active[player] = InPlayPokemon(card=active_card, turn_played=0)
            basics.remove(active_card)
            self._log(f"{player.name} places {active_card.name} as Active")

            # Place up to 5 more on bench
            for bench_card in basics[:MAX_BENCH]:
                s.hands[player].remove(bench_card)
                s.benches[player].append(InPlayPokemon(card=bench_card, turn_played=0))
                self._log(f"{player.name} benches {bench_card.name}")

        # Set prize cards
        for player in (Player.P1, Player.P2):
            s.prizes[player] = s.decks[player][:PRIZE_CARDS]
            s.decks[player] = s.decks[player][PRIZE_CARDS:]

        # Random first player
        s.current_player = random.choice([Player.P1, Player.P2])
        s.first_turn = True
        s.can_attack = (s.current_player == Player.P2)  # P2 can attack on first turn
        s.phase = GamePhase.DRAW
        s.turn_number = 1

        self._log(f"{s.current_player.name} goes first")
        return s

    # ── Turn Loop ────────────────────────────────────────────────────────

    def run_game(self) -> tuple[Optional[Player], GameState]:
        """Run a full game. Returns (winner, final_state)."""
        self.setup()
        s = self.state

        while s.phase != GamePhase.GAME_OVER:
            if s.phase == GamePhase.DRAW:
                self._do_draw_phase()
            elif s.phase == GamePhase.ACTION:
                self._do_action_phase()
            elif s.phase == GamePhase.ATTACK:
                self._do_attack_phase()
            elif s.phase == GamePhase.BETWEEN_TURNS:
                self._do_between_turns()
                if s.phase == GamePhase.GAME_OVER:
                    break
                self._end_turn()

        winner = self._check_winner()
        self._log(f"Game over! Winner: {winner.name if winner else 'Draw'}")
        return winner, s

    def _do_draw_phase(self):
        s = self.state
        player = s.current_player

        # Draw for turn (skip on first turn for player going first)
        if not (s.turn_number == 1 and s.first_turn):
            if s.decks[player]:
                drawn = s.decks[player].pop(0)
                s.hands[player].append(drawn)
                self._log(f"{player.name} draws {drawn.name}")
            else:
                self._log(f"{player.name} has no cards to draw — loses!")
                s.phase = GamePhase.GAME_OVER
                return

        s.energy_attached_this_turn = False
        s.supporter_played_this_turn = False
        s.phase = GamePhase.ACTION

    def _do_action_phase(self):
        """Let the agent choose actions until it attacks or passes."""
        s = self.state
        player = s.current_player
        max_actions = 50
        consecutive_failures = 0

        for _ in range(max_actions):
            can_attack_now = s.turn_number > 1 or player == Player.P2

            agent = self.agent_a if player == Player.P1 else self.agent_b
            if agent is None:
                action = self._simple_heuristic_action(player, can_attack_now)
            else:
                visible = s.get_visible_state(player)
                action = agent(visible)

            if action is None or action.type == ActionType.PASS:
                if can_attack_now and s.active[player] is not None:
                    s.phase = GamePhase.ATTACK
                else:
                    s.phase = GamePhase.BETWEEN_TURNS
                return

            if action.type == ActionType.ATTACK:
                if can_attack_now:
                    s.phase = GamePhase.ATTACK
                    return
                continue

            if self._execute_action(player, action):
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    if can_attack_now and s.active[player] is not None:
                        s.phase = GamePhase.ATTACK
                    else:
                        s.phase = GamePhase.BETWEEN_TURNS
                    return

        # Fallback
        if s.turn_number > 1 and s.active[player] is not None:
            s.phase = GamePhase.ATTACK
        else:
            s.phase = GamePhase.BETWEEN_TURNS

    def _execute_action(self, player: Player, action: Action) -> bool:
        """Execute an action. Returns True if action was performed, False if invalid."""
        s = self.state
        hand = s.hands[player]

        if action.type == ActionType.PLAY_BASIC:
            if 0 <= action.card_index < len(hand):
                card = hand[action.card_index]
                if 'Basic' in card.stage and 'Pokémon' in card.stage:
                    if len(s.benches[player]) < MAX_BENCH:
                        hand.pop(action.card_index)
                        s.benches[player].append(InPlayPokemon(card=card, turn_played=s.turn_number))
                        self._log(f"{player.name} plays {card.name} to bench")
                        return True
            return False

        elif action.type == ActionType.EVOLVE:
            if 0 <= action.card_index < len(hand):
                evo_card = hand[action.card_index]
                target = None
                if action.target_index == -1:
                    target = s.active[player]
                elif 0 <= action.target_index < len(s.benches[player]):
                    target = s.benches[player][action.target_index]

                if target and self._can_evolve(target, evo_card, s.turn_number):
                    hand.pop(action.card_index)
                    target.evolution_chain.append(target.card)
                    target.card = evo_card
                    target.is_evolved = True
                    target.turn_played = s.turn_number
                    self._log(f"{player.name} evolves to {evo_card.name}")
                    self._resolve_on_play_effects(target)
                    return True
            return False

        elif action.type == ActionType.ATTACH_ENERGY:
            if not s.energy_attached_this_turn:
                energy_idx = self._find_energy_in_hand(hand)
                if energy_idx >= 0:
                    target = None
                    if action.target_index == -1:
                        target = s.active[player]
                    elif 0 <= action.target_index < len(s.benches[player]):
                        target = s.benches[player][action.target_index]

                    if target:
                        energy_card = hand.pop(energy_idx)
                        energy_type = energy_card.pokemon_type or '{C}'
                        target.attached_energy[energy_type] += 1
                        s.energy_attached_this_turn = True
                        self._log(f"{player.name} attaches {energy_card.name} to {target.card.name}")
                        return True
            return False

        elif action.type == ActionType.RETREAT:
            active = s.active[player]
            if active and active.total_energy >= active.card.retreat:
                if 0 <= action.target_index < len(s.benches[player]):
                    self._discard_energy_for_retreat(active)
                    s.benches[player].append(active)
                    s.active[player] = s.benches[player].pop(action.target_index)
                    self._log(f"{player.name} retreats to {s.active[player].card.name}")
                    return True
            return False

        elif action.type == ActionType.ATTACK:
            return True  # Handled in _do_attack_phase

        return False

    def _can_evolve(self, target: InPlayPokemon, evo_card: SimCard, turn: int) -> bool:
        """Check if target can evolve into evo_card."""
        if target.turn_played >= turn:  # Can't evolve same turn played
            return False
        if evo_card.previous_stage and evo_card.previous_stage.lower() == target.card.name.lower():
            return True
        # Check if any card in evolution chain matches
        for prev in target.evolution_chain:
            if evo_card.previous_stage and evo_card.previous_stage.lower() == prev.name.lower():
                return True
        return False

    def _find_energy_in_hand(self, hand: list) -> int:
        for i, c in enumerate(hand):
            if 'Energy' in c.stage:
                return i
        return -1

    def _discard_energy_for_retreat(self, pokemon: InPlayPokemon):
        cost = pokemon.card.retreat
        types = list(pokemon.attached_energy.keys())
        for t in types:
            while cost > 0 and pokemon.attached_energy[t] > 0:
                pokemon.attached_energy[t] -= 1
                cost -= 1
            if pokemon.attached_energy[t] <= 0:
                del pokemon.attached_energy[t]
            if cost == 0:
                break

    def _resolve_on_play_effects(self, pokemon: InPlayPokemon):
        """Resolve simple on-play effects (draw, etc.)."""
        card = pokemon.card
        if card.can_draw > 0:
            player = self.state.current_player
            for _ in range(card.can_draw):
                if self.state.decks[player]:
                    self.state.hands[player].append(self.state.decks[player].pop(0))

    # ── Attack Phase ─────────────────────────────────────────────────────

    def _do_attack_phase(self):
        s = self.state
        player = s.current_player
        opp = player.opponent()
        attacker = s.active[player]
        defender = s.active[opp]

        if attacker is None:
            s.phase = GamePhase.BETWEEN_TURNS
            return

        # Agent chooses which attack to use
        agent = self.agent_a if player == Player.P1 else self.agent_b
        attack_idx = 0
        if agent:
            visible = s.get_visible_state(player)
            attack_action = agent(visible)
            if attack_action and attack_action.type == ActionType.ATTACK:
                attack_idx = attack_action.attack_index

        damage = attacker.card.move_damage

        if defender and damage > 0:
            # Apply weakness (×2)
            if attacker.card.pokemon_type == defender.card.weakness:
                damage *= 2
                self._log(f"Weakness! {attacker.card.pokemon_type} → {defender.card.weakness}")

            # Apply resistance (-20)
            if attacker.card.pokemon_type == defender.card.resistance:
                damage = max(0, damage - 20)
                self._log(f"Resistance! -20 damage")

            # Apply damage
            defender.damage_counters += damage // 10
            self._log(f"{player.name}'s {attacker.card.name} attacks for {damage} damage "
                      f"→ {defender.card.name} ({defender.current_hp} HP remaining)")

            # Check KO
            if defender.is_ko:
                self._handle_ko(opp, defender)

        s.phase = GamePhase.BETWEEN_TURNS

    def _handle_ko(self, player: Player, pokemon: InPlayPokemon):
        """Handle a Pokémon being Knocked Out."""
        s = self.state
        opponent = player.opponent()
        prizes_to_take = pokemon.card.prizes_given

        self._log(f"{pokemon.card.name} is Knocked Out!")

        # Discard the KO'd Pokémon and its attachments
        if s.active[player] == pokemon:
            s.active[player] = None
        elif pokemon in s.benches[player]:
            s.benches[player].remove(pokemon)

        # Take prize cards
        for _ in range(prizes_to_take):
            if s.prizes[opponent]:
                prize = s.prizes[opponent].pop()
                s.hands[opponent].append(prize)
                self._log(f"{opponent.name} takes a prize: {prize.name}")

        # Promote new active if needed
        if s.active[player] is None:
            if s.benches[player]:
                s.active[player] = s.benches[player].pop(0)
                self._log(f"{player.name} promotes {s.active[player].card.name} to Active")
            else:
                self._log(f"{player.name} has no Pokémon left!")
                s.phase = GamePhase.GAME_OVER

    # ── Between Turns ────────────────────────────────────────────────────

    def _do_between_turns(self):
        s = self.state
        # Check KOs from special conditions (Poison, Burn)
        for player in (Player.P1, Player.P2):
            active = s.active[player]
            if active and active.is_ko:
                self._handle_ko(player, active)

        if s.phase == GamePhase.GAME_OVER:
            return

        # Check win conditions
        winner = self._check_winner()
        if winner:
            s.phase = GamePhase.GAME_OVER

    def _check_winner(self) -> Optional[Player]:
        s = self.state
        for player in (Player.P1, Player.P2):
            opp = player.opponent()
            # No prizes left
            if len(s.prizes[player]) == 0:
                return player
            # Opponent has no Pokémon in play
            if s.active[opp] is None and len(s.benches[opp]) == 0:
                return player
            # Opponent decked out (can't draw)
            if len(s.decks[opp]) == 0:
                return player
        return None

    # ── End Turn ─────────────────────────────────────────────────────────

    def _end_turn(self):
        s = self.state
        s.current_player = s.current_player.opponent()
        s.turn_number += 1
        s.first_turn = False
        s.can_attack = True
        s.phase = GamePhase.DRAW
        self._log(f"\n--- Turn {s.turn_number}: {s.current_player.name} ---")

    # ── Simple Heuristic Agent (used when no agent provided) ─────────────

    def _simple_heuristic_action(self, player: Player, can_attack: bool) -> Optional[Action]:
        """Basic priority heuristic for automated testing."""
        s = self.state
        hand = s.hands[player]
        active = s.active[player]
        opp_active = s.active[player.opponent()]

        # 1. Can we KO opponent's active? Attack!
        if can_attack and active and opp_active:
            if active.can_use_attack(active.card.move_cost) and active.card.move_damage > 0:
                return Action(type=ActionType.ATTACK, attack_index=0)

        # 2. Play basics to bench (only if bench has space)
        if len(s.benches[player]) < MAX_BENCH:
            for i, c in enumerate(hand):
                if 'Basic' in c.stage and 'Pokémon' in c.stage:
                    return Action(type=ActionType.PLAY_BASIC, card_index=i)

        # 3. Evolve active first, then bench
        for i, c in enumerate(hand):
            if 'Stage 1' in c.stage or 'Stage 2' in c.stage:
                if active and self._can_evolve(active, c, s.turn_number):
                    return Action(type=ActionType.EVOLVE, card_index=i, target_index=-1)
                for j, bench in enumerate(s.benches[player]):
                    if self._can_evolve(bench, c, s.turn_number):
                        return Action(type=ActionType.EVOLVE, card_index=i, target_index=j)

        # 4. Attach energy (only if not done this turn)
        if not s.energy_attached_this_turn and active:
            for i, c in enumerate(hand):
                if 'Energy' in c.stage:
                    return Action(type=ActionType.ATTACH_ENERGY, card_index=i, target_index=-1)

        # 5. Attack if possible
        if can_attack and active and opp_active:
            if active.can_use_attack(active.card.move_cost) and active.card.move_damage > 0:
                return Action(type=ActionType.ATTACK, attack_index=0)

        # 6. Retreat if active is critically low and bench has options
        if active and active.current_hp <= active.card.hp * 0.3 and s.benches[player]:
            if active.total_energy >= active.card.retreat:
                return Action(type=ActionType.RETREAT, target_index=0)

        # 7. If we can't attack and have nothing to do, pass
        if can_attack and active and opp_active:
            if active.can_use_attack(active.card.move_cost):
                return Action(type=ActionType.ATTACK, attack_index=0)
        return Action(type=ActionType.PASS)

    # ── Logging ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        if self.verbose:
            print(f"  {msg}")
        self.state.log.append(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# Tournament / Batch Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_match(cards: dict, deck_a: list, deck_b: list,
              agent_a=None, agent_b=None, seed: int = None, verbose: bool = False) -> dict:
    """Run a single match and return results. Accepts pre-loaded card pool."""
    sim = GameSimulator(cards, deck_a, deck_b, agent_a, agent_b, seed=seed, verbose=verbose)
    winner, state = sim.run_game()

    return {
        'winner': winner.name if winner else 'Draw',
        'turns': state.turn_number,
        'p1_prizes_taken': 6 - len(state.prizes[Player.P1]),
        'p2_prizes_taken': 6 - len(state.prizes[Player.P2]),
        'log': state.log,
    }


def run_tournament(card_pool_path: str, deck_a: list, deck_b: list,
                   agent_a=None, agent_b=None, num_games: int = 100,
                   seed: int = 42) -> dict:
    """Run multiple matches and aggregate results."""
    cards = load_cards_sim(card_pool_path)
    results = {'P1': 0, 'P2': 0, 'Draw': 0, 'games': []}
    random.seed(seed)

    for i in range(num_games):
        game_seed = random.randint(0, 2**31 - 1)
        result = run_match(cards, deck_a, deck_b, agent_a, agent_b, seed=game_seed)
        results[result['winner']] += 1
        results['games'].append({
            'game': i + 1,
            'winner': result['winner'],
            'turns': result['turns'],
        })

    total = num_games
    results['win_rate_a'] = results['P1'] / total * 100
    results['win_rate_b'] = results['P2'] / total * 100
    results['draw_rate'] = results['Draw'] / total * 100

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Demo / Test
# ═══════════════════════════════════════════════════════════════════════════════

def create_test_deck(card_pool: dict, pokemon_names: list[str], energy_types: list[str],
                     trainer_names: list[str] = None) -> list[SimCard]:
    """Create a simple 60-card test deck."""
    name_to_ids = defaultdict(list)
    for cid, card in card_pool.items():
        name_to_ids[card.name].append(cid)

    deck = []

    # Add specified Pokémon (4 copies each)
    for name in pokemon_names:
        ids = name_to_ids.get(name, [])
        for i in range(min(4, len(ids))):
            deck.append(card_pool[ids[i]])

    # Add trainers if specified
    if trainer_names:
        for name in trainer_names:
            ids = name_to_ids.get(name, [])
            for i in range(min(4, len(ids))):
                deck.append(card_pool[ids[i]])

    # Fill remaining with Basic Energy
    energy_remaining = DECK_SIZE - len(deck)
    for et in energy_types:
        ids = name_to_ids.get(et, [])
        if ids:
            deck.append(card_pool[ids[0]])

    # Pad with more energy if needed
    while len(deck) < DECK_SIZE:
        et = energy_types[0]
        ids = name_to_ids.get(et, [])
        if ids:
            deck.append(card_pool[ids[0]])
        else:
            break

    return deck[:DECK_SIZE]


if __name__ == '__main__':
    import sys

    csv_path = sys.argv[1] if len(sys.argv) > 1 else '/workspace/EN_Card_Data.csv'
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print("Loading card pool...")
    cards = load_cards_sim(csv_path)
    print(f"Loaded {len(cards)} cards")

    # Build two simple test decks using common Pokémon
    # Deck A: Fire-themed aggro
    deck_a = create_test_deck(cards, [
        'Charmander', 'Charmeleon', 'Charizard ex',
        'Growlithe', 'Arcanine ex', 'Ponyta', 'Rapidash',
    ], ['Basic {R} Energy'], ['Ultra Ball', "Boss's Orders"])

    # Deck B: Water-themed
    deck_b = create_test_deck(cards, [
        'Squirtle', 'Wartortle', 'Blastoise ex',
        'Magikarp', 'Gyarados', 'Lapras',
    ], ['Basic {W} Energy'], ['Ultra Ball', "Boss's Orders"])

    print(f"Deck A: {len(deck_a)} cards")
    print(f"Deck B: {len(deck_b)} cards")

    print(f"\nRunning {num_games} games...")
    results = run_tournament(csv_path, deck_a, deck_b, num_games=num_games)

    print(f"\nResults ({num_games} games):")
    print(f"  Deck A (Fire): {results['win_rate_a']:.1f}%")
    print(f"  Deck B (Water): {results['win_rate_b']:.1f}%")
    print(f"  Draws: {results['draw_rate']:.1f}%")

    # Show a sample game log
    if results['games']:
        sample = run_match(cards, deck_a, deck_b, seed=42, verbose=True)
