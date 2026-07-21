# 推荐阅读

## 必读（理解本项目必需）

1. **PicoRV32 官方文档**
   - C. Wolf, "PicoRV32 — A Size-Optimized RISC-V CPU"
   - [GitHub](https://github.com/YosysHQ/picorv32)
   - 读 README.md 的 "Verilog Module Parameters" 和 "Cycles per Instruction Performance" 两节

2. **RISC-V 指令集手册（卷1：用户级ISA）**
   - RISC-V International
   - 读第2章（RV32I 基本指令集），约30页
   - [官网下载](https://riscv.org/technical/specifications/)

3. **ROP 攻击经典论文**
   - R. Roemer et al., "Return-Oriented Programming: Systems, Languages, and Applications", ACM TISSEC, 2012
   - 读 Section 2-3（攻击模型和 gadget 构造）

4. **LIF 神经元理论**
   - W. Gerstner et al., "Neuronal Dynamics", Cambridge UP, 2014
   - 读 Chapter 1（神经元模型基础），免费在线版：[neuronaldynamics.epfl.ch](https://neuronaldynamics.epfl.ch/)

## 进阶（深入某个方向）

5. **RISC-V N-Trace 规范**
   - RISC-V International, "N-Trace Specification v1.0", 2024
   - 理解 BTM (Branch Trace Messaging) 的 TCODE 格式

6. **影子栈 CFI**
   - RISC-V International, "Zicfiss and Zicfilp CFI Extensions", v0.4, 2024
   - 理解硬件 CFI 的 ISA 扩展方案

7. **Yosys 综合**
   - S. Tolley et al., "Yosys Open Synthesis Suite"
   - [GitHub](https://github.com/YosysHQ/yosys)
   - 读 synth_ice40 命令的文档

8. **硬件安全检测综述**
   - D. Bove and L. Panzer, "R5Detect", arXiv:2404.03771, 2024
   - HPC-based 检测方案的对比

## 我们这个项目的论文

9. **BTM-SNN 最终版**
   - 本仓库 `results/paper_tcasii.md`
   - 读 Section 2.2（RET 限定信号）、Section 3.3（RET 限定 ROP 检测）、Section 3.10（消融实验）
