"""PTCG AI Battle - Team Rocket Control v4 (ROBUST)
Engine: cabt - Integer enums + never-return-empty + card data fallback."""

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
    431: (280,160), 24: (230,120), 414: (120,90),
    425: (120,80),  409: (130,70),  408: (70,30), 440: (60,20),
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
    if not sel: return []
    opts = sel.get('option') or []
    n = len(opts)
    if n == 0: return []

    mc = max(sel.get('maxCount', 1) or 1, 1)
    mic = max(sel.get('minCount', 0) or 0, 0)
    if n == 1: return [0][:mc]

    sel_type = sel.get('type', -1)

    if sel_type == SEL_MAIN:
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
        mdmg = _dmg(ma) if ma else 0
        odmg = _dmg(oa) if oa else 0
        iko = mdmg > 0 and mdmg >= ohp
        ocko = odmg > 0 and odmg >= mhp
        ea = cur.get('energyAttached', False)

        # Best bench attacker (for energy priority)
        best_bdmg = max((_dmg(b) for b in mb), default=0)

        bi, bp = 0, 99
        for i, o in enumerate(opts):
            t = o.get('type', -1)
            p = 50
            if t == ATTACK:
                p = 0 if iko else (5 if mdmg > 0 else 50)
            elif t == RETREAT:
                p = 1 if (ocko and len(mb)>0) else (8 if mhp<50 and len(mb)>0 else 30)
            elif t == EVOLVE: p = 2
            elif t == PLAY: p = 3 if len(mb) < 3 else 10
            elif t == ATTACH:
                # Prioritize attaching if active is weak and bench has stronger
                p = 3 if (not ea and best_bdmg > mdmg > 0) else (4 if not ea else 20)
            elif t in (ABILITY, DISCARD): p = 6
            elif t == END: p = 99
            if p < bp: bp, bi = p, i

        return [bi][:mc]

    # Sub-selection
    return list(range(max(mic, min(mc, n))))[:mc]

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
