# 第5课：BTM-SNN 架构 —— 把神经元接到 CPU 上

> **要解决的问题**：从哪取信号喂给 LIF？信号怎么从 CPU 内部引出来？
> **学完能干什么**：理解整个检测系统的信号链，知道原论文的 testbench bug 出在哪，以及怎么修。

---

## 5.1 什么是 BTM？——RISC-V 的"行车记录仪"

BTM（Branch Trace Messaging）是 RISC-V N-Trace 规范里定义的调试功能。它记录 CPU 执行的每一条分支指令，就像飞机的黑匣子。

BTM 消息类型（TCODE）：

| TCODE | 含义 | 什么时候产生 |
|:---:|------|------|
| 0 | 同步点 | 程序启动/上下文切换 |
| 1 | 间接分支 | JALR（寄存器跳转） |
| 2 | 异常/中断 | trap 或 irq |
| **3** | **直接分支** | **JAL**（函数调用） |
| **4** | **条件分支** | **BEQ/BNE/BLT**（if/for/while） |

**我们不需要真正的 BTM 数据包**。我们只需要一个比特：**"这条指令是不是一个 taken branch？"**

因为 ROP 的分支密度已经足够高了——比起去解析 TCODE=4（条件分支）还是 TCODE=1（间接分支），先拿到"有没有分支"这个信号，已经能抓到有用信息。而进一步过滤到"只要 RET（TCODE=1 的一个子集）"则是第 6 课要讲的关键优化。

---

## 5.2 信号链：从 CPU 内部到 LIF 输入

整个系统只有 5 步：

```
PicoRV32 内部
  │
  ├── latched_branch  (reg, 内部寄存器)
  │       CPU 在执行跳转指令的那个周期把它拉高
  │
  ▼ assign branch_taken = latched_branch
  │
  ├── branch_taken    (wire, 输出端口)
  │       原本就有这个信号，我们只是把它引出到端口上
  │
  ▼ assign branch_taken_ret = latched_branch && latched_jalr
  │
  ├── branch_taken_ret (wire, 输出端口)
  │       只对 JALR/RET 指令拉高。比 branch_taken 干净得多
  │
  ▼ lif_input = branch_taken_ret ? 30 : 0
  │
  ├── lif_neuron 模块
  │       V = V + I - V/24; if V >= 100 → spike!
  │
  ▼ lif_spike → 报警！
```

**关键设计决策**：我们不加任何中间缓冲、FIFO、或流水线。LIF 在每个时钟周期直接采样 branch_taken_ret，零延迟。

---

## 5.3 latched_branch 是怎么产生的？——翻开 PicoRV32 源码

在 `picorv32.v` 第 1213 行附近，能看到 `latched_branch` 的定义和使用：

```verilog
reg latched_branch;

// 在译码阶段，识别出当前指令是否产生分支：
// ...（状态机代码中）...
if (instr_jal) begin
    latched_branch <= 1;   // JAL：函数调用，一定跳转
end
if (instr_jalr) begin
    latched_branch <= 1;   // JALR：函数返回/间接跳转，一定跳转
end
if (instr_beq || instr_bne || instr_blt || ...) begin
    latched_branch <= (reg_op1 == reg_op2);  // 条件分支，满足条件才跳
end
```

所以 `latched_branch` 在三种情况下拉高：
1. **JAL** — 无条件跳转（函数调用）
2. **JALR** — 无条件跳转（函数返回 / 间接调用 / ROP 的链节）
3. **条件分支** — `if`/`for`/`while` 的条件成立

每拉高一次，`branch_counter`（一个 32 位计数器）自增 1。这是我们验证用的"答案"——数一数整个仿真期间产生了多少次分支。

---

## 5.4 latched_jalr：一行寄存器，打开 RET-only 的大门

在 `picorv32.v` 第 1219 行：

```verilog
reg latched_jalr;     // RET-only signal: latched_branch qualified by JALR
```

在第 1552 行：

```verilog
latched_jalr <= instr_jalr;
```

然后在第 1225 行：

```verilog
assign branch_taken_ret = latched_branch && latched_jalr;
```

**就这么简单**。一个 AND 门，把"是分支吗？"和"是 JALR 吗？"两个信号求与。结果就是：只有 JALR/RET 指令产生的分支才会让 `branch_taken_ret` 拉高。条件分支和 JAL 全部被滤掉。

**硬件代价**：1 个 FF（latched_jalr）+ 1 个 AND 门，约 2 个 LUT。

---

## 5.5 系统架构图：一图胜千言

```
┌─────────────────────────────────────────────────────────────────┐
│                        PicoRV32 Core                            │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐              │
│  │ 取指(IF)  │───→│ 译码(ID)  │───→│ 执行(EX)     │              │
│  │          │    │          │    │ latched_branch│              │
│  └──────────┘    └──────────┘    │ latched_jalr  │              │
│                                   └──────┬───────┘              │
│                                          │                       │
│                    ┌─────────────────────┼──────────────────┐   │
│                    │ branch_taken        │ branch_taken_ret │   │
│                    │ (全部3种分支)        │ (只有JALR)       │   │
│                    └────────┬────────────┼──────────────────┘   │
└─────────────────────────────┼────────────┼──────────────────────┘
                              │            │
                              │            ▼
                              │     ┌─────────────┐
                              │     │ LIF 神经元   │
                              │     │ W=30 tau=24 │
                              │     │ V_th=100    │
                              │     └──────┬──────┘
                              │            │
                              │     ┌──────▼──────┐
                              │     │  lif_spike  │ → 报警
                              │     └─────────────┘
                              │
                              ▼
                     (忽略，全分支信号
                      只是用来对比的)
```

**核心原则**：LIF 相对 CPU 完全并行。CPU 该干嘛干嘛，LIF 在旁路"偷听"分支信号。零延迟、零侵入。

---

## 5.6 原论文的 testbench bug：CPI=1 假设从哪来？

原论文的 testbench 里有一个 FSM（有限状态机）来模拟 ROP 攻击。它用一个查找表（LUT）定义了每个 gadget 的指令条数：

```verilog
// 原论文的 bug 版本：
rop_gadget_len[0] = 3;  // 3条指令的gadget → 按 3 个周期算
rop_gadget_len[1] = 4;  // 4条指令的gadget → 按 4 个周期算
```

**问题**：写这个 testbench 的人假设 CPI=1——每条指令 1 个周期。这在流水线 CPU（如 ARM Cortex-M）上是合理的。但 **PicoRV32 是多周期 CPU**。

PicoRV32 上：
- JALR/RET = 3 个周期（fetch + ld_rs1 + exec）
- 条件分支 = 3 个周期
- gadget 里的其他指令（add/lw 等）= 3-5 个周期

**正确的算法**：gadget 长度（指令数）x 3（CPI）= 实际周期数。

---

## 5.7 CPI 修正：改了之后发生了什么坏事（和好事）

修正后的 LUT：

```verilog
rop_gadget_len[0]  = 9;   // 3 instr × 3 CPI
rop_gadget_len[1]  = 12;  // 4 instr × 3 CPI
rop_gadget_len[2]  = 6;   // 2 instr × 3 CPI
// ...
rop_gadget_len[13] = 18;  // 6 instr × 3 CPI
rop_gadget_len[14] = 12;  // 4 instr × 3 CPI
```

攻击窗口从 540 个周期扩大到 1620 个周期（10 遍链）。

**修正后**：

| 指标 | 修正前（CPI=1） | 修正后（CPI=3） |
|------|:---:|:---:|
| 攻击期分支密度 | 0.278/cycle | 0.094/cycle |
| 密度比（攻击/正常） | **6.7x** | **2.2x** |
| 单神经元检测 | 检测到 11 次 | **0 次** |

**结论**：修正 CPI 后，单神经元全分支信号彻底失效。这直接催生了第 6 课的 RET-only 方案。

---

## 5.8 另一个隐藏的 testbench 问题：CPU 和攻击同时跑

在原论文的 testbench 中，ROP 攻击发生在 200000 到 200050 周期，但这个期间 **CPU 仍然在正常运行固件（Dhrystone）**。

这意味着攻击窗口内的分支密度是：
```
ROP FSM 产生的脉冲 + 正常固件产生的分支 = 叠加态
```

在真实攻击中，一旦 ROP 劫持了控制流，CPU 只执行 ROP 的 gadget，不会同时跑正常程序。

**这个"叠加态"给了原论文虚假的检测成功率**。ROP 脉冲 + 正常分支的叠加密度刚好超过了阈值，造成"能检测到"的假象。

我们的 Python 复现实验证实了这一点：
- ROP 单独跑：V_max=50，0 次发放（原参数下）
- ROP + 正常程序叠加：V_max=95，偶尔发放

---

## 5.9 Python 模型 = Verilog 的精确复制品

我们的所有参数搜索和实验都基于 Python 模型，但关键是：**Python 模型和 Verilog 的行为完全一致**。

验证一致性的三个保证：

1. **相同的整数除法**：Python 用 `V // tau`，Verilog 用 `V / TAU`（都是截断）
2. **相同的更新顺序**：先算 `V_next`，再判断阈值，再决定重置
3. **相同的位宽语义**：V 是 16 位，Python 里最大值限制在 65535 以下

实际对比（VCD 波形 vs Python trace）：完全吻合，无任何偏差。

---

## 5.10 思考题

1. 为什么要把 `branch_taken` 从 `latched_branch` 直接引出，而不是另造一个信号？这样做的好处是什么？
2. testbench 的 FSM 里，`rop_cycle_in_gadget == rop_gadget_len[idx] - 1` 这个条件为什么是 `-1`？这和 gadget 的 RET 指令对应什么？
3. 如果让你设计一个更真实的 ROP 模拟方案（不依赖 FSM），你会怎么做？难点在哪？

---

**下一课**：[第6课：RET-Only 突破](06-signal-isolation.md) —— 怎么用"只听函数返回"把信噪比从 2.2 倍炸到 13.7 倍？
