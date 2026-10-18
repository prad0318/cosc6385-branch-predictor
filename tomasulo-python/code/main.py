# Qing 
# 21st May 2017 

import sys
from copy import deepcopy
from collections import deque, namedtuple
from init import read_instruction, build_rs, ld_sd_entry, ld_sd_exe, ld_sd_mem, cdb, ROB_entry, PC
from print_status import ps, pss
from issue import issue, check_rs_space
from exe import exe 
from mem import mem
from wb import wb 
from commit import commit
'''initialize'''
# added by me: input file and issue width
# usage: python main.py [input_file] [issue_width]
# the input file can also have a line like "Issue width = 2"
# and init lines like "R1=12, R2=32, F20=3.0" and "Mem[4]=3.0, Mem[8]=2.0"
input_file = 'code.in'
if len(sys.argv) > 1:
    input_file = sys.argv[1]
issue_width = 1
size_ROB = 64
lines = read_instruction(input_file)
instructions = []
init_lines = []
for line in lines:
    line = line.strip()
    if line == '' or line[0] == '#':
        continue
    if '=' in line:
        if line.lower().startswith('issue width'):
            issue_width = int(line.split('=')[1])
        elif line.lower().startswith('rob entries'):
            size_ROB = int(line.split('=')[1])
        else:
            init_lines.append(line)
    else:
        instructions.append(line)
if len(sys.argv) > 2:
    issue_width = int(sys.argv[2])   # command line wins
if issue_width < 1:
    issue_width = 1
if issue_width > 4:
    issue_width = 4

'''initialize regs, RAT, memory''' 
reg_int = []
for i in range(32):
    reg_int.extend([0])
reg_fp = []
for i in range(32):
    reg_fp.extend([0])
memory = []
for i in range(256):
    memory.extend([0])
if len(init_lines) == 0:
    # same default values as the original code
    reg_int[1] = 12
    reg_int[2] = 32
    reg_fp[20] = 3.0
    memory[4] = 3.0
    memory[8] = 2.0
    memory[12] = 1.0
    memory[24] = 6.0
    memory[28] = 5.0
    memory[32] = 4.0
else:
    # read the init values from the input file, everything else stays 0
    for line in init_lines:
        for part in line.split(','):
            part = part.strip()
            if part == '':
                continue
            name = part.split('=')[0].strip()
            value = part.split('=')[1].strip()
            if name.startswith('Mem'):
                addr = int(name[name.index('[')+1:name.index(']')])
                memory[addr] = float(value)
            elif name[0] == 'R':
                reg_int[int(name[1:])] = int(value)
            elif name[0] == 'F':
                reg_fp[int(name[1:])] = float(value)
reg_int[0] = 0   # R0 is always 0
rat_int = deepcopy(reg_int)
rat_fp = deepcopy(reg_fp)
'''intialize reservation stations'''
# 2 integer adder rs 
size_rs_int_adder = 4 
rs_int_adder = build_rs(size_rs_int_adder)
# 3 fp adder rs
size_rs_fp_adder = 3
rs_fp_adder = build_rs(size_rs_fp_adder)
# 2 fp multiplier rs
size_rs_fp_multi = 2
rs_fp_multi = build_rs(size_rs_fp_multi)
'''initilize function unit'''
# 1 cycle in int adder 
fu_int_adder = deque()
time_fu_int_adder = 1
# 3 cycles in fp adder 
fu_fp_adder = deque()
time_fu_fp_adder = 4
# 20 cycles in fp multiplier
fu_fp_multi = deque()
time_fu_fp_multi = 15
'''initialize load/store queue'''
ld_sd_queue = deque()
size_ld_sd_queue = 5 
ld_sd_exe = ld_sd_exe()
ld_sd_exe.busy = 0
time_ld_sd_exe = 1
ld_sd_mem = ld_sd_mem()
ld_sd_mem.busy = 0
time_ld_sd_mem = 5
'''initialize ROB'''
ROB = deque()
'''initialize CDB'''
results_buffer = deque()
# changed by me: one cdb per issue slot (up to 4)
cdb_list = []
for i in range(4):
    temp = cdb()
    temp.valid = 0
    cdb_list.append(temp)
"""issue first instruction"""
# instruction pointer 
PC = PC()
PC.PC = 0
PC.valid = 1 
cycle = 1

print('Input file: ' + input_file + '   Issue width: ' + str(issue_width))
print('')
# print title 
item = ''.ljust(30)
item += 'ISSUE'.ljust(15)
item += 'EXE'.ljust(15)
item += 'MEM'.ljust(15)
item += 'WB'.ljust(15)
item += 'COMMIT'.ljust(15)
print (item)

# main
# fixed by me: also keep going while a store is still writing to memory,
# otherwise the last store can get lost when the ROB empties first
while (len(ROB)>0)|(cycle==1)|(ld_sd_mem.busy==1)|(len(ld_sd_queue)>0):
    
    '''ISSUE stage'''
    if (PC.PC<len(instructions))&(PC.valid==1):
        issue(cycle, PC, instructions, ROB, size_ROB, 
                rs_int_adder, 
                rs_fp_adder, 
                rs_fp_multi, 
                ld_sd_queue, size_ld_sd_queue, 
                rat_int, rat_fp, issue_width)

    '''EXE stage'''
    exe(fu_int_adder, time_fu_int_adder, 
        fu_fp_adder, time_fu_fp_adder, 
        fu_fp_multi, time_fu_fp_multi, results_buffer,  
        rs_int_adder, rs_fp_adder, rs_fp_multi, 
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue,
        cycle, ROB, PC)

    '''MEM stage'''
    mem(ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer,
        memory, ROB, cycle)

    '''CDB stage'''
    wb(cdb_list, rat_int, rat_fp, 
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_queue, ROB, cycle,
        results_buffer, issue_width) 
    
    '''COMMIT stage'''
    commit(ROB, reg_int, reg_fp, cycle, instructions, issue_width)
    
    # cycle number 
    cycle +=1

# added by me: print total cycles, registers and non zero memory like the handout asks
print('')
print('Total cycles: ' + str(cycle))
print('')
print('REGISTER VALUES')
line1 = '        '
line2 = 'value:  '
for i in range(32):
    if reg_int[i] != 0 or i < 8:
        line1 += ('R'+str(i)).ljust(8)
        line2 += str(reg_int[i]).ljust(8)
print(line1)
print(line2)
line1 = '        '
line2 = 'value:  '
for i in range(32):
    if reg_fp[i] != 0 or i < 8:
        line1 += ('F'+str(i)).ljust(8)
        line2 += str(reg_fp[i]).ljust(8)
print(line1)
print(line2)
print('')
print('NON-ZERO MEMORY VALUES')
print('Addresses     Values')
for i in range(len(memory)):
    if memory[i] != 0:
        print(str(i).ljust(14) + str(memory[i]))
