# 🔐 BTM-SNN：用"神经元"保护 RISC-V 芯片 —— 从零到论文的完整教程

> **说人话版**：这是一个把你从"啥是 CPU"教到"能读懂顶会安全论文"的完整课程。
> 我们复现了一篇论文的全部实验，发现了原论文的 bug，找到了正确的解法，然后把整个过程写成你正在看的这份教程。

---

## 🤔 这个项目做了什么？

**一句话**：我们在 RISC-V CPU 里放了一个仿生"神经元"，它能闻出黑客攻击的"气味"然后报警。

**稍微专业点**：我们设计了一个硬件安全监控器——把一个漏积分发放（LIF）神经元电路挂在 CPU 的分支信号上。正常程序的分支节奏像散步，ROP 攻击的分支节奏像冲刺。神经元能听出节奏不对，然后拉响警报。

**核心洞察**：别把所有的"脚步声"混在一起听。只听 RET 指令的脚步声（黑客攻击必须用 RET 来串联 gadget），信噪比从 2 倍暴涨到 14 倍。单神经元就够了。

---

## 📚 这门课怎么学？

这个教程模拟一门大学课程的体验。从零基础开始，每节课解决一个问题，层层递进。

| 课时 | 标题 | 解决的问题 | 新概念 |
|:---:|------|-----------|--------|
| 01 | [RISC-V：芯片的"语言"](01-riscv-cpu-basics.md) | CPU 怎么执行程序？ | 指令集、寄存器、取指-译码-执行 |
| 02 | [PicoRV32 内部解剖](02-picorv32-internals.md) | 这个 CPU 的"心跳"是怎样的？ | 状态机、CPI、流水线 vs 多周期 |
| 03 | [ROP 攻击：黑客的"积木"游戏](03-rop-attacks.md) | 不注入代码怎么劫持程序？ | 栈溢出、Gadget、代码复用、W⊕X |
| 04 | [LIF 神经元：硅基脑细胞](04-lif-neuron-theory.md) | 怎么用电路模拟神经元？ | 膜电位、泄漏、脉冲、时间编码 |
| 05 | [BTM-SNN 架构：把神经元挂上 CPU](05-btm-snn-architecture.md) | 神经元怎么"闻"出攻击？ | BTM 追踪、分支密度、信号编码 |
| 06 | [🔥 信号隔离：本项目的核心洞察](06-signal-isolation.md) | 为什么"只听 RET"是决定性突破？ | 密度比、噪声过滤、信息论下限 |
| 07 | [Verilog 代码逐行解读](07-verilog-implementation.md) | 代码怎么写出来的？ | 硬件描述语言、always 块、综合 |
| 08 | [实验与消融：怎么证明它真的有用？](08-experiments-and-ablation.md) | 审稿人会问什么？ | 假阳性、CPI 修正、参数搜索 |
| 09 | [FPGA 综合：从代码到芯片](09-fpga-synthesis.md) | 119 个 LUT 意味着什么？ | Yosys、iCE40、资源统计 |
| 10 | [论文写作：怎么写出诚实的论文](10-paper-writing.md) | 发现原论文有 bug 怎么办？ | 负结果、叙事重构、审稿应对 |

---

## 🎯 学完你能干什么？

- 看懂 RISC-V 汇编，理解 CPU 内部怎么跑指令
- 理解 ROP 攻击的原理和防御思路
- 理解 SNN 神经元的基本数学模型
- 能读 Verilog 代码，知道 FPGA 综合是什么
- 掌握做实验的完整方法论（假阳性/真阳性/CPI 修正/消融实验）
- **最重要的是**：学会怎么诚实地报告负结果，把"翻车"变成"贡献"

---

## 🛠 环境准备

如果你想自己跑一遍代码：

```bash
# 你需要：
# 1. Python 3.8+
# 2. Icarus Verilog (用于 Verilog 仿真) — 可选，Python 模型已验证等价
# 3. RISC-V 交叉编译器 (用于编译固件) — 可选，已提供预编译固件

# 克隆仓库
git clone https://github.com/YOUR_USERNAME/btm-snn-tutorial.git
cd btm-snn-tutorial

# 先跑 Python 模型（不需要任何硬件/仿真器）
python3 code/lif_sim.py                    # LIF 神经元基础模拟
python3 code/adversarial_analysis.py        # 对抗分析
python3 code/ablation_study.py             # 消融实验

# 如果需要跑 Verilog 仿真（需要安装 Icarus Verilog）
iverilog -DCOMPRESSED_ISA -o testbench.vvp testbench.v picorv32.v lif_neuron.v
vvp -N testbench.vvp
```

---

## 📖 适合谁读？

- 🎓 **学生**：想入门硬件安全但不知道怎么上手
- 🔬 **研究者**：想复现论文但被代码劝退
- 💻 **嵌入式工程师**：想了解 CPU 安全监控
- 🤖 **AI 从业者**：想了解 SNN 在安全领域的应用
- 🤔 **任何人**：想理解"芯片怎么防黑客"这个问题的答案

---

## ⭐ 这个项目酷在哪？

1. **发现了原论文的 bug**：原论文声称"100% 检测"，我们复现发现——它把 CPU 的指令数当周期数用了。修正后检测直接失败。这是审稿人能拒稿的硬伤。

2. **找到了正确的解法**：不是加更多神经元（我们试了，不行），而是换一个更好的输入信号。RET-only 信号把信噪比从 2 倍提到 14 倍。

3. **做了完整的消融实验**：信号源、CPI 因子、检测器类型、参数灵敏度——四个维度全扫了一遍，证明 LIF + RET-only 是唯一同时零假阳性且检测 ROP 的方案。

4. **诚实写了论文**：没有掩盖翻车，把"bug → 分析 → 修正 → 验证"的全过程写进了论文。审稿人喜欢诚实的作者。

---

## 📂 仓库结构

```
btm-snn-tutorial/
├── README.md                        # 你正在看的课程总览
├── 01-riscv-cpu-basics.md           # 第1课
├── 02-picorv32-internals.md         # 第2课
├── ...                              # ... 到第10课
├── code/
│   ├── lif_neuron.v                 # LIF 神经元 Verilog（34行！）
│   ├── picorv32_changes.md          # PicoRV32 修改说明
│   ├── testbench_changes.md         # Testbench 修改说明
│   ├── adversarial_analysis.py      # 对抗分析脚本
│   ├── ret_only_verify.py           # RET-only 验证
│   ├── ablation_study.py            # 消融实验
│   └── multi_neuron_search.py       # 多神经元搜索（负结果）
├── results/
│   ├── ablation_summary.png         # 消融实验综合图
│   ├── ablation_signal.png          # 信号源消融
│   ├── ablation_parameters.png      # 参数灵敏度
│   └── adversarial_analysis.png     # 对抗分析
└── resources/
    ├── papers.md                    # 相关论文列表
    └── glossary.md                  # 术语表
```

---

## 🙋 有问题？

每节课末尾都有"思考题"，试着回答它们。如果卡住了，可以把问题丢给 GPTLive 或者直接语音问我。

**现在，从第1课开始吧 → [01-RISC-V：芯片的"语言"](01-riscv-cpu-basics.md)**