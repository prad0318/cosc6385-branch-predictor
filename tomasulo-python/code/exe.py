# Qing 
# 24th May 2017

''' 
1. calculate valid instructions
    -- for ALU instructions, write results into fu_results, remove that fu entry  
    -- for LD/SD, write address result immediately back to ld_sd_queue
2. fetch instructions into function unit with spare space
    -- remove ALU instructions from rs
    -- don't remove ld/sd instructions
'''
from collections import deque
from init import fu_entry, fu_result

# function: check rs and return valid instruction index
def check_valid_ins_in_rs(rs):
    index = -1
    if len(rs)!=0:
        for i in range(len(rs)):
            if (rs[i].valid_1st==1)&(rs[i].valid_2nd==1)&(rs[i].busy==1):
                index = i
                break
    return index

# function: check ld_sd_queue and return valid instruction index
def check_valid_ins_in_ldsd(ldsd):
    index = -1
    if len(ldsd)!=0:
        for i in range(len(ldsd)):
            if (ldsd[i].valid==1) & (ldsd[i].ready==0):
                index = i
                break
    return index

# function: add entry into fu 
def add_entry_into_fu(fu, ins_in_rs):
    fu[-1].cycle = 0
    fu[-1].op = ins_in_rs.op
    fu[-1].value1 = ins_in_rs.value_1st
    fu[-1].value2 = ins_in_rs.value_2nd
    fu[-1].dest_tag = ins_in_rs.dest_tag

# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            break
    return index

# function: functional units execution 
def fu_exe(fu, fu_results, ROB, time_fu, cycle, PC):
    started = False
    if len(fu)!=0:
        for element in fu:
            element.cycle += 1
        # write starting cycle 
        if fu[-1].cycle == 1:
            index = find_ROB_entry(ROB, fu[-1].dest_tag)
            ROB[index].exe.append(cycle)
            started = True
        # finish cycle
        if fu[0].cycle == time_fu:
            index = find_ROB_entry(ROB, fu[0].dest_tag)
            ROB[index].exe.append(cycle)
            # calculation result
            fu_results.append(fu_result())
            fu_results[-1].dest_tag = fu[0].dest_tag
            if (fu[0].op=='Add')|(fu[0].op=='Add.d')|(fu[0].op=='Addi'):
                fu_results[-1].value = fu[0].value1 + fu[0].value2
            elif (fu[0].op=='Sub')|(fu[0].op=='Sub.d'):
                fu_results[-1].value = fu[0].value1 - fu[0].value2
            elif (fu[0].op=='Mult.d'):
                fu_results[-1].value = fu[0].value1 * fu[0].value2
            elif (fu[0].op=='Bne'):
                fu_results.pop()
                if fu[0].value1 == fu[0].value2:
                    PC.PC += 1
                    PC.valid = 1
                else:
                    index = find_ROB_entry(ROB, fu[0].dest_tag)
                    offset = ROB[index].dest_tag
                    PC.PC = int(PC.PC + 1 + offset/4)
                    PC.valid = 1
            else:
                pass
            # remove from fu 
            fu.popleft()
    return started

# function: ld_sd_execution 
def ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle):
    started = False
    if ld_sd_exe.busy == 1:
        # write down starting cycle
        if ld_sd_exe.cycle == 0:            
            for element in ld_sd_queue:
                if element.ld_sd_tag == ld_sd_exe.dest_tag:
                    break
            index = find_ROB_entry(ROB, element.dest_tag)
            ROB[index].exe.append(cycle)
            started = True
            # execute 
            ld_sd_exe.cycle += 1
        # write address back to ld_sd_queue
        if ld_sd_exe.cycle == time_ld_sd_exe:
            address = ld_sd_exe.value1 + ld_sd_exe.value2
            for element in ld_sd_queue:
                if element.ld_sd_tag == ld_sd_exe.dest_tag:
                    element.address = address
                    element.ready = 1
                    break
            # write down finish cycle
            index = find_ROB_entry(ROB, element.dest_tag)
            ROB[index].exe.append(cycle)
            ld_sd_exe.busy = 0
    return started

# function: execution
def exe(fu_int_adder, time_fu_int_adder,
        fu_fp_adder, time_fu_fp_adder,
        fu_fp_multi, time_fu_fp_multi, results_buffer,
        rs_int_adder, rs_fp_adder, rs_fp_multi, 
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue,
        cycle, ROB, PC):
    '''execution in fu and ld_sd address calculation'''
    # changed by me: remember if each unit already started something this cycle.
    # with multi issue two instructions can be ready at once, and the old code
    # could start both on the same (single) unit in one cycle
    ldsd_started = ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle) 
    # functional units 
    int_started = fu_exe(fu_int_adder, results_buffer, ROB, time_fu_int_adder, cycle, PC)
    fpadd_started = fu_exe(fu_fp_adder, results_buffer, ROB, time_fu_fp_adder, cycle, PC)
    fpmul_started = fu_exe(fu_fp_multi, results_buffer, ROB, time_fu_fp_multi, cycle, PC)
    '''fetch instructions from rs and ld_sd_queue'''
    # from ld_sd_queue
    # check valid ins in ld_sd_queue 
    index = check_valid_ins_in_ldsd(ld_sd_queue)
    # put ins into ld_sd_exe (only if the address adder didnt already start one this cycle)
    if (index>=0)&(ld_sd_exe.busy==0)&(ldsd_started==False):
        ld_sd_exe.busy = 1
        ld_sd_exe.cycle = 0
        ld_sd_exe.value1 = ld_sd_queue[index].reg_value
        ld_sd_exe.value2 = ld_sd_queue[index].immediate
        ld_sd_exe.dest_tag = ld_sd_queue[index].ld_sd_tag
        if ROB[find_ROB_entry(ROB, ld_sd_queue[index].dest_tag)].issue[0] < cycle:
            ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle)
    # from rs 
    fetch_from_rs(rs_int_adder, fu_int_adder, int_started, results_buffer, ROB, time_fu_int_adder, cycle, PC)
    fetch_from_rs(rs_fp_adder, fu_fp_adder, fpadd_started, results_buffer, ROB, time_fu_fp_adder, cycle, PC)
    fetch_from_rs(rs_fp_multi, fu_fp_multi, fpmul_started, results_buffer, ROB, time_fu_fp_multi, cycle, PC)

# added by me: same fetch code as before for each rs, just in one function
# and it skips if that unit already started an instruction this cycle
def fetch_from_rs(rs, fu, started, results_buffer, ROB, time_fu, cycle, PC):
    if started:
        return
    if check_valid_ins_in_rs(rs)>=0:
        index = check_valid_ins_in_rs(rs)
        # added by me: start the OLDEST ready instruction (smallest position in the ROB)
        # instead of whatever is in the lowest rs slot. with multi issue the rs slots get
        # reused out of order so the lowest slot is not always the oldest one
        best = -1
        for i in range(len(rs)):
            if (rs[i].busy==1)&(rs[i].valid_1st==1)&(rs[i].valid_2nd==1):
                pos = find_ROB_entry(ROB, rs[i].dest_tag)
                if best == -1 or pos < best:
                    best = pos
                    index = i
        # check if it's a waiting instruction
        if ROB[find_ROB_entry(ROB, rs[index].dest_tag)].issue[0] < cycle:
            # fixed by me: start it on its own. the old code called fu_exe on the
            # whole pipeline again, so instructions already inside got moved
            # forward twice in one cycle (an fp add took 3 cycles instead of 4)
            temp = deque()
            temp.append(fu_entry())
            add_entry_into_fu(temp, rs[index])
            fu_exe(temp, results_buffer, ROB, time_fu, cycle, PC)
            if len(temp) > 0:
                fu.append(temp[0])
        else:
            fu.append(fu_entry())
            add_entry_into_fu(fu, rs[index])
        # remove ins from rs 
        rs[index].busy = 0
