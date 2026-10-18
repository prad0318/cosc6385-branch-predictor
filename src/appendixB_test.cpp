// test for my predictor using the small example from appendix B
// runs b1 b2 b3 in the same order as the handout and checks each step
#include <stdio.h>
#include <string.h>
#include "branch.h"
#include "predictor.h"
#include "my_predictor.h"

int main () {
        unsigned int addr[3] = {0x44, 0x6C, 0x90};   // b1, b2, b3
        int seq[22]     = {0,2,0,1,2,0,2,0,1,2,0,1,0,1,2,0,2,0,1,2,0,2};
        int outcome[22] = {1,1,0,0,1,1,1,0,0,1,0,1,0,0,1,1,1,0,0,1,1,1};
        // answers copied from the table in the handout
        int exp_final[22] = {0,0,1,1,0,1,1,1,1,1,1,0,0,0,1,1,1,0,0,1,1,1};
        int exp_hit[22]   = {0,0,0,0,0,1,0,0,0,1,1,0,0,1,0,1,0,0,0,1,1,0};
        int exp_row[22]   = {0,1,0,3,2,2,1,1,1,2,2,2,1,0,0,2,1,1,1,2,2,1};
        int exp_tag[22]   = {1,1,2,1,0,0,3,2,1,0,0,1,0,1,0,0,3,2,1,0,0,3};

        pm_predictor p(4, 2, 2, 2, true);   // small version: 4 bit local, 2 row bits, 2 tag bits, use address bits 5..2
        int errors = 0;
        printf("step br  GHR  row tag  hit  final actual\n");
        for (int i = 0; i < 22; i++) {
                branch_info b; b.address = addr[seq[i]]; b.opcode = 0; b.br_flags = BR_CONDITIONAL;
                unsigned int ghr = p.ghr;
                branch_update *u = p.predict(b);
                pm_update *pu = (pm_update *) u;
                int pred = u->direction_prediction();
                int hit = pu->way >= 0;
                bool ok = pred == exp_final[i] && hit == exp_hit[i] &&
                          (int)pu->row == exp_row[i] && (int)pu->tag == exp_tag[i];
                if (!ok) errors++;
                printf("%4d  b%d  %d%d%d%d  %d   %d%d   %-4s %-5s %-5s %s\n", i+1, seq[i]+1,
                       (ghr>>3)&1,(ghr>>2)&1,(ghr>>1)&1,ghr&1, pu->row, (pu->tag>>1)&1, pu->tag&1,
                       hit ? "hit" : "-", pred ? "T" : "NT", outcome[i] ? "T" : "NT", ok ? "" : "<-- MISMATCH");
                p.update(u, outcome[i], 0);
        }
        printf("\n%s (%d mismatches out of 22 steps)\n", errors ? "FAIL" : "PASS: matches Appendix B", errors);
        return errors != 0;
}
