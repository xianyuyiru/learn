# 术语表

## RISC-V / CPU
- **ISA (Instruction Set Architecture)**：指令集架构。CPU 能理解的"语言"。
- **RV32I**：RISC-V 最基本的 32 位整数指令集，40 条指令。
- **RV32IMC**：I=基本整数, M=乘除法, C=压缩指令（16位）。
- **寄存器**：CPU 内部的"草稿纸"，32 个 32 位的存储单元。
- **PC (Program Counter)**：程序计数器，指向当前正在执行的指令地址。
- **CPI (Cycles Per Instruction)**：每条指令平均消耗的时钟周期数。
- **流水线 (Pipeline)**：多个指令同时在 CPU 的不同阶段执行。PicoRV32 不是流水线。
- **多周期 (Multi-cycle)**：同一时刻只有一条指令在 CPU 里，PicoRV32 的类型。
- **one-hot 编码**：状态机编码方式，N 个状态用 N 位表示，每次只有一位是 1。

## 安全
- **ROP (Return-Oriented Programming)**：返回导向编程。利用程序中已有的以 ret 结尾的代码片段（gadget）组合成攻击链。
- **JOP (Jump-Oriented Programming)**：面向跳转编程。用间接跳转代替 ret 来串联 gadget。
- **COOP (Counterfeit Object-Oriented Programming)**：利用 C++ 虚函数表劫持控制流。
- **Gadget**：ROP 攻击的"积木块"——以 ret 结尾的短指令序列。
- **DEP / W⊕X**：数据执行保护。内存页要么可写，要么可执行，不能同时。
- **影子栈 (Shadow Stack)**：在"影子"区域存储一份返回地址副本，ret 时比对防止篡改。
- **CFI (Control Flow Integrity)**：控制流完整性。确保程序执行路径符合预期。

## SNN / LIF
- **SNN (Spiking Neural Network)**：脉冲神经网络。信息编码在脉冲的时间序列里，而非连续数值。
- **ANN (Artificial Neural Network)**：传统人工神经网络。信息编码在浮点数值里。
- **LIF (Leaky Integrate-and-Fire)**：漏积分发放模型。最简单的 SNN 神经元。
- **膜电位 V**：神经元的"水位"，输入脉冲让它上升，泄漏让它下降。
- **脉冲 (Spike)**：当膜电位超过阈值时，神经元"发放"一次。
- **时间常数 τ (tau)**：控制泄漏速度。τ 越大，记忆越长。
- **频率编码 (Rate Coding)**：信息编码在脉冲的频率（密度）里。本项目用的就是这种。

## 硬件 / FPGA
- **FPGA (Field-Programmable Gate Array)**：现场可编程门阵列。可以"重新布线"的芯片。
- **LUT (Look-Up Table)**：查找表。FPGA 的基本逻辑单元。iCE40 使用 LUT4（4 输入）。
- **FF (Flip-Flop)**：触发器。存储 1 位状态的硬件单元。
- **Yosys**：开源 Verilog 综合工具。把 Verilog 代码变成门级网表。
- **Icarus Verilog (iverilog)**：开源 Verilog 仿真器。
- **综合 (Synthesis)**：把 RTL 代码转换为门级网表的过程。
- **关键路径 (Critical Path)**：电路中延迟最长的组合逻辑路径，决定最大时钟频率。
- **BRAM (Block RAM)**：FPGA 上的专用存储块。

## 实验方法论
- **假阳性 (False Positive)**：正常程序被误报为攻击。
- **假阴性 (False Negative)**：真实攻击未被检测到。
- **消融实验 (Ablation Study)**：逐个移除/修改组件，测量每个组件对最终性能的贡献。
- **ROC 曲线**：展示检测率和假阳性率之间 trade-off 的曲线。
- **稳态分析 (Steady-State Analysis)**：推导系统在恒定输入下的长期行为。
