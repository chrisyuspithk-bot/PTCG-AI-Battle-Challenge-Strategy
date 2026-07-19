"""PTCG AI Battle - Mega Lucario ex v2 (SMARTER PRIORITIES)
Engine: cabt - Bench-aware: finds strongest attacker, retreats weak actives."""

import os, sys, traceback
from typing import Optional

_CALL = 0
_DECK: Optional[list[int]] = None

# OptionType enum (int)
PLAY,ATTACH,EVOLVE,ABILITY,DISCARD = 6,7,8,9,10
RETREAT,ATTACK,END = 11,12,13
SEL_MAIN = 0

# Known card HP/damage (fallback when attacks field missing)
CARD = {
    431: (280,160), 24: (230,120), 414: (120,90),   # TR deck
    425: (120,80),  409: (130,70),  408: (70,30), 440: (60,20),
    974: (70,20),   678: (340,220), 673: (80,30),    # Mega Lucario deck
    674: (150,80),  676: (110,70),  675: (110,50), 235: (30,0),
}

def read_deck() -> list[int]:
    for base in ['/kaggle_simulations/agent', '.']:
        path = os.path.join(base, 'deck.csv')
        if os.path.isfile(path):
            ids = []
            with open(path) as f:
                for line in f:
                    s = line.strip()
                    if s and s.lstrip('-').isdigit(): ids.append(int(s))
            while len(ids) < 60 and ids: ids.append(ids[0])
            return ids[:60]
    return [1]*60

def _hp(p):
    if not p: return 0
    return max(0, (p.get('hp',0) or 0) - (p.get('damage',0) or 0))

def _dmg(p):
    if not p: return 0
    atks = p.get('attacks')
    if atks:
        try: return int(atks[0].get('damage',0) or 0)
        except: pass
    cid = p.get('id')
    return CARD.get(cid, (0,0))[1] if cid else 0

def select_action(obs: dict) -> list[int]:
    sel = obs.get('select')
    if not sel: return [0]
    opts = sel.get('option') or []
    if not opts: return [0]

    n = len(opts)
    mc = max(int(sel.get('maxCount', 1) or 1), 1)
    mic = max(int(sel.get('minCount', 0) or 0), 0)
    sel_type = sel.get('type', -1)

    # MAIN action: smarter priority
    if sel_type == 0:
        cur = obs.get('current') or {}
        pls = cur.get('players') or []
        yi = int(cur.get('yourIndex', 0) or 0)
        me = pls[yi] if 0 <= yi < len(pls) else {}
        op = pls[1-yi] if 0 <= (1-yi) < len(pls) else {}
        ma = (me.get('active') or [None])[0]
        oa = (op.get('active') or [None])[0]
        mb = me.get('bench') or []
        mhp, ohp = _hp(ma) if ma else 0, _hp(oa) if oa else 999
        mdmg, odmg = _dmg(ma) if ma else 0, _dmg(oa) if oa else 0
        ea = cur.get('energyAttached', False)

        # Find strongest bench attacker
        bbi, bbd, bbh = -1, 0, 0
        for i, b in enumerate(mb):
            d = _dmg(b); h = _hp(b)
            if d > bbd or (d == bbd and h > bbh):
                bbi, bbd, bbh = i, d, h

        under_threat = odmg > 0 and odmg >= mhp
        want_swap = (bbd > mdmg and bbh > mhp/2) or (mhp < 80 and len(mb) > 0)

        bi, bp = 0, 99
        for i, o in enumerate(opts):
            t = int(o.get('type', -1) or -1)
            s = 50
            if t == ATTACK:
                s = 0 if (mdmg > 0 and mdmg >= ohp) else (4 if mdmg > 0 else 50)
            elif t == RETREAT:
                s = 1 if under_threat else (3 if want_swap else (7 if mhp < 100 and len(mb) > 0 else 25))
            elif t == EVOLVE: s = 2
            elif t == PLAY: s = 5 if len(mb) < 3 else 11
            elif t == ATTACH:
                s = 6 if (not ea and (mdmg >= bbd or bbd == 0)) else (8 if not ea else 20)
            elif t in (ABILITY, DISCARD): s = 9
            elif t == END: s = 99
            if s < bp: bp, bi = s, i
        return [bi] or [0]

    # Sub-selection
    count = max(mic, min(mc, n))
    return list(range(count)) or [0]

def agent(obs_dict: dict) -> list[int]:
    global _CALL, _DECK
    _CALL += 1
    try:
        sel = obs_dict.get('select') if isinstance(obs_dict, dict) else None
        if sel is None:
            if _DECK is None: _DECK = read_deck()
            return list(_DECK)
        return select_action(obs_dict)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        try:
            if obs_dict.get('select') is None: return _DECK or []
            opts = obs_dict['select'].get('option', [])
            return [0] if opts else []
        except: return []
