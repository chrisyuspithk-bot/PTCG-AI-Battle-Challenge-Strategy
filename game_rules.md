# Pokémon TCG Game Mechanics Reference

Codified rules for the simulator engine (Phase 2). Based on the Pokémon TCG
Standard format with the card pool defined in EN_Card_Data.csv.

---

## Deck Construction

- **60 cards** exactly
- Maximum **4 copies** of any card with the same name (except Basic Energy)
- Maximum **1 ACE SPEC** card per deck
- At least **1 Basic Pokémon** (or you auto-lose at setup)

---

## Game Setup

1. Both players shuffle their decks
2. Draw 7 cards each
3. Place 1 Basic Pokémon face-down as Active Pokémon
4. Place up to 5 additional Basic Pokémon face-down on Bench
5. Set aside top 6 cards as Prize Cards (face-down)
6. If a player has no Basic Pokémon in opening hand: reveal hand, shuffle back,
   draw 7 again. Opponent may optionally draw 1 extra card per mulligan.
7. Flip a coin to decide who goes first

---

## Turn Structure

### 1. Draw Phase
- Draw 1 card from deck
- **First turn of the game (player going first): skip this draw**

### 2. Action Phase (any order, any number of times unless restricted)
- **Attach 1 Energy** from hand to 1 Pokémon (once per turn)
- **Play Basic Pokémon** from hand onto Bench
- **Evolve Pokémon** (once per Pokémon per turn; cannot evolve on first turn
  or on the turn a Pokémon was played)
- **Play Trainer cards**: Items (any number), Supporters (1 per turn),
  Stadiums (1 in play at a time), Pokémon Tools (1 per Pokémon)
- **Use Abilities** (as specified on card)

### 3. Attack Phase
- Declare 1 attack with Active Pokémon (ends your turn)
- Must have required Energy attached
- Apply damage, effects

### 4. Between-Turns (Pokémon Checkup)
- Check for KO'd Pokémon (damage counters ≥ HP)
- Resolve Special Conditions (Poison, Burn, Sleep, Paralysis, Confusion)
- Check win conditions

---

## Win Conditions

1. **Take all 6 Prize Cards** — each time you KO an opponent's Pokémon:
   - 1 Prize for regular Pokémon
   - 2 Prizes for Pokémon ex / Mega Pokémon ex
2. **Opponent has no Pokémon in play** (Active + Bench empty)
3. **Opponent cannot draw at start of turn** (deck empty)

---

## Damage & KO Mechanics

- Damage counters (1 counter = 10 damage) are placed on Pokémon
- Damage persists between turns (not healed automatically)
- Weakness: ×2 damage from matching type
- Resistance: -20 damage from matching type (where applicable)
- A Pokémon is Knocked Out when damage counters ≥ its HP

---

## Special Conditions

| Condition | Effect |
|---|---|
| **Asleep** | Cannot attack or retreat. Flip coin between turns: heads = cured. |
| **Burned** | Place 2 damage counters between turns. Flip coin: heads = cured. |
| **Confused** | Flip coin before attacking: tails = 30 damage to self. |
| **Paralyzed** | Cannot attack or retreat. Cured at end of next turn. |
| **Poisoned** | Place 1 damage counter between turns. |

---

## Card Type Reference

| Symbol | Type |
|---|---|
| `{G}` | Grass |
| `{R}` | Fire |
| `{W}` | Water |
| `{L}` | Lightning |
| `{P}` | Psychic |
| `{F}` | Fighting |
| `{D}` | Darkness |
| `{M}` | Metal |
| `{C}` | Colorless |
| `{A}` | Any/Prism |
| `●` | Colorless energy cost |

---

## Key Rule Categories

- **Pokémon ex**: Give 2 Prize Cards when KO'd. Have Rule Boxes.
- **Mega Pokémon ex**: Evolve from Pokémon ex. End turn when played (unless
  Spirit Link attached). Give 2 Prize Cards.
- **ACE SPEC**: Limit 1 per deck. Powerful effects.
- **Tera Pokémon**: While on Bench, prevent all damage from attacks.
- **Ancient / Future**: Archetype tags enabling specific support cards.
- **Trainer's Pokémon**: Tagged with specific trainer name. Dedicated support
  cards only work with matching trainer.

---

## Supporter Rule

- Only 1 Supporter card may be played per turn
- Cannot play a Supporter on the first turn (by the player going first)
