"""PTCG AI Battle — Simulation Category (DIAGNOSTIC v2)
Engine: cabt — https://matsuoinstitute.github.io/cabt/
Logs every call to stderr. Download agent logs on Kaggle to debug."""

import os, sys, traceback
from typing import Optional

_CALL = 0
_DECK: Optional[list[int]] = None

try:
    print(f"[AGENT] START py={sys.version.split()[0]} cwd={os.getcwd()}", file=sys.stderr, flush=True)
except: pass

def read_deck() -> list[int]:
    for base in ['/kaggle_simulations/agent', '.']:
        path = os.path.join(base, 'deck.csv')
        print(f"[AGENT] probe {path} ok={os.path.isfile(path)}", file=sys.stderr, flush=True)
        if os.path.isfile(path):
            ids = []
            with open(path) as f:
                for line in f:
                    s = line.strip()
                    if s and s.lstrip('-').isdigit():
                        ids.append(int(s))
            print(f"[AGENT] deck={len(ids)} from {path}", file=sys.stderr, flush=True)
            while len(ids) < 60 and ids: ids.append(ids[0])
            return ids[:60]
    print("[AGENT] FATAL no deck.csv", file=sys.stderr, flush=True)
    return [1]*60

def _hp(p):
    if not p: return 0
    return max(0, p.get('hp', 0) - p.get('damage', 0))

def _dmg(a):
    if not a: return 0
    try: return int(a[0].get('damage', 0))
    except: return 0

def select_action(obs: dict) -> list[int]:
    sel = obs.get('select')
    if not sel: return []
    opts = sel.get('option') or []
    n = len(opts)
    if n == 0: return []
    if n == 1: return [0]

    cur = obs.get('current') or {}
    pls = cur.get('players') or []
    yi = sel.get('yourIndex', 0)
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
        t = str(o.get('type', '')).lower()
        p = 50
        if t in ('attack','use_attack','move'):
            p = 0 if iko else (5 if mdmg > 0 else 50)
        elif t in ('retreat','switch'):
            p = 1 if (ocko and hb) else (8 if (mhp < 50 and hb) else 30)
        elif t in ('evolve','evolution'): p = 2
        elif t in ('play_basic','bench','play_to_bench'): p = 3 if bs else 10
        elif t in ('attach_energy','energy_attach'): p = 4 if not ea else 20
        elif t in ('trainer','use_supporter','use_item','supporter'): p = 6
        elif t in ('ability','use_ability'): p = 9
        elif t in ('pass','end_turn'): p = 99
        if p < bp: bp, bi = p, i

    mc = sel.get('maxCount', 1) or 1
    mic = sel.get('minCount', 0) or 0
    if mc <= 1: return [bi]
    r = [bi]
    need = max(mic, min(mc, n))
    for j in range(1, need):
        if j < n and j not in r: r.append(j)
    return r[:mc]

def agent(obs_dict: dict) -> list[int]:
    global _CALL, _DECK
    _CALL += 1; c = _CALL

    try:
        sel = obs_dict.get('select') if isinstance(obs_dict, dict) else None

        if c <= 3 or c % 50 == 0:
            nopts = len(sel.get('option', [])) if sel else 0
            print(f"[AGENT] #{c} {'DECK' if sel is None else f'SEL n={nopts}'}", file=sys.stderr, flush=True)

        if sel is None:
            if _DECK is None: _DECK = read_deck()
            return list(_DECK)

        return select_action(obs_dict)

    except Exception:
        print(f"[AGENT] #{c} CRASH:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        try:
            if obs_dict.get('select') is None: return _DECK or []
            return [0] if obs_dict['select'].get('option') else []
        except: return []
