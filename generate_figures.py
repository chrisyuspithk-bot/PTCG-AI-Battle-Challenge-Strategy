"""
Phase 6: Generate figures for Kaggle Strategy Writeup.
Outputs PNG charts to /workspace/project/figures/
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

os.makedirs('/workspace/project/figures', exist_ok=True)

# Style
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.dpi': 150,
})

COLORS = {'rocket': '#C62828', 'aggro': '#F57C00', 'evo': '#1565C0',
          'p1': '#78909C', 'p2': '#FF6F00', 'ex': '#C62828', 'sp': '#2E7D32'}

# ═══════════════════════════════════════════════════════════════════════════════
# Figure 1: P2 Advantage by Archetype
# ═══════════════════════════════════════════════════════════════════════════════

def figure_turn_order():
    archetypes = ['Team Rocket\nControl', 'Aggro\nBasics', 'Evolution\nPower']
    p1_rates = [30, 30, 63]
    p2_rates = [70, 70, 37]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(archetypes))
    w = 0.35

    ax.bar(x - w/2, p1_rates, w, label='P1 (Goes First)', color=COLORS['p1'])
    ax.bar(x + w/2, p2_rates, w, label='P2 (Goes Second)', color=COLORS['p2'])

    ax.set_ylabel('Win Rate (%)')
    ax.set_title('Figure 1: Turn-Order Advantage by Archetype\n(P2 wins 70% with fast decks, but only 37% with evolution)')
    ax.set_xticks(x)
    ax.set_xticklabels(archetypes)
    ax.set_ylim(0, 85)
    ax.legend(loc='upper right')
    ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='Fair coin')

    for i, (p1, p2) in enumerate(zip(p1_rates, p2_rates)):
        ax.text(i - w/2, p1 + 1, f'{p1}%', ha='center', fontsize=10, fontweight='bold')
        ax.text(i + w/2, p2 + 1, f'{p2}%', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig('/workspace/project/figures/fig1_turn_order.png')
    plt.close()
    print("Figure 1 saved")


# ═══════════════════════════════════════════════════════════════════════════════
# Figure 2: Prize Trade — Ex vs Single-Prize
# ═══════════════════════════════════════════════════════════════════════════════

def figure_prize_trade():
    categories = ['Single-Prize\nAttackers', 'Multi-Prize\nEx Attackers']
    win_rates = [17, 83]
    colors = [COLORS['sp'], COLORS['ex']]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(categories, win_rates, color=colors, width=0.5)

    ax.set_ylabel('Win Rate (%)')
    ax.set_title('Figure 2: Prize Trade Efficiency\n(Hypothesis: Single-prize would trade favorably. Reality: Ex dominate)')
    ax.set_ylim(0, 100)

    for bar, rate in zip(bars, win_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{rate}%', ha='center', fontsize=14, fontweight='bold')

    ax.annotate('Reversed hypothesis', xy=(0.5, 50), fontsize=11,
                ha='center', color='red', style='italic',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFEBEE', alpha=0.8))

    plt.tight_layout()
    plt.savefig('/workspace/project/figures/fig2_prize_trade.png')
    plt.close()
    print("Figure 2 saved")


# ═══════════════════════════════════════════════════════════════════════════════
# Figure 3: Cross-Archetype Matchup Matrix
# ═══════════════════════════════════════════════════════════════════════════════

def figure_matchup_matrix():
    names = ['Team Rocket', 'Aggro Basics', 'Evolution']
    matrix = np.array([
        [50, 52, 100],
        [48, 50, 94],
        [0,   6, 50],
    ])

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, cmap='RdYlGn', vmin=0, vmax=100)

    ax.set_xticks(np.arange(3))
    ax.set_yticks(np.arange(3))
    ax.set_xticklabels(names)
    ax.set_yticklabels(names)
    ax.set_title('Figure 3: Archetype Matchup Matrix\n(Row = Player, Col = Opponent. Values = Row win %)')

    for i in range(3):
        for j in range(3):
            color = 'white' if matrix[i, j] > 80 or matrix[i, j] < 20 else 'black'
            text = f'{matrix[i, j]:.0f}%'
            if i == j:
                text = '—'
                color = 'gray'
            ax.text(j, i, text, ha='center', va='center', fontsize=13,
                    fontweight='bold', color=color)

    ax.set_xlabel('Opponent Deck')
    ax.set_ylabel('Your Deck')
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Win Rate (%)')

    plt.tight_layout()
    plt.savefig('/workspace/project/figures/fig3_matchup_matrix.png')
    plt.close()
    print("Figure 3 saved")


# ═══════════════════════════════════════════════════════════════════════════════
# Figure 4: Deck Iteration — Incremental Improvement
# ═══════════════════════════════════════════════════════════════════════════════

def figure_deck_iteration():
    steps = ['Mewtwo ex\n(4x)', '+Kangaskhan\nex (4x)',
             '+Bench\nbasics (8x)', '+Trainers\n(8x)']
    win_rates = [63, 67, 57, 57]
    colors_bar = ['#C62828', '#E53935', '#EF9A9A', '#FFCDD2']

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(steps, win_rates, color=colors_bar, width=0.5)

    for bar, rate in zip(bars, win_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{rate}%', ha='center', fontsize=13, fontweight='bold')

    # Draw connecting line to show non-linear relationship
    x_vals = np.arange(len(steps))
    ax.plot(x_vals, win_rates, 'o-', color='#333', linewidth=2, markersize=8, zorder=5)

    ax.set_ylabel('Win Rate vs Aggro (%)')
    ax.set_title('Figure 4: Deck Iteration — Non-Linear Returns\n(Adding cards can reduce win rate)')
    ax.set_ylim(40, 75)
    ax.axhline(y=50, color='gray', linestyle='--', alpha=0.4)

    ax.annotate('Diminishing\nreturns', xy=(2, 57), fontsize=9, color='#C62828',
                ha='center', style='italic')

    plt.tight_layout()
    plt.savefig('/workspace/project/figures/fig4_deck_iteration.png')
    plt.close()
    print("Figure 4 saved")


# ═══════════════════════════════════════════════════════════════════════════════
# Figure 5: Attacker Efficiency
# ═══════════════════════════════════════════════════════════════════════════════

def figure_attacker_efficiency():
    names = ['Mewtwo ex\n(280HP/160dmg)', 'Kangaskhan ex\n(230HP/120dmg)',
             'Articuno\n(120HP/60dmg)']
    win_rates = [63, 50, 13]
    hps = [280, 230, 120]

    fig, ax1 = plt.subplots(figsize=(9, 5))

    bars = ax1.bar(names, win_rates, color=COLORS['rocket'], width=0.4, alpha=0.8)
    ax1.set_ylabel('Win Rate (%)', color=COLORS['rocket'])
    ax1.set_ylim(0, 80)
    ax1.tick_params(axis='y', labelcolor=COLORS['rocket'])

    for bar, rate in zip(bars, win_rates):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{rate}%', ha='center', fontsize=12, fontweight='bold')

    ax2 = ax1.twinx()
    ax2.plot(names, hps, 'o-', color='#1565C0', linewidth=3, markersize=10)
    ax2.set_ylabel('HP', color='#1565C0')
    ax2.set_ylim(0, 350)
    ax2.tick_params(axis='y', labelcolor='#1565C0')

    for i, hp in enumerate(hps):
        ax2.text(i, hp + 10, f'{hp} HP', ha='center', fontsize=9, color='#1565C0')

    ax1.set_title('Figure 5: Attacker Quality → Win Rate\n(HP and damage are the dominant factors)')

    # Legend
    p1 = mpatches.Patch(color=COLORS['rocket'], label='Win Rate')
    p2 = mpatches.Patch(color='#1565C0', label='HP')
    ax1.legend(handles=[p1, p2], loc='upper right')

    plt.tight_layout()
    plt.savefig('/workspace/project/figures/fig5_attacker.png')
    plt.close()
    print("Figure 5 saved")


# ═══════════════════════════════════════════════════════════════════════════════
# Figure 6: Energy Ratio Impact
# ═══════════════════════════════════════════════════════════════════════════════

def figure_energy_ratio():
    ratios = ['16 energy\n(27%)', '16 energy\n(27%)', '24 energy\n(40%)']
    win_rates = [53, 53, 40]
    colors_bar = ['#2E7D32', '#388E3C', '#A5D6A7']

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(ratios, win_rates, color=colors_bar, width=0.5)

    for bar, rate in zip(bars, win_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{rate}%', ha='center', fontsize=13, fontweight='bold')

    ax.set_ylabel('Win Rate vs Aggro (%)')
    ax.set_title('Figure 6: Energy Ratio Impact\n(Oversaturating with energy reduces win rate by 13%)')
    ax.set_ylim(30, 65)
    ax.axhline(y=50, color='gray', linestyle='--', alpha=0.4)

    # Arrow showing decline
    ax.annotate('', xy=(2, 40), xytext=(0.5, 53),
                arrowprops=dict(arrowstyle='->', color='red', lw=2))
    ax.text(1.2, 46, '-13%', fontsize=12, color='red', fontweight='bold')

    plt.tight_layout()
    plt.savefig('/workspace/project/figures/fig6_energy_ratio.png')
    plt.close()
    print("Figure 6 saved")


if __name__ == '__main__':
    figure_turn_order()
    figure_prize_trade()
    figure_matchup_matrix()
    figure_deck_iteration()
    figure_attacker_efficiency()
    figure_energy_ratio()
    print("\nAll 6 figures saved to /workspace/project/figures/")
