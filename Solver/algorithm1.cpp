#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <climits>
#include <vector>

namespace {

typedef unsigned __int128 u128;
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;

#define BIT(i) ((u128)1 << (i))

inline int ctz128(u128 x) {
    u64 lo = (u64)x;
    return lo ? __builtin_ctzll(lo) : 64 + __builtin_ctzll((u64)(x >> 64));
}

enum { K_WALL, K_LAVA, K_FLOOR, K_HOLE, K_SPIKE, K_PLATE, K_GATE, K_LOCK, K_KEY, K_DIAMOND, K_EXIT, K_RELIC, K_POT };
const u8 KIND_OF[20] = {K_FLOOR, K_WALL,  K_HOLE, K_HOLE, K_SPIKE, K_SPIKE, K_LAVA,  K_DIAMOND, K_KEY,   K_POT,
                        K_FLOOR, K_LOCK,  K_EXIT, K_EXIT, K_PLATE, K_GATE,  K_GATE,  K_SPIKE,   K_PLATE, K_RELIC};
const int I_PUSH = 4;
const int INF = 0xFFFF;
const u32 NONE = 0xFFFFFFFFu;
const char DC[4] = {'U', 'D', 'L', 'R'};

struct State {
    u128 rocks;
    u64 diam, spk, holes;
    u16 keys, locks;
    u8 player, hasKey;
    u8 pad[2];
};
struct Node {
    State s;
    u64 h;
    u32 parent;
    u16 g;
    u8 cell, info;
};
static_assert(sizeof(State) == 48, "state");
static_assert(sizeof(Node) == 64, "node");

struct Model { u128 spikeLike; u16 pg[16]; };

// ---------------------------------------------------------------- persistent memory
bool g_init = false;
int H, N;
u128 gridM, col0M, col7M, rowLastM, freeM;
u128 wallM, lavaM, holeM, spikeM, potM, plateM, gateM, lockM, keyM, diamM, targetM;
int targetCell;
u8 kind[128], cid[128];
int nHole, nSpike, nPlate, nGate, nLock, nKey, nDiam;
u8 holeCell[64], spikeCell[64], plateCell[16], gateCell[16], lockCell[16], keyCell[16], diamCell[64];
u8 adjPl[16][4], nAdjPl[16];
u16 cand[16], allGates;
u64 knownD;
u16 knownK;
bool havePred;
State pred;
u16 rootPressed, rootOpenG;
Model MO, MC;
const Model* M = &MO;
State S0;
u64 S0h;

u64 rockZ[128], playerZ[128], diamondZ[64], spikeZ[64], holeZ[64], keyZ[16], lockZ[16], hasKeyZ;

#ifdef __AVX2__
typedef u16 VU __attribute__((vector_size(32)));
#else
typedef u16 VU __attribute__((vector_size(16)));
#endif
const int VL = (int)(sizeof(VU) / sizeof(u16));
const int NVMAX = (20 + VL - 1) / VL;

bool distReady, hkReady, hkMode;
u16 dD[64][128], dT[128];
VU dcol[20][NVMAX], ncol[20][NVMAX];
u16* G = nullptr;

u8 dist[128];

// ---------------------------------------------------------------- bit helpers
inline u128 nbr(u128 F) {
    return (((F & ~col7M) << 1) | ((F & ~col0M) >> 1) | (F << 8) | (F >> 8)) & gridM;
}
inline int nb(int p, int d) {
    switch (d) {
        case 0: return p >= 8 ? p - 8 : -1;
        case 1: return p + 8 < N ? p + 8 : -1;
        case 2: return (p & 7) ? p - 1 : -1;
        default: return (p & 7) != 7 ? p + 1 : -1;
    }
}
inline u128 cellsOf(u64 m, const u8* tab) {
    u128 r = 0;
    for (; m; m &= m - 1) r |= BIT(tab[__builtin_ctzll(m)]);
    return r;
}
inline u16 openG(const Model& m, u16 q) {
    u16 g = 0;
    for (u32 t = q; t; t &= t - 1) g |= m.pg[__builtin_ctz(t)];
    if (q == rootPressed) g |= rootOpenG;
    return g;
}
inline u128 gateCells(u32 g) {
    u128 r = 0;
    for (; g; g &= g - 1) r |= BIT(gateCell[__builtin_ctz(g)]);
    return r;
}
inline u16 pressedQ(const State& S) {
    u16 q = 0;
    for (u128 r = S.rocks & plateM; r; r &= r - 1) q |= (u16)(1u << cid[ctz128(r)]);
    if (kind[S.player] == K_PLATE) q |= (u16)(1u << cid[S.player]);
    return q;
}
inline int dirOf(char c) { return c == 'U' ? 0 : c == 'D' ? 1 : c == 'L' ? 2 : 3; }

u64 smState;
inline u64 splitmix() {
    u64 z = (smState += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

u64 hashOf(const State& s) {
    u64 h = 0;
    for (u128 r = s.rocks; r; r &= r - 1) h ^= rockZ[ctz128(r)];
    for (u64 m = s.diam; m; m &= m - 1) h ^= diamondZ[__builtin_ctzll(m)];
    for (u64 m = s.spk; m; m &= m - 1) h ^= spikeZ[__builtin_ctzll(m)];
    for (u64 m = s.holes; m; m &= m - 1) h ^= holeZ[__builtin_ctzll(m)];
    for (u32 m = s.keys; m; m &= m - 1) h ^= keyZ[__builtin_ctz(m)];
    for (u32 m = s.locks; m; m &= m - 1) h ^= lockZ[__builtin_ctz(m)];
    if (s.hasKey) h ^= hasKeyZ;
    return h ^ playerZ[s.player];
}

// ---------------------------------------------------------------- search arenas
std::vector<Node> pool;

struct Slot { u64 h; u32 idx; u32 gen; };
Slot* ht = nullptr;
size_t htCap = 0, htCnt = 0;
u32 htGen = 0;

void htNew() {
    if (!ht) {
        htCap = (size_t)1 << 20;
        ht = (Slot*)calloc(htCap, sizeof(Slot));
    }
    if (++htGen == 0) {
        memset(ht, 0, htCap * sizeof(Slot));
        htGen = 1;
    }
    htCnt = 0;
}
inline u32 htFind(u64 h, const State& s, size_t& pos) {
    const size_t m = htCap - 1;
    size_t i = h & m;
    for (;;) {
        const Slot& sl = ht[i];
        if (sl.gen != htGen) { pos = i; return NONE; }
        if (sl.h == h && !memcmp(&pool[sl.idx].s, &s, sizeof(State))) return sl.idx;
        i = (i + 1) & m;
    }
}
void htGrow() {
    const size_t nc = htCap * 2, m = nc - 1;
    Slot* nt = (Slot*)calloc(nc, sizeof(Slot));
    for (size_t i = 0; i < htCap; i++) {
        if (ht[i].gen != htGen) continue;
        size_t j = ht[i].h & m;
        while (nt[j].gen == htGen) j = (j + 1) & m;
        nt[j] = ht[i];
    }
    free(ht);
    ht = nt;
    htCap = nc;
}
inline void htInsertAt(size_t pos, u64 h, u32 idx) {
    ht[pos].h = h;
    ht[pos].idx = idx;
    ht[pos].gen = htGen;
    if (++htCnt * 2 > htCap) htGrow();
}

std::vector<u64> heap;

inline void hpush(u64 v) {
    size_t i = heap.size();
    heap.push_back(v);
    u64* a = heap.data();
    while (i) {
        size_t p = (i - 1) >> 1;
        if (a[p] <= v) break;
        a[i] = a[p];
        i = p;
    }
    a[i] = v;
}
inline u64 hpop() {
    u64* a = heap.data();
    const u64 top = a[0];
    const size_t n = heap.size() - 1;
    const u64 v = a[n];
    heap.pop_back();
    if (n) {
        size_t i = 0;
        for (;;) {
            size_t l = 2 * i + 1;
            if (l >= n) break;
            size_t r = l + 1;
            size_t m = (r < n && a[r] < a[l]) ? r : l;
            a[i] = a[m];
            i = m;
        }
        while (i) {
            size_t p = (i - 1) >> 1;
            if (a[p] <= v) break;
            a[i] = a[p];
            i = p;
        }
        a[i] = v;
    }
    return top;
}

// ---------------------------------------------------------------- heuristic
void relaxedBFS(int src, u16* out) {
    for (int i = 0; i < N; i++) out[i] = INF;
    u128 V = BIT(src), F = V;
    out[src] = 0;
    int d = 0;
    while (F) {
        ++d;
        u128 Nn = nbr(F) & freeM & ~V;
        for (u128 x = Nn; x; x &= x - 1) out[ctz128(x)] = (u16)d;
        V |= Nn;
        F = Nn;
    }
}

// push form of G[mask][i] = min_j (dD[i][j] + G[mask\{i}][j]): for each R (increasing),
// out[i] = min_{j in R} (dD[i][j] + G[R][j]) for all i at once, stored to G[R|{i}][i];
// c + min(r, ~c) is the add saturated at INF
template <int NV>
void buildHK(int k) {
    const u32 full = (u32)(((size_t)1 << k) - 1);
    const VU zero = {};
    const VU inf = zero + (u16)INF;
    for (u32 R = 1; R < full; R++) {
        const u16* row = G + (size_t)R * k;
        VU out[NV];
        for (int v = 0; v < NV; v++) out[v] = inf;
        for (u32 b = R; b; b &= b - 1) {
            const int j = __builtin_ctz(b);
            const VU rb = zero + row[j];
            for (int v = 0; v < NV; v++) {
                const VU t = rb < ncol[j][v] ? rb : ncol[j][v];
                const VU s = dcol[j][v] + t;
                out[v] = s < out[v] ? s : out[v];
            }
        }
        u16 o[NV * VL];
        memcpy(o, out, sizeof out);
        for (u32 b = full & ~R; b; b &= b - 1) {
            const int i = __builtin_ctz(b);
            G[(size_t)(R | (1u << i)) * k + i] = o[i];
        }
    }
}

void ensureHeur() {
    if (!distReady) {
        for (int i = 0; i < nDiam; i++) relaxedBFS(diamCell[i], dD[i]);
        relaxedBFS(targetCell, dT);
        distReady = true;
    }
    if (hkMode && !hkReady) {
        const int k = nDiam;
        free(G);
        G = (u16*)malloc(((size_t)1 << k) * (size_t)(k ? k : 1) * sizeof(u16));
        for (int j = 0; j < k; j++)
            for (int v = 0; v < NVMAX; v++)
                for (int l = 0; l < VL; l++) {
                    const int i = v * VL + l;
                    const u16 c = i < k ? dD[i][diamCell[j]] : (u16)INF;
                    dcol[j][v][l] = c;
                    ncol[j][v][l] = (u16)~c;
                }
        for (int i = 0; i < k; i++) G[((size_t)1 << i) * k + i] = dT[diamCell[i]];
        const int nv = (k + VL - 1) / VL;
        if (nv <= 1) buildHK<1>(k);
        else if (nv == 2) buildHK<2>(k);
        else buildHK<NVMAX>(k);
        hkReady = true;
    }
}

int mstH(const State& S) {
    int ids[64], key[65];
    bool in[65];
    int m = 0;
    const int p = S.player;
    for (u64 a = S.diam; a; a &= a - 1) ids[m++] = __builtin_ctzll(a);
    for (int j = 0; j < m; j++) { key[j] = dD[ids[j]][p]; in[j] = false; }
    key[m] = dT[p];
    in[m] = false;
    int total = 0;
    for (int it = 0; it <= m; it++) {
        int bj = -1, bv = INT_MAX;
        for (int j = 0; j <= m; j++)
            if (!in[j] && key[j] < bv) { bv = key[j]; bj = j; }
        if (bv >= INF) return INF;
        in[bj] = true;
        total += bv;
        for (int j = 0; j <= m; j++) {
            if (in[j]) continue;
            int d;
            if (bj < m) d = j < m ? dD[ids[bj]][diamCell[ids[j]]] : dT[diamCell[ids[bj]]];
            else d = dT[diamCell[ids[j]]];
            if (d < key[j]) key[j] = d;
        }
    }
    return total >= INF ? INF : total;
}

inline int heur(const State& S) {
    const int p = S.player;
    u64 dm = S.diam;
    if (!dm) return dT[p];
    if (!hkMode) return mstH(S);
    const u16* row = G + (size_t)dm * nDiam;
    int best = INF;
    for (; dm; dm &= dm - 1) {
        const int i = __builtin_ctzll(dm);
        const int x = dD[i][p] + row[i];
        if (x < best) best = x;
    }
    return best;
}

bool reachOK(const State& S) {
    const u128 act = cellsOf(S.spk, spikeCell);
    const u128 base = wallM | lavaM | targetM | act;
    u128 Fz = 0;
    const u128 rocks = S.rocks;
    if (rocks) {
        for (;;) {
            const u128 Bm = base | Fz;
            const u128 L = col0M | ((Bm & ~col7M) << 1);
            const u128 R = col7M | ((Bm & ~col0M) >> 1);
            const u128 U = (u128)0xFF | (Bm << 8);
            const u128 D = rowLastM | (Bm >> 8);
            const u128 nf = rocks & (L | R) & (U | D);
            if (nf == Fz) break;
            Fz = nf;
        }
    }
    const u128 fr = freeM & ~act & ~Fz;
    u128 Rc = BIT(S.player), F = Rc;
    while (F) {
        const u128 Nn = nbr(F) & fr & ~Rc;
        Rc |= Nn;
        F = Nn;
    }
    const u128 need = cellsOf(S.diam, diamCell) | targetM;
    return !(need & ~Rc);
}

// ---------------------------------------------------------------- macro moves
struct Ctx {
    u128 event, pass, activeSp, lockC, closedG;
    u16 rockQ, baseG;
    int ngc;
    u8 gc[16];
    u128 gop[16];
};

inline void prepare(const State& S, Ctx& c) {
    const Model& m = *M;
    const u128 diamC = cellsOf(S.diam, diamCell);
    const u128 keyC = cellsOf(S.keys, keyCell);
    c.lockC = cellsOf(S.locks, lockCell);
    c.activeSp = cellsOf(S.spk, spikeCell);
    const u128 filled = cellsOf(S.holes, holeCell);
    u16 rq = 0, base = 0;
    for (u128 r = S.rocks & plateM; r; r &= r - 1) {
        const int p = cid[ctz128(r)];
        rq |= (u16)(1u << p);
        base |= m.pg[p];
    }
    c.rockQ = rq;
    c.baseG = base;
    const u16 og = base | (rq == rootPressed ? rootOpenG : 0);
    c.closedG = gateM & ~gateCells(og);
    const u128 blocked = wallM | lavaM | S.rocks | (holeM & ~filled) | c.activeSp | c.closedG |
                         (S.hasKey ? (u128)0 : c.lockC) | (S.diam ? targetM : (u128)0);
    const u128 ev = (diamC | (S.hasKey ? c.lockC : keyC) | (m.spikeLike & ~c.activeSp) |
                     (S.diam ? (u128)0 : targetM)) & ~blocked;
    c.event = ev;
    c.pass = gridM & ~blocked & ~ev;
    c.ngc = 0;
    if (nGate) {
        for (u128 cg = c.closedG & ~S.rocks; cg; cg &= cg - 1) {
            const int gcell = ctz128(cg), gid = cid[gcell];
            u128 om = 0;
            for (int a = 0; a < nAdjPl[gid]; a++) {
                const int pc = adjPl[gid][a], pid = cid[pc];
                const u16 q2 = rq | (u16)(1u << pid);
                const u16 o2 = base | m.pg[pid] | (q2 == rootPressed ? rootOpenG : 0);
                if ((o2 >> gid) & 1) om |= BIT(pc);
            }
            if (om) { c.gc[c.ngc] = (u8)gcell; c.gop[c.ngc++] = om; }
        }
    }
}

// cb(child, hash, cost, cell, info, goal, structural) -> true to stop
template <class CB>
inline bool expand(const State& S, u64 hS, CB&& cb) {
    Ctx c;
    prepare(S, c);
    const int s = S.player;
    u64 sAct = 0;
    u64 hBase = hS ^ playerZ[s];
    if ((M->spikeLike >> s) & 1) {
        const u64 b = 1ull << cid[s];
        if (!(S.spk & b)) { sAct = b; hBase ^= spikeZ[cid[s]]; }
    }
    const u128 pushOrig = nbr(S.rocks);
    u128 V = BIT(s), F = V, RP = 0;
    int d = 0;
    while (F) {
        const u128 Nn = nbr(F) & ~V;
        u128 E = Nn & c.event, PG = Nn & c.pass;
        for (int k = 0; k < c.ngc; k++) {
            const int g = c.gc[k];
            if (!((V >> g) & 1) && (F & c.gop[k])) PG |= BIT(g);
        }
        ++d;
        for (u128 o = PG & pushOrig; o; o &= o - 1) dist[ctz128(o)] = (u8)d;
        V |= E | PG;
        RP |= PG;
        F = PG;
        for (; E; E &= E - 1) {
            const int e = ctz128(E);
            State C = S;
            C.player = (u8)e;
            C.spk |= sAct;
            u64 h = hBase ^ playerZ[e];
            bool goal = false;
            switch (kind[e]) {
                case K_DIAMOND: C.diam &= ~(1ull << cid[e]); h ^= diamondZ[cid[e]]; break;
                case K_KEY: C.keys &= (u16)~(1u << cid[e]); C.hasKey = 1; h ^= keyZ[cid[e]] ^ hasKeyZ; break;
                case K_LOCK: C.locks &= (u16)~(1u << cid[e]); C.hasKey = 0; h ^= lockZ[cid[e]] ^ hasKeyZ; break;
                case K_EXIT: case K_RELIC: goal = true; break;
                default: break;
            }
            if (cb(C, h, d, e, 0, goal, sAct != 0)) return true;
        }
    }
    const u128 tbBase = wallM | lavaM | targetM | S.rocks | c.activeSp | c.lockC;
    for (u128 R = S.rocks; R; R &= R - 1) {
        const int r = ctz128(R), col = r & 7;
        for (int dir = 0; dir < 4; dir++) {
            int o, t;
            if (dir == 0) { if (r < 8 || r + 8 >= N) continue; o = r + 8; t = r - 8; }
            else if (dir == 1) { if (r < 8 || r + 8 >= N) continue; o = r - 8; t = r + 8; }
            else if (dir == 2) { if (col == 0 || col == 7) continue; o = r + 1; t = r - 1; }
            else { if (col == 0 || col == 7) continue; o = r - 1; t = r + 1; }
            int dd;
            if (o == s) dd = 0;
            else if ((RP >> o) & 1) dd = dist[o];
            else continue;
            u128 cg = c.closedG;
            if (kind[o] == K_PLATE) {
                const int pid = cid[o];
                const u16 q = c.rockQ | (u16)(1u << pid);
                cg = gateM & ~gateCells(c.baseG | M->pg[pid] | (q == rootPressed ? rootOpenG : 0));
            }
            if ((cg >> r) & 1) continue;
            u128 tb = tbBase | cg;
            if (dd && sAct) tb |= BIT(s);
            if ((tb >> t) & 1) continue;
            State C = S;
            u64 h = hBase ^ playerZ[r] ^ rockZ[r];
            C.rocks &= ~BIT(r);
            C.player = (u8)r;
            C.spk |= sAct;
            if (kind[t] == K_HOLE && !((S.holes >> cid[t]) & 1)) { C.holes |= 1ull << cid[t]; h ^= holeZ[cid[t]]; }
            else { C.rocks |= BIT(t); h ^= rockZ[t]; }
            if (kind[r] == K_DIAMOND) {
                const u64 b = 1ull << cid[r];
                if (S.diam & b) { C.diam &= ~b; h ^= diamondZ[cid[r]]; }
            } else if (kind[r] == K_KEY && !S.hasKey) {
                const u16 b = (u16)(1u << cid[r]);
                if (S.keys & b) { C.keys &= (u16)~b; C.hasKey = 1; h ^= keyZ[cid[r]] ^ hasKeyZ; }
            }
            if (cb(C, h, dd + 1, r, I_PUSH | dir, false, true)) return true;
        }
    }
    return false;
}

bool walkTo(const State& S, const Ctx& c, int target, std::vector<char>& out) {
    const int s = S.player;
    if (s == target) return true;
    u8 q[128], pc[128], pd[128];
    int qh = 0, qt = 0;
    u128 V = BIT(s);
    q[qt++] = (u8)s;
    while (qh < qt) {
        const int u = q[qh++];
        for (int dir = 0; dir < 4; dir++) {
            const int v = nb(u, dir);
            if (v < 0 || ((V >> v) & 1)) continue;
            bool exp;
            if ((c.pass >> v) & 1) exp = true;
            else if ((c.event >> v) & 1) exp = false;
            else {
                int k = 0;
                while (k < c.ngc && c.gc[k] != v) k++;
                if (k == c.ngc || !((c.gop[k] >> u) & 1)) continue;
                exp = true;
            }
            V |= BIT(v);
            pc[v] = (u8)u;
            pd[v] = (u8)dir;
            if (v == target) {
                char buf[128];
                int L = 0;
                for (int x = v; x != s; x = pc[x]) buf[L++] = DC[pd[x]];
                while (L) out.push_back(buf[--L]);
                return true;
            }
            if (exp) q[qt++] = (u8)v;
        }
    }
    return false;
}

std::vector<u32> chainBuf;
bool buildMoves(u32 endIdx, std::vector<char>& out) {
    out.clear();
    chainBuf.clear();
    for (u32 i = endIdx; pool[i].parent != NONE; i = pool[i].parent) chainBuf.push_back(i);
    for (size_t k = chainBuf.size(); k-- > 0;) {
        const Node& cn = pool[chainBuf[k]];
        const State& P = pool[cn.parent].s;
        Ctx c;
        prepare(P, c);
        const int dir = cn.info & 3;
        int target = cn.cell;
        if (cn.info & I_PUSH) target = dir == 0 ? cn.cell + 8 : dir == 1 ? cn.cell - 8 : dir == 2 ? cn.cell + 1 : cn.cell - 1;
        if (!walkTo(P, c, target, out)) return false;
        if (cn.info & I_PUSH) out.push_back(DC[dir]);
    }
    return true;
}

// ---------------------------------------------------------------- single move
inline void activate(State& S, int p, const Model& m) {
    if ((m.spikeLike >> p) & 1) S.spk |= 1ull << cid[p];
}
int step(State& S, int d, const Model& m) {
    const int p = S.player, c = nb(p, d);
    if (c < 0) return 0;
    const int k = kind[c];
    if (k == K_WALL || k == K_LAVA) return 0;
    if (k == K_EXIT || k == K_RELIC) {
        if (S.diam) return 0;
        S.player = (u8)c;
        activate(S, p, m);
        return 2;
    }
    if (k == K_HOLE && !((S.holes >> cid[c]) & 1)) return 0;
    const u16 Q = pressedQ(S);
    if (k == K_GATE && !((openG(m, Q) >> cid[c]) & 1)) return 0;
    if (((m.spikeLike >> c) & 1) && ((S.spk >> cid[c]) & 1)) return 0;
    if (k == K_LOCK && ((S.locks >> cid[c]) & 1)) {
        if (!S.hasKey) return 0;
        S.locks &= (u16)~(1u << cid[c]);
        S.hasKey = 0;
        S.player = (u8)c;
        activate(S, p, m);
        return 1;
    }
    if ((S.rocks >> c) & 1) {
        const int t = nb(c, d);
        if (t < 0) return 0;
        const int kt = kind[t];
        if (kt == K_WALL || kt == K_LAVA || kt == K_EXIT || kt == K_RELIC) return 0;
        if ((S.rocks >> t) & 1) return 0;
        if (kt == K_GATE && !((openG(m, Q) >> cid[t]) & 1)) return 0;
        if (((m.spikeLike >> t) & 1) && ((S.spk >> cid[t]) & 1)) return 0;
        if (kt == K_LOCK && ((S.locks >> cid[t]) & 1)) return 0;
        S.rocks &= ~BIT(c);
        if (kt == K_HOLE && !((S.holes >> cid[t]) & 1)) S.holes |= 1ull << cid[t];
        else S.rocks |= BIT(t);
    }
    S.player = (u8)c;
    if (k == K_DIAMOND) S.diam &= ~(1ull << cid[c]);
    else if (k == K_KEY && ((S.keys >> cid[c]) & 1) && !S.hasKey) {
        S.keys &= (u16)~(1u << cid[c]);
        S.hasKey = 1;
    }
    activate(S, p, m);
    return 1;
}

// ---------------------------------------------------------------- reset / reconcile
void resetAll() {
    g_init = false;
    havePred = false;
    distReady = hkReady = false;
    free(G);
    G = nullptr;
}

bool initLevel(const int* c) {
    wallM = lavaM = holeM = spikeM = potM = plateM = gateM = lockM = keyM = diamM = targetM = 0;
    nHole = nSpike = nPlate = nGate = nLock = nKey = nDiam = 0;
    int nT = 0;
    for (int i = 0; i < N; i++) {
        const int k = KIND_OF[c[i]];
        kind[i] = (u8)k;
        cid[i] = 0;
        switch (k) {
            case K_WALL: wallM |= BIT(i); break;
            case K_LAVA: lavaM |= BIT(i); break;
            case K_HOLE: if (nHole >= 64) return false; holeM |= BIT(i); holeCell[nHole] = (u8)i; cid[i] = (u8)nHole++; break;
            case K_SPIKE: if (nSpike >= 64) return false; spikeM |= BIT(i); spikeCell[nSpike] = (u8)i; cid[i] = (u8)nSpike++; break;
            case K_PLATE: if (nPlate >= 16) return false; plateM |= BIT(i); plateCell[nPlate] = (u8)i; cid[i] = (u8)nPlate++; break;
            case K_GATE: if (nGate >= 16) return false; gateM |= BIT(i); gateCell[nGate] = (u8)i; cid[i] = (u8)nGate++; break;
            case K_LOCK: if (nLock >= 16) return false; lockM |= BIT(i); lockCell[nLock] = (u8)i; cid[i] = (u8)nLock++; break;
            case K_KEY: if (nKey >= 16) return false; keyM |= BIT(i); keyCell[nKey] = (u8)i; cid[i] = (u8)nKey++; break;
            case K_DIAMOND: if (nDiam >= 64) return false; diamM |= BIT(i); diamCell[nDiam] = (u8)i; cid[i] = (u8)nDiam++; break;
            case K_EXIT: case K_RELIC: targetM |= BIT(i); targetCell = i; nT++; break;
            case K_POT: potM |= BIT(i); break;
            default: break;
        }
    }
    if (nT != 1) return false;
    for (u128 p = potM; p; p &= p - 1) {
        const int i = ctz128(p);
        if (nSpike >= 64) return false;
        spikeCell[nSpike] = (u8)i;
        cid[i] = (u8)nSpike++;
    }
    for (int g = 0; g < nGate; g++) {
        nAdjPl[g] = 0;
        for (int d = 0; d < 4; d++) {
            const int v = nb(gateCell[g], d);
            if (v >= 0 && kind[v] == K_PLATE) adjPl[g][nAdjPl[g]++] = (u8)v;
        }
    }
    allGates = (u16)((1u << nGate) - 1);
    for (int p = 0; p < nPlate; p++) cand[p] = allGates;
    knownD = nDiam == 64 ? ~0ull : (1ull << nDiam) - 1;
    knownK = (u16)((1u << nKey) - 1);
    havePred = false;
    smState = 0x2545F4914F6CDD1Dull;
    for (int i = 0; i < 128; i++) rockZ[i] = splitmix();
    for (int i = 0; i < 128; i++) playerZ[i] = splitmix();
    for (int i = 0; i < 64; i++) diamondZ[i] = splitmix();
    for (int i = 0; i < 64; i++) spikeZ[i] = splitmix();
    for (int i = 0; i < 64; i++) holeZ[i] = splitmix();
    for (int i = 0; i < 16; i++) keyZ[i] = splitmix();
    for (int i = 0; i < 16; i++) lockZ[i] = splitmix();
    hasKeyZ = splitmix();
    hkMode = nDiam <= 20;
    distReady = hkReady = false;
    return true;
}

bool reconcile(const int* c, int h) {
    const int n = h << 3;
    u128 w = 0, l = 0;
    for (int i = 0; i < n; i++) {
        if (c[i] == 1) w |= BIT(i);
        else if (c[i] == 6) l |= BIT(i);
    }
    if (!g_init || h != H || w != wallM || l != lavaM) {
        resetAll();
        H = h;
        N = n;
        gridM = N == 128 ? ~(u128)0 : (BIT(N) - 1);
        col0M = col7M = 0;
        for (int r = 0; r < 16; r++) { col0M |= BIT(r * 8); col7M |= BIT(r * 8 + 7); }
        rowLastM = (u128)0xFF << (8 * (H - 1));
        if (!initLevel(c)) return false;
        freeM = gridM & ~wallM & ~lavaM;
        g_init = true;
    }

    // resolve POTENTIAL cells
    for (u128 p = potM; p; p &= p - 1) {
        const int i = ctz128(p), v = c[i];
        if (v == 0 || v == 10) { kind[i] = K_FLOOR; potM &= ~BIT(i); }
        else if (v == 4 || v == 5 || v == 17) { kind[i] = K_SPIKE; potM &= ~BIT(i); spikeM |= BIT(i); }
    }

    int player = 0;
    u128 rocks = 0;
    for (int i = 0; i < N; i++) {
        const int v = c[i];
        if (v == 10 || v == 17 || v == 18) player = i;
        else if (v == 9) rocks |= BIT(i);
    }
    const u128 cover = rocks | BIT(player);
    const bool usePred = havePred && pred.rocks == rocks && pred.player == player;

    State s;
    memset(&s, 0, sizeof s);
    s.rocks = rocks;
    s.player = (u8)player;

    // diamonds: update known[], then visible + covered-by-rock presence
    for (int i = 0; i < nDiam; i++) {
        const int cell = diamCell[i];
        const u64 b = 1ull << i;
        if (!((cover >> cell) & 1)) {
            if (c[cell] == 7) { knownD |= b; s.diam |= b; }
            else knownD &= ~b;
        } else if ((rocks >> cell) & 1) {
            if ((usePred ? pred.diam : knownD) & b) s.diam |= b;
        }
    }

    // keys (§7.4)
    int x = 0, u = 0;
    for (int i = 0; i < nKey; i++) {
        const int cell = keyCell[i];
        const u16 b = (u16)(1u << i);
        if (!((cover >> cell) & 1)) {
            if (c[cell] == 8) { knownK |= b; s.keys |= b; x++; }
            else knownK &= (u16)~b;
        } else if ((rocks >> cell) & 1) {
            if ((usePred ? pred.keys : knownK) & b) { s.keys |= b; u++; }
        }
    }
    for (int i = 0; i < nLock; i++) if (c[lockCell[i]] == 11) s.locks |= (u16)(1u << i);
    const int y = nLock - __builtin_popcount(s.locks);
    const int v = nKey - x - u - y;
    s.hasKey = (u8)(v < 0 ? 0 : v > 1 ? 1 : v);
    if (kind[player] == K_KEY && v >= 2) s.keys |= (u16)(1u << cid[player]);

    for (int i = 0; i < nHole; i++)
        if (c[holeCell[i]] == 3 || ((cover >> holeCell[i]) & 1)) s.holes |= 1ull << i;
    for (int i = 0; i < nSpike; i++) {
        const int cell = spikeCell[i];
        if (kind[cell] == K_SPIKE && c[cell] == 4) s.spk |= 1ull << i;
    }

    // root gate observation and plate→gate learning (§7.5)
    rootPressed = 0;
    for (int p = 0; p < nPlate; p++) if ((cover >> plateCell[p]) & 1) rootPressed |= (u16)(1u << p);
    u16 ro = 0, rc = 0, un = 0;
    for (int g = 0; g < nGate; g++) {
        const int cell = gateCell[g];
        const u16 b = (u16)(1u << g);
        if ((cover >> cell) & 1) un |= b;
        else if (c[cell] == 15) ro |= b;
        else if (c[cell] == 16) rc |= b;
        else un |= b;
    }
    rootOpenG = ro;
    for (int p = 0; p < nPlate; p++) cand[p] &= (((rootPressed >> p) & 1) ? ro : rc) | un;
    if (nPlate == nGate) {
        bool ch = true;
        while (ch) {
            ch = false;
            for (int p = 0; p < nPlate; p++) {
                if (__builtin_popcount(cand[p]) != 1) continue;
                for (int q = 0; q < nPlate; q++)
                    if (q != p && (cand[q] & cand[p])) { cand[q] &= (u16)~cand[p]; ch = true; }
            }
            for (int g = 0; g < nGate; g++) {
                int cnt = 0, who = -1;
                for (int p = 0; p < nPlate; p++) if ((cand[p] >> g) & 1) { cnt++; who = p; }
                if (cnt == 1 && cand[who] != (u16)(1u << g)) { cand[who] = (u16)(1u << g); ch = true; }
            }
        }
    }
    for (int p = 0; p < nPlate; p++)
        if (!cand[p]) {
            for (int q = 0; q < nPlate; q++) cand[q] = allGates;
            break;
        }
    MO.spikeLike = spikeM;
    MC.spikeLike = spikeM | potM;
    for (int p = 0; p < nPlate; p++) {
        MO.pg[p] = cand[p];
        MC.pg[p] = __builtin_popcount(cand[p]) == 1 ? cand[p] : 0;
    }
    S0 = s;
    S0h = hashOf(s);
    return true;
}

// ---------------------------------------------------------------- greedy best-first search (§9)
inline u32 newNode(const State& s, u64 h, u32 parent, int g, int cell, int info) {
    Node nd;
    nd.s = s; nd.h = h; nd.parent = parent; nd.g = (u16)g; nd.cell = (u8)cell; nd.info = (u8)info;
    pool.push_back(nd);
    return (u32)pool.size() - 1;
}

u32 gbfs() {
    ensureHeur();
    if (!pool.capacity()) {
        pool.reserve((size_t)1 << 16);
        heap.reserve((size_t)1 << 16);
    }
    pool.clear();
    heap.clear();
    htNew();
    const int h0 = heur(S0);
    if (h0 >= INF) return NONE;
    size_t pos = 0;
    htFind(S0h, S0, pos);
    newNode(S0, S0h, NONE, 0, 0, 0);
    htInsertAt(pos, S0h, 0);
    hpush((u64)((u32)h0 << 16) << 32);
    u32 goal = NONE;
    while (!heap.empty()) {
        const u32 idx = (u32)hpop();
        const Node X = pool[idx];
        if (expand(X.s, X.h, [&](const State& cs, u64 ch, int cost, int cell, int info, bool isGoal, bool st) -> bool {
                const int g2 = X.g + cost;
                if (isGoal) { goal = newNode(X.s, 0, idx, g2, cell, info); return true; }
                size_t p2 = 0;
                if (htFind(ch, cs, p2) != NONE) return false;
                const int hh = heur(cs);
                const bool dead = hh >= INF || (st && !reachOK(cs));
                const u32 k = newNode(cs, ch, idx, g2, cell, info);
                htInsertAt(p2, ch, k);
                if (!dead) hpush(((u64)(((u32)hh << 16) | (u32)(u16)g2) << 32) | k);
                return false;
            }))
            return goal;
    }
    return NONE;
}

bool runSearch(const Model& m, std::vector<char>& out) {
    M = &m;
    const u32 goal = gbfs();
    return goal != NONE && buildMoves(goal, out);
}

// ---------------------------------------------------------------- reliance scan (§10.2)
long relianceCut(const std::vector<char>& mv) {
    State S = S0;
    u128 uncov = 0, U = 0;
    for (size_t j = 0; j < mv.size(); j++) {
        const int dir = dirOf(mv[j]), p = S.player, c = nb(p, dir);
        if (c < 0) return (long)j;
        const u16 Q = pressedQ(S);
        const u16 diff = openG(MO, Q) & (u16)~openG(MC, Q);
        const bool push = (S.rocks >> c) & 1;
        bool rel = (U >> c) & 1;
        if (kind[c] == K_GATE && ((diff >> cid[c]) & 1)) rel = true;
        if (push) {
            const int t = nb(c, dir);
            if (t >= 0) {
                if ((U >> t) & 1) rel = true;
                if (kind[t] == K_GATE && ((diff >> cid[t]) & 1)) rel = true;
            }
        }
        if (rel) return (long)j;
        const int r = step(S, dir, MO);
        if (!r) return (long)j;
        if (push && kind[c] == K_POT) uncov |= BIT(c);
        if ((uncov >> p) & 1) U |= BIT(p);
        if (r == 2) break;
    }
    return -1;
}

std::vector<char> outMv;

}  // namespace

__attribute__((visibility("hidden")))
int alg1_solve(const int* cells, int H, char* out_moves, int out_capacity, int* out_is_final) {
    if (!reconcile(cells, H)) return -1;
    if (!runSearch(MO, outMv)) return -1;
    int fin;
    const long j = relianceCut(outMv);
    if (j < 0) fin = 1;
    else if (j >= 1) { outMv.resize((size_t)j); fin = 0; }
    else {
        if (!runSearch(MC, outMv)) return -1;
        fin = 1;
    }
    State S = S0;
    for (char ch : outMv)
        if (step(S, dirOf(ch), MO) == 2) break;
    pred = S;
    havePred = true;
    const int n = (int)outMv.size();
    if (n > out_capacity) return -2;
    memcpy(out_moves, outMv.data(), (size_t)n);
    *out_is_final = fin;
    return n;
}
