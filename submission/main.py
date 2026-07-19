"""PTCG AI Battle - Team Rocket Control v3 (INTEGER ENUMS FIXED)
Engine: cabt - https://matsuoinstitute.github.io/cabt/
Fix: option.type is integer OptionType enum, not string."""

import os, sys, traceback
from typing import Optional

_CALL = 0
_DECK: Optional[list[int]] = None

# OptionType enum
PLAY,ATTACH,EVOLVE,ABILITY,DISCARD = 6,7,8,9,10
RETREAT,ATTACK,END = 11,12,13
SEL_MAIN = 0

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

def _dmg(a):
    if not a: return 0
    try: return int(a[0].get('damage',0) or 0)
    except: return 0

def select_action(obs: dict) -> list[int]:
    sel = obs.get('select')
    if not sel: return []
    opts = sel.get('option') or []
    n = len(opts)
    if n == 0: return []
    if n == 1: return [0]

    # Only use threat-aware logic for MAIN selection
    if sel.get('type', -1) == SEL_MAIN:
        cur = obs.get('current') or {}
        pls = cur.get('players') or []
        yi = cur.get('yourIndex', 0)
        me = pls[yi] if yi < len(pls) else {}
        op = pls[1-yi] if (1-yi) < len(pls) else {}
        ma = (me.get('active') or [None])[0]
        oa = (op.get('active') or [None])[0]
        mb = me.get('bench') or []
        mhp = _hp(ma) if ma else 0
        ohp = _hp(oa) if oa else 999
        mdmg = _dmg(ma.get('attacks')) if ma else 0
        odmg = _dmg(oa.get('attacks')) if oa else 0
        iko = mdmg > 0 and mdmg >= ohp
        ocko = odmg > 0 and odmg >= mhp
        hb = len(mb) > 0
        bs = len(mb) < 3
        ea = cur.get('energyAttached', False)
        bi, bp = 0, 99
        for i, o in enumerate(opts):
            t = o.get('type', -1)
            p = 50
            if t == ATTACK:
                p = 0 if iko else (5 if mdmg > 0 else 50)
            elif t == RETREAT:
                p = 1 if (ocko and hb) else (8 if mhp < 50 and hb else 30)
            elif t == EVOLVE: p = 2
            elif t == PLAY: p = 3 if bs else 10
            elif t == ATTACH: p = 4 if not ea else 20
            elif t in (ABILITY, DISCARD): p = 6
            elif t == END: p = 99
            if p < bp: bp, bi = p, i
        mc = sel.get('maxCount', 1) or 1
        if mc <= 1: return [bi]
        return [bi] + [0]*(mc-1)

    # Sub-selection: pick first N valid options
    mc = sel.get('maxCount', 1) or 1
    mic = sel.get('minCount', 0) or 0
    count = max(mic, min(mc, n))
    return list(range(count))

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
