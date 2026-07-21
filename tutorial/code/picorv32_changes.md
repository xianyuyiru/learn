# PicoRV32 修改清单

## 新增信号（3个）

### 1. branch_taken (输出端口)
```verilog
// picorv32.v:165
output wire branch_taken
// picorv32.v:1221
assign branch_taken = latched_branch;
```
所有已提交的分支（JAL/JALR/BEQ等），组合逻辑直接引出。

### 2. branch_taken_ret (输出端口)
```verilog
// picorv32.v:167
output wire branch_taken_ret
// picorv32.v:1222
assign branch_taken_ret = latched_branch && latched_jalr;
```
仅 RET/JALR 分支。AND 门将 latched_branch 限定为 JALR 指令。

### 3. branch_counter (输出端口)
```verilog
// picorv32.v:162
output reg [31:0] branch_counter
// picorv32.v:1540
if (latched_branch) branch_counter <= branch_counter + 1;
```
32位分支计数器（仅用于实验统计，正式芯片可去掉）。

## 新增内部寄存器（1个）

### latched_jalr
```verilog
// picorv32.v:1217
reg latched_jalr;
// picorv32.v:1547
latched_jalr <= instr_jalr;  // 在fetch状态锁存
```
捕获当前指令是否为 JALR，在执行阶段与 latched_branch 组合产生 branch_taken_ret。

## picorv32_axi 包装器透传

```verilog
// picorv32.v:2630-2631
output wire branch_taken,
output wire branch_taken_ret
// picorv32.v:2745-2746
.branch_taken(branch_taken),
.branch_taken_ret(branch_taken_ret)
```

## 硬件成本

| 新增项 | 硬件 | 说明 |
|--------|------|------|
| latched_jalr | 1 FF | 1位寄存器 |
| branch_taken_ret AND | ~3 LUTs | 2输入AND |
| branch_counter | ~32 FFs + adder | 仅实验用 |
| **总计（不含counter）** | **~119 LUTs + 19 FFs** | 约CPU的3.2% |
