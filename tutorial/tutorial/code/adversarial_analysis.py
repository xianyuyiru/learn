"""
Adversarial Robustness & Multi-Program Analysis for BTM-SNN ROP Detector
=======================================================================
Updated: CPI-aware branch modeling for multi-cycle CPU realism.

Key fix: On PicoRV32 (multi-cycle), minimum inter-branch gap ≥ 3 cycles
(CPI of taken branch = fetch + ld_rs1 + ld_rs2 + exec = 4 cycles minimum).
Random uniform models without this constraint produce unrealistic clusters.

Matches Verilog LIF exactly: integer division, weight=25, tau=10, threshold=100
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# LIF Model — exact match to Verilog (integer division)
# ============================================================
TAU = 10
THRESHOLD = 100
WEIGHT = 25
CPI_MIN = 4  # minimum cycles between branches on PicoRV32 multi-cycle

def lif_simulate(input_sequence):
    """Returns V_trace, spike_trace for a given input current sequence."""
    V = 0
    V_trace = []
    spike_trace = []
    for I in input_sequence:
        V_next = V + I - V // TAU
        if V_next >= THRESHOLD:
            V_trace.append(THRESHOLD)
            spike_trace.append(1)
            V = 0
        else:
            V_trace.append(V_next)
            spike_trace.append(0)
            V = V_next
    return np.array(V_trace), np.array(spike_trace)


def generate_realistic_branch_sequence(length, density, min_gap=CPI_MIN,
                                        burstiness=0.0, seed=42):
    """
    Generate a CPI-aware branch sequence for a multi-cycle CPU.

    Parameters:
    - density: target branch density (branches/cycle)
    - min_gap: minimum cycles between branches (CPI constraint)
    - burstiness: 0=uniform, 1=highly bursty (clusters of branches)
    """
    np.random.seed(seed)
    seq = np.zeros(length, dtype=int)

    # Convert density to mean interval
    mean_interval = 1.0 / density if density > 0 else float('inf')

    pos = int(np.random.uniform(0, min(mean_interval * 0.5, 50)))
    while pos < length:
        # Place a branch
        seq[pos] = WEIGHT

        # Compute next gap
        if burstiness > 0:
            # Mix of short gaps (burst) and long gaps (quiet)
            if np.random.random() < burstiness:
                # Burst mode: short gap
                gap = np.random.randint(min_gap, max(min_gap + 1, int(mean_interval * 0.3)))
            else:
                # Quiet mode: long gap
                gap = np.random.randint(max(min_gap, int(mean_interval * 0.5)),
                                       max(min_gap + 1, int(mean_interval * 2.5)))
        else:
            # Exponential-like spacing with min_gap constraint
            gap = max(min_gap, int(np.random.exponential(mean_interval - min_gap) + min_gap))

        pos += gap

    return seq


# ============================================================
# Experiment 1: Adversarial Slowdown Curve
# ============================================================
print("=" * 60)
print("Experiment 1: Adversarial Slowdown Curve")
print("=" * 60)

intervals = list(range(1, 31))
max_v_values = []
spike_counts = []

T_SIM = 1000

for interval in intervals:
    seq = np.zeros(T_SIM, dtype=int)
    for t in range(0, T_SIM, interval):
        seq[t] = WEIGHT
    V_trace, S_trace = lif_simulate(seq)
    max_v_values.append(V_trace.max())
    spike_counts.append(S_trace.sum())

# Find evasion threshold
evasion_interval = None
for i, (interval, sc) in enumerate(zip(intervals, spike_counts)):
    if sc == 0 and (i == 0 or spike_counts[i-1] > 0):
        evasion_interval = interval
        break

print(f"\nEvasion threshold: interval >= {evasion_interval} cycles -> LIF silent")
print(f"Normal program density: ~1/24 = {1/24:.3f}/cycle")
print(f"ROP attack (testbench, unrealistic): ~1/3.6 = {1/3.6:.3f}/cycle")
print(f"ROP attack (CPI-adjusted, real CPU): ~1/{3.6*CPI_MIN:.0f} = {1/(3.6*CPI_MIN):.3f}/cycle")

# ============================================================
# Experiment 2: Multi-Program Density Analysis (CPI-aware)
# ============================================================
print("\n" + "=" * 60)
print("Experiment 2: Multi-Program Density Analysis (CPI-aware)")
print("=" * 60)

T_PROG = 100000

programs = {
    'Dhrystone (baseline)': {
        'density': 1/24,
        'burstiness': 0.1,  # mostly uniform, slight clustering
    },
    'CoreMark (est.)': {
        'density': 1/12,
        'burstiness': 0.2,  # loop-heavy, moderate clustering
    },
    'Recursive Fibonacci': {
        'density': 1/12,     # recursive: call bursts during descent
        'burstiness': 0.8,   # highly bursty
    },
    'Lexer/Parser (switch-case)': {
        'density': 1/14,
        'burstiness': 0.3,
    },
    'IRQ-heavy (timer 8kHz)': {
        'density': 1/18,
        'burstiness': 0.5,   # periodic IRQ bursts
    },
    'Tight inner loop (DSP)': {
        'density': 1/6,
        'burstiness': 0.0,   # very regular
    },
}

results = []
for name, cfg in programs.items():
    seq = generate_realistic_branch_sequence(
        T_PROG, cfg['density'], min_gap=CPI_MIN,
        burstiness=cfg['burstiness'], seed=hash(name) % 10000)

    V_trace, S_trace = lif_simulate(seq)

    actual_density = (seq > 0).sum() / T_PROG
    status = "SAFE" if S_trace.sum() == 0 else f"FALSE POSITIVE ({S_trace.sum()} spikes)"

    print(f"\n{name}:")
    print(f"  Branch density: {actual_density:.4f}/cycle (1 per {1/actual_density:.1f} cycles)")
    print(f"  Total branches: {(seq > 0).sum()}")
    print(f"  V_max: {V_trace.max()}")
    print(f"  Spikes: {S_trace.sum()}")
    print(f"  Status: {status}")

    results.append({
        'name': name,
        'density': actual_density,
        'V_max': V_trace.max(),
        'spikes': S_trace.sum(),
        'status': status,
    })

# ============================================================
# Experiment 3: ROP Chain Realism Analysis
# ============================================================
print("\n" + "=" * 60)
print("Experiment 3: ROP Chain Detection (CPI-adjusted)")
print("=" * 60)

# The testbench used gadget lengths [3,4,2,5,3,4,3,2,5,3,3,4,2,6,4] as CYCLE counts
# On a real multi-cycle CPU, each instruction takes CPI_MIN cycles
# So the real inter-branch interval = gadget_length * CPI_MIN

gadget_lengths_instr = [3, 4, 2, 5, 3, 4, 3, 2, 5, 3, 3, 4, 2, 6, 4]
gadget_intervals_testbench = gadget_lengths_instr  # testbench: 1 "cycle" per instruction

# Real PicoRV32: each instruction = CPI_MIN cycles
gadget_intervals_realistic = [g * CPI_MIN for g in gadget_lengths_instr]

# Simulate both scenarios
T_ROP = 800
# Testbench version (unrealistic)
seq_tb = np.zeros(T_ROP, dtype=int)
pos = 0
for interval in gadget_intervals_testbench * 5:  # repeat chain 5x
    if pos < T_ROP:
        seq_tb[pos] = WEIGHT
    pos += max(1, interval)

# Realistic version (CPI-adjusted)
seq_real = np.zeros(T_ROP, dtype=int)
pos = 0
for interval in gadget_intervals_realistic * 5:
    if pos < T_ROP:
        seq_real[pos] = WEIGHT
    pos += max(1, interval)

V_tb, S_tb = lif_simulate(seq_tb)
V_real, S_real = lif_simulate(seq_real)

print(f"\nTestbench ROP (1 cyc/instr): V_max={V_tb.max()}, spikes={S_tb.sum()}")
print(f"Realistic ROP (4 cyc/instr):  V_max={V_real.max()}, spikes={S_real.sum()}")
print(f"\nCPI-adjusted gap range: {min(gadget_intervals_realistic)}-{max(gadget_intervals_realistic)} cycles")

if S_real.sum() == 0:
    print("\n*** CRITICAL: Current parameters FAIL to detect ROP on real multi-cycle CPU! ***")
    print("*** Parameters must be re-tuned for CPI-adjusted branch density. ***")

# ============================================================
# Experiment 4: Parameter Re-tuning for Realistic ROP
# ============================================================
print("\n" + "=" * 60)
print("Experiment 4: Parameter Re-tuning for CPI-adjusted ROP Detection")
print("=" * 60)

# Search for parameters that:
# (a) Detect realistic ROP (interval 8-24 cycles)
# (b) Don't false-positive on Dhrystone (density ~1/24, with CPI min_gap)
# (c) Don't false-positive on CoreMark (density ~1/12)

seq_dhry = generate_realistic_branch_sequence(50000, 1/24, min_gap=CPI_MIN,
                                               burstiness=0.1, seed=42)
seq_coremark = generate_realistic_branch_sequence(50000, 1/12, min_gap=CPI_MIN,
                                                    burstiness=0.2, seed=123)
# Realistic ROP: gadget lengths 2-6 instr * CPI_MIN cycles
seq_rop_real = seq_real[:500]

def eval_params(tau, vth, weight):
    """Evaluate a parameter combination across 3 scenarios."""
    def sim(seq):
        V = 0
        spikes = 0
        max_v = 0
        for I in seq:
            V_next = V + I - V // tau
            if V_next >= vth:
                spikes += 1
                V = 0
            else:
                V = V_next
            if V > max_v:
                max_v = V
        return max_v, spikes

    v_dhry, s_dhry = sim(seq_dhry)
    v_core, s_core = sim(seq_coremark)
    v_rop, s_rop = sim(seq_rop_real)

    return {
        'tau': tau, 'vth': vth, 'weight': weight,
        'V_dhry': v_dhry, 'S_dhry': s_dhry,
        'V_core': v_core, 'S_core': s_core,
        'V_rop': v_rop, 'S_rop': s_rop,
        'safe_dhry': s_dhry == 0,
        'safe_core': s_core == 0,
        'detect_rop': s_rop > 0,
        'all_safe': s_dhry == 0 and s_core == 0 and s_rop > 0,
    }

# Grid search
tau_range = [8, 10, 12, 16, 20, 32, 50]
vth_range = [80, 100, 120, 150, 200, 250, 300]
weight_range = [25, 30, 40, 50]

all_results = []
for tau in tau_range:
    for vth in vth_range:
        for weight in weight_range:
            all_results.append(eval_params(tau, vth, weight))

# Find all-safe combinations
safe_combos = [r for r in all_results if r['all_safe']]
print(f"\nTotal parameter combinations: {len(all_results)}")
print(f"Safe combinations (no FP on Dhrystone+CoreMark, detects ROP): {len(safe_combos)}")

if safe_combos:
    print("\nRecommended parameter sets:")
    for r in sorted(safe_combos, key=lambda x: (x['V_rop'] - x['vth'], x['V_core']))[:10]:
        print(f"  tau={r['tau']:2d}, V_th={r['vth']:3d}, weight={r['weight']:2d}: "
              f"V_dhry={r['V_dhry']:3d}, V_core={r['V_core']:3d}, V_rop={r['V_rop']:3d}")
else:
    # Find closest-to-safe
    print("\nNo perfectly safe combination found.")
    print("Closest combinations (detect ROP, FP only on CoreMark):")
    close = [r for r in all_results if r['safe_dhry'] and r['detect_rop']]
    for r in sorted(close, key=lambda x: x['V_core'])[:10]:
        print(f"  tau={r['tau']:2d}, V_th={r['vth']:3d}, weight={r['weight']:2d}: "
              f"V_dhry={r['V_dhry']:3d}, V_core={r['V_core']:3d} (>{r['vth']}!), V_rop={r['V_rop']:3d}")

    print("\nClosest combinations (FP-free but miss ROP):")
    close2 = [r for r in all_results if r['safe_dhry'] and r['safe_core'] and not r['detect_rop']]
    if close2:
        for r_item in sorted(close2, key=lambda x: x['V_rop'] - x['vth'], reverse=True)[:10]:
            print(f"  tau={r_item['tau']:2d}, V_th={r_item['vth']:3d}, weight={r_item['weight']:2d}: "
                  f"V_dhry={r_item['V_dhry']:3d}, V_core={r_item['V_core']:3d}, V_rop={r_item['V_rop']:3d} (miss!)")

# ============================================================
# Experiment 5: Why the testbench detected ROP (CPU runs in parallel)
# ============================================================
print("\n" + "=" * 60)
print("Experiment 5: Testbench ROP Detection Explained")
print("=" * 60)
print("The testbench runs ROP FSM AND normal firmware simultaneously.")
print("During attack window (50 cycles), both contribute pulses:")
print("  ROP FSM: ~15 branches (gadget chain)")
print("  CPU normal firmware: ~2 branches (density ~1/24)")
print("  Combined: ROP pulses every 2-6 cyc + occasional CPU pulses")
print("")
print("This combined density is HIGHER than a real attack would produce.")
print("On a real CPU under ROP attack, ONLY ROP gadgets execute.")
print("No normal firmware runs simultaneously.")
print("")
print("-> Testbench results OVERESTIMATE detection capability.")
print("-> Need parameter re-tuning for realistic deployment.")

# Simulate combined scenario
T_COMBINED = 100
seq_combined = np.zeros(T_COMBINED, dtype=int)

# ROP pulses (testbench timing)
rop_positions = []
pos = 0
for interval in gadget_intervals_testbench:
    if pos < T_COMBINED:
        seq_combined[pos] = WEIGHT
        rop_positions.append(pos)
    pos += max(1, interval)

# Add CPU background branches (density 1/24)
np.random.seed(99)
for t in range(T_COMBINED):
    if t not in rop_positions and np.random.random() < 1/24:
        seq_combined[t] = WEIGHT

V_combined, S_combined = lif_simulate(seq_combined)

# Compare: ROP alone vs ROP + CPU
seq_rop_alone = np.zeros(T_COMBINED, dtype=int)
pos = 0
for interval in gadget_intervals_testbench:
    if pos < T_COMBINED:
        seq_rop_alone[pos] = WEIGHT
    pos += max(1, interval)
V_rop_alone, S_rop_alone = lif_simulate(seq_rop_alone)

print(f"\nROP alone (testbench timing, no CPU): V_max={V_rop_alone.max()}, spikes={S_rop_alone.sum()}")
print(f"ROP + CPU (testbench timing, realistic):   V_max={V_combined.max()}, spikes={S_combined.sum()}")
if S_combined.sum() > S_rop_alone.sum():
    print(f"-> Extra {S_combined.sum() - S_rop_alone.sum()} spikes from CPU background branches!")
    print("-> This explains the original testbench detection results.")

# ============================================================
# Experiment 6: Recommended Re-tuned Parameters
# ============================================================
print("\n" + "=" * 60)
print("Experiment 6: Recommended Parameters for Realistic Deployment")
print("=" * 60)

# The CPI-adjusted ROP has branch intervals of 8-24 cycles
# We need parameters that detect this while not false-positiving on normal programs
# Strategy: increase weight, increase tau (slower leak), adjust threshold

# Test specific recommended parameter sets
recommended = [
    {'tau': 16, 'vth': 120, 'weight': 40, 'note': 'Higher weight, slower leak'},
    {'tau': 20, 'vth': 150, 'weight': 50, 'note': 'Conservative, wide margin'},
    {'tau': 12, 'vth': 100, 'weight': 35, 'note': 'Minimal change from original'},
]

seq_dhry_50k = generate_realistic_branch_sequence(50000, 1/24, min_gap=CPI_MIN,
                                                    burstiness=0.1, seed=42)
seq_core_50k = generate_realistic_branch_sequence(50000, 1/12, min_gap=CPI_MIN,
                                                    burstiness=0.2, seed=123)
seq_rop_real_500 = seq_real[:500]

def test_params(tau, vth, weight):
    def sim(seq):
        V = 0
        spikes = 0
        max_v = 0
        for I in seq:
            V_next = V + I - V // tau
            if V_next >= vth:
                spikes += 1
                V = 0
            else:
                V = V_next
            if V > max_v:
                max_v = V
        return max_v, spikes

    v1, s1 = sim(seq_dhry_50k)
    v2, s2 = sim(seq_core_50k)
    v3, s3 = sim(seq_rop_real_500)
    return v1, s1, v2, s2, v3, s3

print("\nRecommended parameter sets for CPI-adjusted deployment:")
for rec in recommended:
    v1, s1, v2, s2, v3, s3 = test_params(rec['tau'], rec['vth'], rec['weight'])
    safe_d = "SAFE" if s1 == 0 else "FP!"
    safe_c = "SAFE" if s2 == 0 else "FP!"
    detect_r = "DETECT" if s3 > 0 else "MISS!"
    all_ok = "*** DEPLOYABLE ***" if (s1 == 0 and s2 == 0 and s3 > 0) else ""
    print(f"\n  tau={rec['tau']}, V_th={rec['vth']}, weight={rec['weight']} ({rec['note']})")
    print(f"    Dhrystone: V_max={v1}, spikes={s1} [{safe_d}]")
    print(f"    CoreMark:  V_max={v2}, spikes={s2} [{safe_c}]")
    print(f"    ROP (real): V_max={v3}, spikes={s3} [{detect_r}]")
    if all_ok:
        print(f"    {all_ok}")

# ============================================================
# FIGURES
# ============================================================

# Figure 1: Adversarial Slowdown with CPI Context
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Panel A: V_max vs inter-branch interval
ax = axes[0, 0]
ax.plot(intervals, max_v_values, 'b-o', markersize=4, linewidth=1.5)
ax.axhline(y=THRESHOLD, color='r', linestyle='--', linewidth=1.5,
           label=f'Threshold = {THRESHOLD}')
if evasion_interval:
    ax.axvline(x=evasion_interval, color='gray', linestyle=':', linewidth=1.5,
               label=f'Evasion boundary: {evasion_interval} cycles')

# Shade regions
ax.axvspan(1, 3, alpha=0.1, color='red', label='Detection zone')
ax.axvspan(3, 30, alpha=0.08, color='green', label='Evasion zone')

# Mark program operating points
ax.axvline(x=24, color='green', linestyle='--', alpha=0.6, linewidth=1)
ax.annotate('Normal\n(~24 cyc)', xy=(24, 40), fontsize=8, color='green',
            ha='center')
ax.axvline(x=3.6, color='red', linestyle='--', alpha=0.6, linewidth=1)
ax.annotate('ROP TB\n(~3.6 cyc)', xy=(3.6, 100), fontsize=8, color='red',
            ha='center')
ax.axvline(x=3.6*CPI_MIN, color='orange', linestyle='--', alpha=0.6, linewidth=1)
ax.annotate(f'ROP real\n(~{3.6*CPI_MIN:.0f} cyc)', xy=(3.6*CPI_MIN, 50), fontsize=8,
            color='orange', ha='center')

ax.set_xlabel('Inter-Branch Interval (cycles)', fontsize=11)
ax.set_ylabel('Max Membrane Potential V', fontsize=11)
ax.set_title('A. Adversarial Slowdown: V_max vs Interval', fontsize=12, fontweight='bold')
ax.legend(fontsize=7, loc='upper right')
ax.set_ylim(0, 130)
ax.grid(True, alpha=0.3)

# Panel B: V(t) for testbench vs realistic ROP
ax = axes[0, 1]
# Truncate to first 200 cycles
t_show = min(200, T_ROP)
ax.plot(V_tb[:t_show], 'r-', linewidth=1.2, alpha=0.7, label='Testbench ROP (1 cyc/instr)')
ax.plot(V_real[:t_show], 'orange', linewidth=1.5, label=f'Realistic ROP ({CPI_MIN} cyc/instr)')
ax.axhline(y=THRESHOLD, color='black', linestyle='--', linewidth=1, alpha=0.5)
# Mark spike points
tb_spike_times = np.where(S_tb[:t_show] == 1)[0]
real_spike_times = np.where(S_real[:t_show] == 1)[0]
if len(tb_spike_times) > 0:
    ax.scatter(tb_spike_times, [THRESHOLD]*len(tb_spike_times),
               color='red', marker='v', s=30, label=f'Spikes (TB): {S_tb.sum()}')
if len(real_spike_times) > 0:
    ax.scatter(real_spike_times, [THRESHOLD]*len(real_spike_times),
               color='orange', marker='^', s=30, label=f'Spikes (Real): {S_real.sum()}')

ax.set_xlabel('Cycle', fontsize=11)
ax.set_ylabel('Membrane Potential V', fontsize=11)
ax.set_title('B. ROP Detection: Testbench vs CPI-Adjusted', fontsize=12, fontweight='bold')
ax.legend(fontsize=7)
ax.set_ylim(0, 120)
ax.grid(True, alpha=0.3)

# Panel C: Multi-program V_max bar chart
ax = axes[1, 0]
names = [r['name'] for r in results]
vmax_vals = [r['V_max'] for r in results]
densities = [r['density'] for r in results]
spike_flags = [r['spikes'] > 0 for r in results]

colors_bar = ['#c62828' if s else '#2e7d32' for s in spike_flags]
bars = ax.barh(range(len(names)), vmax_vals, color=colors_bar, edgecolor='white', height=0.6)
ax.axvline(x=THRESHOLD, color='black', linestyle='--', linewidth=2, label=f'Threshold = {THRESHOLD}')
ax.set_yticks(range(len(names)))
ax.set_yticklabels([n.split('(')[0].strip() for n in names], fontsize=9)
ax.set_xlabel('Max Membrane Potential V', fontsize=11)
ax.set_title('C. V_max Across Program Types (CPI-aware)', fontsize=12, fontweight='bold')

for i, (vmax, density) in enumerate(zip(vmax_vals, densities)):
    ax.text(vmax + 1, i, f'1/{1/density:.0f} cyc', va='center', fontsize=7, color='gray')

from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#2e7d32', label='No false positive'),
    Patch(facecolor='#c62828', label='False positive (alarm)'),
]
ax.legend(handles=legend_elements, fontsize=8, loc='lower right')
ax.set_xlim(0, max(vmax_vals) * 1.15)
ax.grid(True, alpha=0.2, axis='x')

# Panel D: Parameter space safety map
ax = axes[1, 1]
# Pick tau and vth for a fixed weight=25
weight25_results = [r for r in all_results if r['weight'] == 25]

tau_vals = sorted(set(r['tau'] for r in weight25_results))
th_vals = sorted(set(r['vth'] for r in weight25_results))

# Create grid
grid = np.zeros((len(tau_vals), len(th_vals)))
grid_rop = np.zeros((len(tau_vals), len(th_vals)))
for r in weight25_results:
    ti = tau_vals.index(r['tau'])
    thi = th_vals.index(r['vth'])
    grid[ti, thi] = 1 if r['safe_dhry'] and r['safe_core'] else 0
    grid_rop[ti, thi] = 1 if r['detect_rop'] else 0

im = ax.imshow(grid, cmap='RdYlGn', aspect='auto', origin='lower',
               extent=[min(th_vals)-10, max(th_vals)+10,
                       min(tau_vals)-1, max(tau_vals)+1],
               alpha=0.7)

# Mark current design
ax.plot(THRESHOLD, TAU, 'b*', markersize=15, markeredgecolor='blue',
        markerfacecolor='yellow', label=f'Current (tau={TAU}, V_th={THRESHOLD})')

# Highlight ROP-detectable zone with diagonal hatching
for ti, tau in enumerate(tau_vals):
    for thi, th in enumerate(th_vals):
        r = [x for x in weight25_results if x['tau'] == tau and x['vth'] == th][0]
        if r['safe_dhry'] and r['safe_core'] and r['detect_rop']:
            ax.plot(th, tau, 'go', markersize=8, markerfacecolor='green')
        elif r['detect_rop'] and not (r['safe_dhry'] and r['safe_core']):
            ax.plot(th, tau, 'rx', markersize=5)

ax.set_xlabel('Threshold V_th', fontsize=11)
ax.set_ylabel('Time Constant tau', fontsize=11)
ax.set_title('D. Safe Operating Region (weight=25)', fontsize=12, fontweight='bold')
ax.legend(fontsize=8)

plt.suptitle('Adversarial Robustness Analysis of LIF-based ROP Detector\n'
             f'Parameters: I={WEIGHT}, tau={TAU}, V_th={THRESHOLD} | CPI_min={CPI_MIN} (multi-cycle)',
             fontweight='bold', fontsize=13)
plt.tight_layout()
plt.savefig('experiment/results/adversarial_analysis.png', dpi=150, bbox_inches='tight')
print("\nSaved: experiment/results/adversarial_analysis.png")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("KEY FINDINGS FOR PAPER")
print("=" * 60)

print(f"\n1. ADVERSARIAL SLOWDOWN:")
print(f"   Evasion threshold: >= {evasion_interval} cycles between branches")
print(f"   Normal (Dhrystone): ~24 cycles -> safely below threshold")
print(f"   Attack margin: ROP must slow to {evasion_interval}/3.6 = {evasion_interval/3.6:.1f}x to evade")

print(f"\n2. CPI-AWARE ROP DETECTION:")
print(f"   Testbench ROP (unrealistic): V_max={V_tb.max()}, {S_tb.sum()} spikes")
print(f"   Realistic ROP ({CPI_MIN}x CPI): V_max={V_real.max()}, {S_real.sum()} spikes")
if S_real.sum() == 0:
    print(f"   -> [CRITICAL] Current parameters FAIL on real multi-cycle CPU!")

print(f"\n3. MULTI-PROGRAM (CPI-aware):")
for r in results:
    flag = "[SAFE]" if r['spikes'] == 0 else "[FP!]"
    print(f"   {flag} {r['name']}: V_max={r['V_max']}, density={r['density']:.4f}/cycle")

print(f"\n4. PARAMETER RETUNING:")
print(f"   Safe (tau, V_th, weight) combinations: {len(safe_combos)}/{len(all_results)}")
if safe_combos:
    best = min(safe_combos, key=lambda x: x['V_core'])
    print(f"   Best: tau={best['tau']}, V_th={best['vth']}, weight={best['weight']}")
    print(f"     V_dhry={best['V_dhry']}, V_core={best['V_core']}, V_rop={best['V_rop']}")

print("\nDone.")
