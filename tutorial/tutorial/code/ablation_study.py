"""
Ablation Study: BTM-SNN ROP Detector
====================================
Four ablation dimensions:
1. Signal source: all-branch vs RET-only
2. CPI factor: 1 vs 3 vs 5 (microarchitecture sensitivity)
3. Detector type: LIF vs FixedCounter vs LeakyCounter vs SimpleThreshold
4. LIF parameter sensitivity: tau, W, V_th sweeps

For each ablation, measure: FP rate on normal programs, detection rate on ROP.
"""
import numpy as np

CPI = 3
T_PROG = 50000

# ============================================================
# Shared simulation infrastructure
# ============================================================
def gen_ret_seq(density_all=1/24, density_ret=1/150, seed=42):
    np.random.seed(seed)
    seq_all = np.zeros(T_PROG, dtype=int)
    seq_ret = np.zeros(T_PROG, dtype=int)
    pos = int(np.random.uniform(0, 30))
    while pos < T_PROG:
        is_ret = np.random.random() < (density_ret / density_all)
        seq_all[pos] = 1
        if is_ret: seq_ret[pos] = 1
        gap = max(CPI, int(np.random.exponential(1/density_all - CPI) + CPI))
        pos += gap
    return seq_all, seq_ret

def gen_rop_seq(rounds=5, cpi=CPI):
    gadget_lens = [3, 4, 2, 5, 3, 4, 3, 2, 5, 3, 3, 4, 2, 6, 4]
    seq_all = []; seq_ret = []
    for _ in range(rounds):
        for gl in gadget_lens:
            gap = gl * cpi
            seq_all.extend([0]*(gap-1)); seq_all.append(1)
            seq_ret.extend([0]*(gap-1)); seq_ret.append(1)
    return np.array(seq_all, dtype=int), np.array(seq_ret, dtype=int)

def lif_detect(seq, tau, vth, w):
    V = 0; spikes = 0; vmax = 0
    for I in seq:
        V_next = V + (w if I > 0 else 0) - V // tau
        if V_next >= vth: spikes += 1; V = 0
        else: V = V_next
        if V > vmax: vmax = V
    return vmax, spikes

# Alternative detectors
def fixed_counter(seq, window, threshold):
    """Fixed-size sliding window counter. O(W) memory equivalent."""
    spikes = 0; vmax = 0
    buf = []
    for I in seq:
        buf.append(1 if I > 0 else 0)
        if len(buf) > window: buf.pop(0)
        count = sum(buf)
        if count > vmax: vmax = count
        if count >= threshold: spikes += 1; buf = []  # reset window
    return vmax, spikes

def leaky_counter(seq, decay, threshold):
    """Leaky bucket counter. Like LIF but without integer division reset dynamics."""
    V = 0; spikes = 0; vmax = 0
    for I in seq:
        V = V * decay + (1 if I > 0 else 0)  # exponential decay
        if V > vmax: vmax = V
        if V >= threshold: spikes += 1; V = 0
    return vmax, spikes

def simple_threshold(seq, gap_threshold):
    """Simple threshold: alarm if N branches within M cycles."""
    # Simplified: count consecutive branches
    spikes = 0; vmax = 0; count = 0
    last_branch = -999
    for t, I in enumerate(seq):
        if I > 0:
            if t - last_branch <= gap_threshold:
                count += 1
            else:
                count = 1
            last_branch = t
            if count > vmax: vmax = count
            if count >= 5:  # 5 consecutive close branches
                spikes += 1
                count = 0
    return vmax, spikes

# Generate data
seqs_normal = {
    'Dhrystone': gen_ret_seq(1/24, 1/150, 42),
    'CoreMark':  gen_ret_seq(1/14, 1/100, 123),
    'DSP-loop':  gen_ret_seq(1/6,  1/80,  99),
}
seq_rop = gen_rop_seq(5, CPI)

print("="*70)
print("ABLATION 1: SIGNAL SOURCE (all-branch vs RET-only)")
print("="*70)
tau, vth, w = 24, 100, 30
for name, (sa, sr) in seqs_normal.items():
    va, sa_sp = lif_detect(sa * w, tau, vth, w)
    vr, sr_sp = lif_detect(sr * w, tau, vth, w)
    print(f"  {name:12s} | all-branch: Vmax={va:3d}, FP={sa_sp:3d} | RET-only: Vmax={vr:3d}, FP={sr_sp:3d}")
va, sa_sp = lif_detect(seq_rop[0] * w, tau, vth, w)
vr, sr_sp = lif_detect(seq_rop[1] * w, tau, vth, w)
print(f"  {'ROP':12s} | all-branch: Vmax={va:3d}, detect={sa_sp:3d} | RET-only: Vmax={vr:3d}, detect={sr_sp:3d}")
print(f"  -> RET-only: {sr_sp}/{sa_sp} detections, {(seq_rop[1]>0).sum()} RET gadgets")

print("\n" + "="*70)
print("ABLATION 2: CPI FACTOR (microarchitecture sensitivity)")
print("="*70)
for cpi in [1, 2, 3, 4, 5]:
    s_all, s_ret = gen_rop_seq(5, cpi)
    v_all, sp_all = lif_detect(s_all * w, tau, vth, w)
    v_ret, sp_ret = lif_detect(s_ret * w, tau, vth, w)
    density_ret = (s_ret>0).sum() / len(s_ret)
    print(f"  CPI={cpi}: RET density={density_ret:.4f}/cyc, all-branch detect={sp_all:2d}, RET-only detect={sp_ret:2d}")

print("\n" + "="*70)
print("ABLATION 3: DETECTOR TYPE (LIF vs Counter vs LeakyCounter)")
print("="*70)
# Tune each detector for comparable sensitivity then test
_, sr_d = seqs_normal['Dhrystone']
_, sr_r = seq_rop

detectors = {
    'LIF (tau=24, Vth=100, W=30)':        ('lif', lif_detect, (24, 100, 30)),
    'LIF (tau=10, Vth=100, W=25) orig':   ('lif', lif_detect, (10, 100, 25)),
    'FixedWindow (W=100, Th=5)':           ('fw', fixed_counter, (100, 5)),
    'FixedWindow (W=200, Th=8)':           ('fw', fixed_counter, (200, 8)),
    'LeakyCounter (decay=0.95, Th=5.0)':   ('lc', leaky_counter, (0.95, 5.0)),
    'LeakyCounter (decay=0.98, Th=10.0)':  ('lc', leaky_counter, (0.98, 10.0)),
    'SimpleThreshold (gap=10)':            ('st', simple_threshold, (10,)),
    'SimpleThreshold (gap=5)':             ('st', simple_threshold, (5,)),
}

seq_test_ret = sr_d
seq_test_rop = sr_r

print(f"{'Detector':<42s} {'Dhry FP':>8s} {'DSP FP':>8s} {'ROP detect':>10s} {'Hardware':>10s}")
print("-"*80)
for name, (dtype, func, args) in detectors.items():
    if dtype == 'lif':
        vd, sd = func(seq_test_ret * args[2], *args)
        vdsp, sdsp = func(seqs_normal['DSP-loop'][1] * args[2], *args)
        vr, sr = func(seq_test_rop * args[2], *args)
        hw = "~119 LUTs"
    elif dtype == 'fw':
        vd, sd = func(seq_test_ret, *args)
        vdsp, sdsp = func(seqs_normal['DSP-loop'][1], *args)
        vr, sr = func(seq_test_rop, *args)
        hw = f"~{args[0]} FFs + adder"
    elif dtype == 'lc':
        # Scale inputs for leaky counter
        vd, sd = func(seq_test_ret * 1, *args)
        vdsp, sdsp = func(seqs_normal['DSP-loop'][1] * 1, *args)
        vr, sr = func(seq_test_rop * 1, *args)
        hw = "~50 LUTs (fixed-pt)"
    else:
        vd, sd = func(seq_test_ret, *args)
        vdsp, sdsp = func(seqs_normal['DSP-loop'][1], *args)
        vr, sr = func(seq_test_rop, *args)
        hw = "~20 LUTs"

    status = "SAFE+DETECT" if (sd==0 and sdsp==0 and sr>0) else ("FP!" if (sd>0 or sdsp>0) else "MISS")
    print(f"{name:<42s} {sd:8d} {sdsp:8d} {sr:10d} {hw:>10s} [{status}]")

print("\n" + "="*70)
print("ABLATION 4: LIF PARAMETER SENSITIVITY")
print("="*70)
# Vary one parameter at a time from the baseline (tau=24, Vth=100, W=30)
sr_d = seqs_normal['Dhrystone'][1]
sr_c = seqs_normal['CoreMark'][1]
sr_r = seq_rop[1]

print("\n--- Varying tau (Vth=100, W=30) ---")
for tau in [8, 12, 16, 20, 24, 32, 40]:
    vd, sd = lif_detect(sr_d * 30, tau, 100, 30)
    vc, sc = lif_detect(sr_c * 30, tau, 100, 30)
    vr, sr = lif_detect(sr_r * 30, tau, 100, 30)
    ok = "OK" if sd==0 and sc==0 and sr>0 else ("FP" if sd>0 or sc>0 else "MISS")
    print(f"  tau={tau:2d}: Dhry Vmax={vd:3d} S={sd:2d} | Core Vmax={vc:3d} S={sc:2d} | ROP S={sr:2d} [{ok}]")

print("\n--- Varying V_th (tau=24, W=30) ---")
for vth in [60, 80, 100, 120, 150, 200]:
    vd, sd = lif_detect(sr_d * 30, 24, vth, 30)
    vc, sc = lif_detect(sr_c * 30, 24, vth, 30)
    vr, sr = lif_detect(sr_r * 30, 24, vth, 30)
    ok = "OK" if sd==0 and sc==0 and sr>0 else ("FP" if sd>0 or sc>0 else "MISS")
    print(f"  V_th={vth:3d}: Dhry Vmax={vd:3d} S={sd:2d} | Core Vmax={vc:3d} S={sc:2d} | ROP S={sr:2d} [{ok}]")

print("\n--- Varying W (tau=24, Vth=100) ---")
for w in [20, 25, 30, 35, 40, 50]:
    vd, sd = lif_detect(sr_d * w, 24, 100, w)
    vc, sc = lif_detect(sr_c * w, 24, 100, w)
    vr, sr = lif_detect(sr_r * w, 24, 100, w)
    ok = "OK" if sd==0 and sc==0 and sr>0 else ("FP" if sd>0 or sc>0 else "MISS")
    print(f"  W={w:3d}: Dhry Vmax={vd:3d} S={sd:2d} | Core Vmax={vc:3d} S={sc:2d} | ROP S={sr:2d} [{ok}]")

print("\nDone.")
