// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
#define HISTORY_LENGTH	15
#define TABLE_BITS	15
	gshare_update u;
	branch_info bi;
	unsigned int history;
	unsigned char tab[1<<TABLE_BITS];

	gshare_predictor (void) : history(0) { 
		memset (tab, 0, sizeof (tab));
	}

	branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			u.index = 
				  (history << (TABLE_BITS - HISTORY_LENGTH)) 
				^ (b.address & ((1<<TABLE_BITS)-1));
			u.direction_prediction (tab[u.index] >> 1);
		} else {
			u.direction_prediction (true);
		}
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *u, bool taken, unsigned int target) {
		if (bi.br_flags & BR_CONDITIONAL) {
			unsigned char *c = &tab[((gshare_update*)u)->index];
			if (taken) {
				if (*c < 3) (*c)++;
			} else {
				if (*c > 0) (*c)--;
			}
			history <<= 1;
			history |= taken;
			history &= (1<<HISTORY_LENGTH)-1;
		}
	}
};

//
// Pentium M hybrid branch predictors
// This class implements a simple hybrid branch predictor based on the Pentium M branch outcome prediction units. 
// Instead of implementing the complete Pentium M branch outcome predictors, the class below implements a hybrid 
// predictor that combines a bimodal predictor and a global predictor. 
class pm_update : public branch_update {
public:
        unsigned int index;   // which local counter we looked at
        unsigned int row;     // which row of the global table
        unsigned int tag;     // tag we compared against the 2 ways
        int way;              // way that matched, -1 means global missed
};

// Pentium M style hybrid predictor (bimodal + global)
//
// how i think about it:
// - the local table only knows "what does THIS branch usually do"
// - the global table knows "what does this branch do given what just happened",
//   because it mixes the branch address with the ghr (history of the last few branches)
// - global is more specific, so if it has an entry we trust it. if not we fall back to local
//
// sizes are parameters so the same code can run the tiny appendix B example
// (4 bit local index, 2 row bits, 2 tag bits) and check every step against the handout
class pm_predictor : public branch_predictor {
public:
        pm_update u;
        branch_info bi;

        int localBits, rowBits, tagBits, shift;

        // ghr = global history register. not a counter, just the last few outcomes
        // as bits (1 = taken, 0 = not taken), newest bit on the right
        unsigned int ghr;

        unsigned char *localTable;  // 2 bit counters, one per local index
        unsigned char *ctr[2];      // global counters for way 0 and way 1
        unsigned int *tags[2];      // tag stored in each way
        bool *valid[2];             // empty entries can't hit
        unsigned char *lru;         // per row, which way gets replaced next

        // real run: 4096 local counters and 1024 rows x 2 ways with 6 bit tags
        // (close to real pentium m sizes)
        //
        // experiments i ran, changing one thing at a time (avg MPKI over 20 traces):
        //   lb rb tb sh
        //   12 10  6  0   7.861   <- what i submitted
        //   13 10  6  0   7.746   bigger local table, small gain
        //   14 10  6  0   7.674   4x local table, still only ~2% better
        //   12 11  6  0   7.178   more global rows, biggest gain (~9%)
        //   12  9  6  0   8.661   fewer global rows, worse
        //   12 10  4  0   7.989   shorter tags = shorter history, more collisions
        //   12 10  8  0   8.182   longer tags = history too specific, entries rarely reused
        //   12 10  6  2   8.181   appendix B style address bits, worse on x86
        // so the global table runs out of room first (like conflict misses in a 2 way cache)
        pm_predictor(int lb = 12, int rb = 10, int tb = 6, int sh = 0, bool example = false) {
                localBits = lb;
                rowBits = rb;
                tagBits = tb;
                shift = sh;
                ghr = 0;

                int numLocal = 1 << localBits;   // 2^bits entries
                int numRows = 1 << rowBits;

                localTable = new unsigned char[numLocal];
                lru = new unsigned char[numRows];
                for (int w = 0; w < 2; w++) {
                        ctr[w] = new unsigned char[numRows];
                        tags[w] = new unsigned int[numRows];
                        valid[w] = new bool[numRows];
                }

                // appendix B gives specific starting counters, otherwise start at 2 (weakly taken)
                for (int i = 0; i < numLocal; i++) {
                        if (example) localTable[i] = i % 4;   // 0,1,2,3,0,1,...
                        else localTable[i] = 2;
                }

                for (int r = 0; r < numRows; r++) {
                        lru[r] = 0;   // way 0 is the first one to get filled
                        for (int w = 0; w < 2; w++) {
                                valid[w][r] = false;
                                tags[w][r] = 0;
                        }
                        if (example) {
                                ctr[0][r] = r % 4;       // way 0 starts 0,1,2,3
                                ctr[1][r] = 3 - r % 4;   // way 1 starts 3,2,1,0
                        } else {
                                ctr[0][r] = 2;
                                ctr[1][r] = 2;
                        }
                }
        }

        ~pm_predictor() {
                delete[] localTable;
                delete[] lru;
                for (int w = 0; w < 2; w++) {
                        delete[] ctr[w];
                        delete[] tags[w];
                        delete[] valid[w];
                }
        }

        // 2 bit counter: 0,1 = predict not taken, 2,3 = predict taken
        // needs two wrong guesses in a row to flip, so a loop exit only costs 1 miss
        void updateCounter(unsigned char &c, bool taken) {
                if (taken && c < 3) c++;
                if (!taken && c > 0) c--;
        }

        branch_update *predict(branch_info &b) {
                bi = b;

                if (b.br_flags & BR_CONDITIONAL) {
                        // appendix B uses address bits 5..2 (shift 2). for the x86 traces
                        // i use shift 0 since x86 instructions aren't 4 byte aligned
                        unsigned int addr = b.address >> shift;

                        // local: low address bits pick the counter
                        // e.g. b1 = 0x44 = 0100 0100, bits 5..2 = 0001 -> local index 1
                        u.index = addr % (1 << localBits);
                        bool localPred = localTable[u.index] >= 2;

                        // global: XOR the address bits with the ghr bit by bit
                        // (same bit -> 0, different -> 1). same branch with a different
                        // history ends up in a different entry
                        unsigned int x = (addr ^ ghr) % (1 << (rowBits + tagBits));
                        u.row = x >> tagBits;          // top bits = row
                        u.tag = x % (1 << tagBits);    // bottom bits = tag
                        // e.g. 1101 -> row 11 = 3, tag 01

                        // going to a row isn't a hit by itself, one of the 2 ways
                        // has to be valid AND have the same tag (like a 2 way cache)
                        u.way = -1;
                        for (int w = 0; w < 2; w++) {
                                if (valid[w][u.row] && tags[w][u.row] == u.tag)
                                        u.way = w;
                        }

                        // final prediction: global if it hit, local if it missed
                        if (u.way != -1)
                                u.direction_prediction(ctr[u.way][u.row] >= 2);
                        else
                                u.direction_prediction(localPred);
                } else {
                        u.direction_prediction(true);   // unconditional branches always go
                }

                u.target_prediction(0);   // target prediction is not part of this assignment
                return &u;
        }

        void update(branch_update *bu, bool taken, unsigned int target) {
                if (!(bi.br_flags & BR_CONDITIONAL)) return;

                pm_update *p = (pm_update *) bu;

                // the local counter learns every time
                updateCounter(localTable[p->index], taken);

                // global miss: take over the LRU way in that row. the tag gets replaced
                // but the counter keeps whatever value was already there (appendix B does this)
                int w = p->way;
                if (w == -1) {
                        w = lru[p->row];
                        valid[w][p->row] = true;
                        tags[w][p->row] = p->tag;
                }
                updateCounter(ctr[w][p->row], taken);

                // we just used way w, so with only 2 ways the other one is now LRU
                lru[p->row] = 1 - w;

                // ghr: shift left, put the outcome on the right (1 if taken, 0 if not),
                // and drop the oldest bit. e.g. 0110 + not taken -> 1100
                ghr = (ghr << 1) | (taken ? 1 : 0);
                ghr = ghr % (1 << (rowBits + tagBits));
        }
};
