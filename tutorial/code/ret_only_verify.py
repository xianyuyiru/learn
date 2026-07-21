"""
RET-Only Signal Approach: Verification
======================================
Key insight: branch_taken mixes all branch types. Normal programs have
many conditional branches (loop beq/bne) that drown the ROP signal.
If we filter to ONLY JALR/RET events, the noise floor drops dramatically.

Normal: RET density ~1/150 cycles (function returns are sparse)
ROP:    RET density ~1/10.8 cycles (CPI-adjusted, every gadget ends in RET)
Ratio:  ~14x (vs 2x for unfiltered branch_taken)
"""
import numpy as np

CPI = 3
T_PROG = 50000

def sim_lif(seq, tau, vth, weight):
    V = 0; spikes = 0; max_v = 0
    for I in seq:
        V_next = V + (weight if I > 0 else 0) - V // tau
        if V_next >= vth:
            spikes += 1; V = 0
        else:
            V = V_next
            if V > max_v: max_v = V
    return max_v, spikes

# === Normal program RET patterns ===
# In real programs, RETs come from function returns.
# Average function length ~100 instructions on embedded systems.
# On multi-cycle CPU (CPI~3): RET interval ~300 cycles.
# We model conservatively at 1/150 density.

def gen_ret_normal(density_ret=1/150, density_other=1/24, seed=42, length=T_PROG):
    """
    Generate realistic branch sequence with separate RET and non-RET branches.
    density_ret: JALR/RET density (sparse)
    density_other: total branch density minus RET (BEQ + JAL)
    """
    np.random.seed(seed)
    seq_all = np.zeros(length, dtype=int)      # all branches
    seq_ret = np.zeros(length, dtype=int)      # RET only

    pos = int(np.random.uniform(0, 30))
    while pos < length:
        # Decide if this branch is a RET (probability = density_ret/density_other)
        is_ret = np.random.random() < (density_ret / density_other)
        seq_all[pos] = 1
        if is_ret:
            seq_ret[pos] = 1
        gap = max(CPI, int(np.random.exponential(1/density_other - CPI) + CPI))
        pos += gap

    return seq_all, seq_ret

def gen_rop_ret(rounds=5):
    """ROP chain: every branch IS a RET (gadget termination)"""
    gadget_lens = [3, 4, 2, 5, 3, 4, 3, 2, 5, 3, 3, 4, 2, 6, 4]
    seq_all = []
    seq_ret = []
    for _ in range(rounds):
        for gl in gadget_lens:
            gap = gl * CPI
            seq_all.extend([0] * (gap - 1))
            seq_all.append(1)
            seq_ret.extend([0] * (gap - 1))
            seq_ret.append(1)  # Every ROP branch is a RET
    return np.array(seq_all, dtype=int), np.array(seq_ret, dtype=int)

# Generate sequences
seq_all_d, seq_ret_d = gen_ret_normal(1/150, 1/24, 42)
seq_all_c, seq_ret_c = gen_ret_normal(1/100, 1/14, 123)  # CoreMark: more calls
seq_all_rop, seq_ret_rop = gen_rop_ret(5)

print("=" * 70)
print("RET-ONLY SIGNAL ANALYSIS")
print("=" * 70)

print(f"\nNormal (Dhrystone):")
print(f"  All branches: {(seq_all_d > 0).sum()}, density={(seq_all_d > 0).sum()/T_PROG:.4f}")
print(f"  RET only:     {(seq_ret_d > 0).sum()}, density={(seq_ret_d > 0).sum()/T_PROG:.4f}")
print(f"  Ratio RET/all: {(seq_ret_d > 0).sum()/max(1,(seq_all_d > 0).sum())*100:.1f}%")

print(f"\nROP (CPI-adjusted):")
print(f"  All branches (all RET): {(seq_all_rop > 0).sum()}, density={(seq_all_rop > 0).sum()/len(seq_all_rop):.4f}")
print(f"  RET density = ALL density (every gadget ends in RET)")

print(f"\nDensity ratio (ROP/normal):")
print(f"  All branches: {(seq_all_rop > 0).sum()/len(seq_all_rop):.4f} / {(seq_all_d > 0).sum()/T_PROG:.4f} = {(seq_all_rop > 0).sum()/len(seq_all_rop) / ((seq_all_d > 0).sum()/T_PROG):.1f}x")
print(f"  RET only:     {(seq_ret_rop > 0).sum()/len(seq_ret_rop):.4f} / {(seq_ret_d > 0).sum()/T_PROG:.4f} = {(seq_ret_rop > 0).sum()/len(seq_ret_rop) / max(0.0001, (seq_ret_d > 0).sum()/T_PROG):.1f}x")

# === LIF parameter search for RET-only ===
print(f"\n{'='*70}")
print("LIF PARAMETER SEARCH (RET-only signal)")
print(f"{'='*70}")

tau_vals = [8, 10, 12, 16, 20, 24, 32]
vth_vals = [60, 80, 100, 120, 150, 200]
w_vals   = [25, 30, 40, 50, 60]

min_rop_spikes = 3

print(f"\n{'tau':>3s} {'vth':>4s} {'W':>4s} | {'Dhry V':>7s} {'Dhry S':>7s} | {'Core V':>7s} {'Core S':>7s} | {'ROP V':>7s} {'ROP S':>7s} |")
print("-" * 78)

safe_solutions = []
for tau in tau_vals:
    for vth in vth_vals:
        for w in w_vals:
            v1, s1 = sim_lif(seq_ret_d * w, tau, vth, w)
            v2, s2 = sim_lif(seq_ret_c * w, tau, vth, w)
            v3, s3 = sim_lif(seq_ret_rop * w, tau, vth, w)

            safe = (s1 == 0) and (s2 == 0) and (s3 >= min_rop_spikes)
            if safe:
                safe_solutions.append((tau, vth, w, v1, v2, v3, s3))
                print(f" {tau:3d}  {vth:4d}  {w:4d} | {v1:7d} {s1:7d} | {v2:7d} {s2:7d} | {v3:7d} {s3:7d} | <<< SAFE")

if safe_solutions:
    print(f"\n*** FOUND {len(safe_solutions)} DEPLOYABLE SOLUTIONS! ***")
    # Pick the best: highest margin on normal programs
    safe_solutions.sort(key=lambda x: min(x[3], x[4]))
    best = safe_solutions[-1]
    print(f"\nRecommended: tau={best[0]}, V_th={best[1]}, W={best[2]}")
    print(f"  Dhrystone: Vmax={best[3]}, spikes=0")
    print(f"  CoreMark:  Vmax={best[4]}, spikes=0")
    print(f"  ROP:       Vmax={best[5]}, spikes={best[6]}")
    print(f"  Hardware: ~114 LUTs (same as original LIF)")
else:
    print("\nNo safe solution with these parameters. Trying wider range...")
    for tau in [10, 12, 16, 20]:
        for vth in [40, 50, 60, 80, 100]:
            for w in [30, 40, 50]:
                v1, s1 = sim_lif(seq_ret_d * w, tau, vth, w)
                v2, s2 = sim_lif(seq_ret_c * w, tau, vth, w)
                v3, s3 = sim_lif(seq_ret_rop * w, tau, vth, w)
                if s1 == 0 and s2 == 0 and s3 >= min_rop_spikes:
                    safe_solutions.append((tau, vth, w, v1, v2, v3, s3))
    if safe_solutions:
        print(f"Found {len(safe_solutions)} solutions in extended search!")
