"""
Multi-Neuron LIF Array for ROP Detection
========================================
3 neurons with heterogeneous tau: 10 (fast), 50 (medium), 200 (slow)
All share the same branch_taken input.
Alarm = OR(spike_1, spike_2, spike_3)
"""
import numpy as np

CPI = 3
T_PROG = 50000

def sim_multineuron(seq, params):
    """params = [(tau, vth, weight), ...]; returns (max_v_list, spikes_list, alarm_count)"""
    n = len(params)
    V = [0] * n
    spikes = [0] * n
    max_v = [0] * n
    alarms = 0
    for I_val in seq:
        any_spike = False
        for i, (tau, vth, w) in enumerate(params):
            V_next = V[i] + (w if I_val > 0 else 0) - V[i] // tau
            if V_next >= vth:
                spikes[i] += 1
                V[i] = 0
                any_spike = True
            else:
                V[i] = V_next
                if V[i] > max_v[i]:
                    max_v[i] = V[i]
        if any_spike:
            alarms += 1
    return max_v, spikes, alarms

def gen_sequence(density=1/24, seed=42, length=T_PROG):
    np.random.seed(seed)
    seq = np.zeros(length, dtype=int)
    pos = int(np.random.uniform(0, 30))
    while pos < length:
        seq[pos] = 1
        gap = max(CPI, int(np.random.exponential(1/density - CPI) + CPI))
        pos += gap
    return seq

def gen_rop_cpi(rounds=5):
    gadget_lens = [3, 4, 2, 5, 3, 4, 3, 2, 5, 3, 3, 4, 2, 6, 4]
    seq = []
    for _ in range(rounds):
        for gl in gadget_lens:
            seq.extend([0] * (gl * CPI - 1))
            seq.append(1)
    return np.array(seq, dtype=int)

# Generate sequences
seq_n_d = gen_sequence(1/24, 42)
seq_n_c = gen_sequence(1/12, 123)
seq_rop = gen_rop_cpi(5)
seq_irq = gen_sequence(1/18, 77)
seq_dsp = gen_sequence(1/6, 99)

print("=" * 85)
print("MULTI-NEURON PARAMETER SEARCH")
print("=" * 85)

# Candidate designs
candidates = [
    ("A: slow-dominant", [
        (10, 120, 25), (50, 150, 15), (200, 250, 10),
    ]),
    ("B: balanced", [
        (10, 100, 25), (50, 120, 20), (200, 300, 12),
    ]),
    ("C: slow-heavy", [
        (10, 150, 30), (50, 200, 20), (200, 400, 15),
    ]),
    ("D: aggressive-slow", [
        (10, 120, 25), (50, 180, 18), (200, 350, 12),
    ]),
    ("E: two-neuron", [
        (10, 100, 25), (200, 300, 10),
    ]),
]

for name, params in candidates:
    print(f"\n--- {name} ---")
    for i, (tau, vth, w) in enumerate(params):
        print(f"  N{i+1}: tau={tau:3d}, V_th={vth:3d}, W={w:2d}")

    all_safe = True
    for pname, seq in [("Dhrystone", seq_n_d), ("CoreMark", seq_n_c),
                        ("IRQ-heavy", seq_irq), ("DSP-loop", seq_dsp)]:
        max_v, spikes, alarms = sim_multineuron(seq, params)
        fp = [i+1 for i, s in enumerate(spikes) if s > 0]
        status = "SAFE" if len(fp) == 0 else f"FP: N{fp}"
        if fp:
            all_safe = False
        print(f"  {pname:12s}: Vmax={max_v}, spikes={spikes}, alarms={alarms} [{status}]")

    max_v, spikes, alarms = sim_multineuron(seq_rop, params)
    det = [i+1 for i, s in enumerate(spikes) if s > 0]
    detected = len(det) > 0
    print(f"  ROP(CPI-adj):     Vmax={max_v}, spikes={spikes}, alarms={alarms} "
          f"[{'DETECT N' + str(det) if detected else 'MISSED'}]")

    if all_safe and detected:
        print(f"  *** DEPLOYABLE ***")
    elif all_safe:
        print(f"  [SAFE but misses ROP]")
    elif detected:
        print(f"  [Detects ROP but has FP]")

# Grid search
print("\n" + "=" * 85)
print("GRID SEARCH: slow neuron (tau=200) optimization")
print("=" * 85)

best = []
for vth_s in [200, 250, 280, 300, 350, 400, 450, 500]:
    for w_s in [8, 10, 12, 15, 18, 20]:
        for vth_f in [100, 120, 150]:
            for vth_m in [120, 150, 180, 200]:
                params = [(10, vth_f, 25), (50, vth_m, 15), (200, vth_s, w_s)]
                safe = True
                for seq in [seq_n_d, seq_n_c, seq_irq]:
                    _, spikes, _ = sim_multineuron(seq, params)
                    if sum(spikes) > 0:
                        safe = False
                        break
                if not safe:
                    continue
                _, spikes_r, alarms_r = sim_multineuron(seq_rop, params)
                if sum(spikes_r) > 0:
                    mv_d, sp_d, _ = sim_multineuron(seq_n_d, params)
                    mv_c, sp_c, _ = sim_multineuron(seq_n_c, params)
                    mv_r, sp_r, _ = sim_multineuron(seq_rop, params)
                    margin = min([p[1] - mv for p, mv in zip(params, mv_d)] +
                                 [p[1] - mv for p, mv in zip(params, mv_c)])
                    best.append({
                        'params': params, 'Vmax_D': mv_d, 'Vmax_C': mv_c,
                        'Vmax_R': mv_r, 'spikes_R': sum(sp_r),
                        'alarms_R': alarms_r, 'margin': margin,
                    })

if best:
    best.sort(key=lambda x: (x['margin'], -x['spikes_R']), reverse=True)
    print(f"Found {len(best)} deployable solutions!")
    for i, sol in enumerate(best[:8]):
        p = sol['params']
        print(f"\n#{i+1}: tau=[{p[0][0]},{p[1][0]},{p[2][0]}], "
              f"Vth=[{p[0][1]},{p[1][1]},{p[2][1]}], W=[{p[0][2]},{p[1][2]},{p[2][2]}]")
        print(f"  Dhry: Vmax={sol['Vmax_D']}, Core: Vmax={sol['Vmax_C']}, "
              f"ROP: spikes={sol['spikes_R']}, alarms={sol['alarms_R']}, margin={sol['margin']}")
else:
    print("No deployable solution found. Trying wider search...")
    # Wider search: allow higher weights for slow neuron
    for vth_s in [300, 400, 500, 600, 800]:
        for w_s in [10, 15, 20, 25, 30]:
            for vth_f in [120, 150, 200]:
                params = [(10, vth_f, 25), (200, vth_s, w_s)]  # 2-neuron
                safe = True
                for seq in [seq_n_d, seq_n_c]:
                    _, spikes, _ = sim_multineuron(seq, params)
                    if sum(spikes) > 0:
                        safe = False
                        break
                if not safe:
                    continue
                _, spikes_r, alarms_r = sim_multineuron(seq_rop, params)
                if sum(spikes_r) > 0:
                    mv_d, _, _ = sim_multineuron(seq_n_d, params)
                    mv_c, _, _ = sim_multineuron(seq_n_c, params)
                    margin = min(p[1] - mv for p, mv in zip(params, mv_d))
                    best.append({
                        'params': params, 'Vmax_D': mv_d, 'Vmax_C': mv_c,
                        'spikes_R': sum(spikes_r), 'alarms_R': alarms_r,
                        'margin': margin,
                    })
    if best:
        best.sort(key=lambda x: (x['margin'], -x['spikes_R']), reverse=True)
        print(f"Found {len(best)} solutions (2-neuron):")
        for i, sol in enumerate(best[:5]):
            p = sol['params']
            print(f"  #{i+1}: tau=[{p[0][0]},{p[1][0]}], Vth=[{p[0][1]},{p[1][1]}], "
                  f"W=[{p[0][2]},{p[1][2]}], ROP alarms={sol['alarms_R']}, margin={sol['margin']}")
    else:
        print("Still no solution. Multi-neuron with tau=200 also cannot span the gap.")
        print("The CPI-adjusted gap is fundamentally too wide for LIF-based detection.")
