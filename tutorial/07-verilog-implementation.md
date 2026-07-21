# 第7课：Verilog 代码走读 —— 这三四十行代码凭什么能工作？

> **要解决的问题**：LIF 神经元在硬件上到底怎么实现？改 PicoRV32 要动哪些地方？
> **学完能干什么**：能读懂和修改本项目所有 Verilog 代码；理解 wire/reg、阻塞/非阻塞赋值等关键概念。

---

## 7.1 代码全景：一共动了哪几个文件？

| 文件 | 改动量 | 作用 |
|------|:---:|------|
| `lif_neuron.v` | 34 行（新建） | LIF 神经元核心模块 |
| `picorv32.v` | ~20 行新增 | 引出 `branch_taken`、`branch_taken_ret` 端口；加 `latched_jalr` 寄存器 |
| `testbench.v` | ~50 行修改 | ROP 攻击 FSM；LIF 输入多路选择；spike 监控 |
| `picorv32_lif_top.v` | 114 行（新建） | 综合用顶层 wrapper |

**总代码量**：净增不到 150 行。一个本科生的课程设计规模。

---

## 7.2 lif_neuron.v —— 逐行讲解

```verilog
// LIF (Leaky Integrate-and-Fire) Neuron
// Models: dV/dt = I - V/tau,  when V >= threshold -> spike & reset
module lif_neuron (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  input_current,   // input current (integer)
    output reg         spike,           // output spike pulse
    output wire [15:0] V_out            // membrane potential (for debug)
);
```

**第 1-9 行**：模块声明。
- `clk`：时钟信号。所有 `always @(posedge clk)` 都靠它驱动。100MHz（周期 10ns）。
- `rst_n`：复位（低有效）。`_n` 后缀表示 active-low。`rst_n=0` 时，所有状态归零。
- `input_current`：8 位输入电流。我们不传浮点数——直接传整数（0 或 30）。
- `spike`：1 位输出。`output reg` 表示它在 `always` 块里用 `<=` 赋值。
- `V_out`：16 位膜电位，调试用。`output wire` 表示用 `assign` 连续赋值。

```verilog
    reg [15:0] V;                        // membrane potential
    assign V_out = V;
    localparam THRESHOLD = 100;          // firing threshold
    localparam TAU = 24;                 // leak time constant (RET-only tuned)
```

**第 11-14 行**：内部变量和参数。
- `reg [15:0] V`：16 位寄存器。这是神经元的"水桶"——膜电位。
- `assign V_out = V`：把内部寄存器连接到输出端口，方便调试时看波形。
- `localparam`：编译时常量。不占硬件资源——综合时直接替换成数字。

**为什么 V 是 16 位？** 最大值不会超几百（阈值才 100），但怕万一程序异常产生持续高输入导致溢出，16 位（最大 65535）足够安全。

```verilog
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            V     <= 16'd0;
            spike <= 1'b0;
        end else begin
```

**第 16-20 行**：时序逻辑块。
- `always @(posedge clk or negedge rst_n)`：在时钟上升沿或复位下降沿触发。这是带异步复位的时序逻辑标准写法。
- `!rst_n`：复位条件优先。复位时 V=0，spike=0。
- `<=`：**非阻塞赋值**。所有 `<=` 在当前时钟周期结束时同时生效。这是时序逻辑的黄金法则——如果你用 `=`（阻塞赋值），综合出来的电路可能有时序问题。

```verilog
            if (V + input_current - (V / TAU) >= THRESHOLD) begin
                V     <= 16'd0;          // reset after spike
                spike <= 1'b1;
            end else begin
                V     <= V + input_current - (V / TAU);
                spike <= 1'b0;
            end
        end
    end
```

**第 21-30 行**：核心计算。
- `V + input_current - (V / TAU)`：先算下一时刻的膜电位。`V / TAU` 是整数除法（截断）。
- 如果 >= 100：发放。V 重置为 0，spike 拉高一个周期。
- 如果 < 100：更新 V，spike 低。

**注意**：spike 只持续 1 个时钟周期（10ns）。下一周期 V=0，spike 自动回 0。这不是锁存告警——要让告警持续，需要在外面接一个锁存器。

**为什么在 if 条件里算了一次 V_next，在 else 分支又算了一次？** 因为 Verilog 不支持把计算结果存到临时变量（在 always 块里可以是 reg，但不能在这用 wire 连续赋值）。综合工具会自动识别这是同一个表达式，只生成一份硬件。

---

## 7.3 关键 Verilog 概念速成

### wire vs reg

| 特性 | `wire` | `reg` |
|------|--------|-------|
| 赋值方式 | `assign`（连续赋值） | `<=` 或 `=`（在 always 块内） |
| 含义 | 组合逻辑——线网，值随时变化 | 时序逻辑——触发器，只在时钟沿变化 |
| 对应硬件 | 导线 / LUT 输出 | 触发器（FF） |
| 能存值吗？ | 不能 | 能（每个 reg 至少 1 个 FF） |

**速记**："wire 是铁丝，reg 是记忆。"

### 阻塞赋值 `=` vs 非阻塞赋值 `<=`

```verilog
// 阻塞赋值：顺序执行，上面写完下面立即可见
a = 1;
b = a;   // b = 1（a 的值已经更新了）

// 非阻塞赋值：并行执行，所有右边先算完，再同时写入左边
a <= 1;
b <= a;  // b = a 的旧值（a 还没更新）
```

**时序逻辑（always @(posedge clk)）里永远用 `<=`**。组合逻辑（always @(*)）里用 `=`。这是 Verilog 新手最容易踩的坑。

### localparam vs parameter

- `localparam`：模块内部常量，外部不可改写。
- `parameter`：可被实例化时覆盖（如 `lif_neuron #(.TAU(32)) uut (...)`）。

我们用 `localparam`，因为 tau=24 是经过参数搜索确定的，不希望被误改。

---

## 7.4 picorv32.v 的改动 —— 最小侵入

PicoRV32 有 3000+ 行代码。我们只动了约 20 行：

**1. 端口声明（第 165-168 行）**：
```verilog
output wire branch_taken,
output wire branch_taken_ret
```
在模块端口列表里加了两个输出。

**2. 新寄存器（第 1219 行）**：
```verilog
reg latched_jalr;
```

**3. 信号赋值（第 1224-1225 行）**：
```verilog
assign branch_taken = latched_branch;
assign branch_taken_ret = latched_branch && latched_jalr;
```

**4. 在译码阶段捕获 JALR（第 1552 行）**：
```verilog
latched_jalr <= instr_jalr;
```

**5. axi wrapper 传递（第 2629-2746 行）**：
在 `picorv32_axi` 模块中增加 passthrough 端口，把 `branch_taken` 和 `branch_taken_ret` 从核心传到顶层。

**原则**：不修改任何已有的状态机、不改变任何时序路径。只在已有信号上"搭线"。

---

## 7.5 testbench.v 的改动 —— ROP FSM + LIF 集成

**1. 端口声明新增**：
```verilog
wire branch_taken_ret;
wire lif_spike;
wire [15:0] lif_V;
```

**2. ROP 攻击 FSM**：在 `picorv32_wrapper` 里加了一个小型状态机（约 60 行）。
- `rop_gadget_len[0:14]`：15 个 gadget 的 CPI 修正长度（9-18 周期）
- `rop_gadget_idx`：当前是第几个 gadget（0-14）
- `rop_cycle_in_gadget`：当前 gadget 里的进度
- `rop_active`：攻击窗口标记（200000-201620 周期）

**3. LIF 输入多路选择**：
```verilog
assign lif_input = rop_branch ? 8'd30 : (branch_taken_ret ? 8'd30 : 8'd0);
```
优先看 FSM 产生的 ROP 脉冲，如果没有 ROP 活动，就看真实的 CPU RET 信号。

**4. Spike 监控**：
```verilog
always @(posedge clk) begin
    if (resetn && lif_spike) begin
        spike_count <= spike_count + 1;
        $display("LIF SPIKE #%0d at cycle %0d, V=%0d",
                 spike_count + 1, sim_cycle, lif_V);
    end
end
```

---

## 7.6 picorv32_lif_top.v —— 综合用顶层 wrapper

这个文件的作用是把 PicoRV32 + LIF 包成一个可以用 Yosys 综合的单一模块。

关键代码：

```verilog
// RET-qualified branch events, weight=30, tau=24, V_th=100
wire [7:0] lif_input;
assign lif_input = branch_taken_ret ? 8'd30 : 8'd0;

lif_neuron lif (
    .clk          (clk),
    .rst_n        (resetn),
    .input_current(lif_input),
    .spike        (lif_spike),
    .V_out        (lif_V)
);
```

**为什么需要单独的 wrapper？**
- testbench.v 是仿真用的，里面有时钟生成、内存、文件读取等不可综合的东西。
- 综合工具（Yosys）只能综合纯硬件描述。
- 因此需要把 PicoRV32 + LIF 单独包一层，去掉仿真部分。

---

## 7.7 代码量总结

```
lif_neuron.v:       34 行 （核心：V = V + I - V/TAU）
picorv32.v:         ~20 行新增 （端口 + latched_jalr + assign）
testbench.v:        ~50 行新增/修改 （ROP FSM + LIF 集成）
picorv32_lif_top.v: 114 行 （综合 wrapper）
─────────────────────────────────────
总共:               ~150 行新代码
```

一个空调遥控器的固件都比这长。

---

## 7.8 思考题

1. `always @(posedge clk or negedge rst_n)` 中，为什么是 `negedge rst_n` 而不是 `posedge rst_n`？如果写成 `posedge rst_n`，复位行为会有什么变化？
2. `V + input_current - (V / TAU) >= THRESHOLD` 这个条件中，综合工具实际上生成了什么硬件？（提示：加法器、比较器、除法器、减法器各需要几个？）
3. 如果把 `spike` 从 `output reg` 改成 `output wire`，代码要怎么改？哪种写法更省硬件？

---

**下一课**：[第8课：实验与消融](08-experiments-and-ablation.md) —— 怎么用实验证明你的方案真的有效？
