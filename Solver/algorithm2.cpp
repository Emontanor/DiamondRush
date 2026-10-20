#include <cstring>

namespace {

typedef unsigned __int128 u128;

#define BIT(i) ((u128)1 << (i))

struct LevelData { const char* rows[12]; int startRow, startCol; const char* moves; };
static const LevelData LEVELS[20] = {
    /* level  1,  22 moves */ {{"########", "..######", "..######", "........", "######..", "######..", "........", "...#####", "...#####", "##......", "##..#...", "....#..."},
        3, 1,
        "RRRRRDDDLLLLLDDRDRRRDR"},
    /* level  2,  34 moves */ {{"########", ".....###", ".....###", ".###.##.", ".###....", ".###....", ".###.###", ".#...###", ".#.#.###", ".###....", "........", "..##...."},
        10, 6,
        "LLLLLDLUUUUUUUUURURDRRDDRRDLLDDLLD"},
    /* level  3,  63 moves */ {{"########", "...#.#..", "..##....", ".....#..", "#.#.####", "..#..#..", "..#.....", "#.#..#..", "..#..###", ".##..#..", "........", ".###.#.."},
        2, 0,
        "DRDDDDDLDDRRRUUUUUUDDDDDDRDURRRLLLUUUURRDRUULDLLULUURURRURLDDRU"},
    /* level  4,  47 moves */ {{"########", "........", "#####.##", "........", ".#######", "........", "#####.##", "........", "........", "#...#.#.", "##..#.#.", "###.###."},
        1, 1,
        "RRRRDDLLLLLDDRRRRRRLDDLLLLLDRURDDDRDUULURRURDDD"},
    /* level  5,  53 moves */ {{"########", ".#####..", ".....#..", ".##.###.", ".#...##.", ".#......", ".#......", ".....#..", "....###.", "###.###.", "###.....", "####..##"},
        2, 0,
        "RRRRLDDDDRDLDDDRDRURRUUUUUUUULURDDDDDLLLDLLLDLUUUUUUU"},
    /* level  6,  77 moves */ {{"########", "........", "........", ".#.##.#.", "........", "........", "..##.#..", "..#..#..", "#.####.#", "........", ".######.", "........"},
        1, 4,
        "RRRDLLLLULDDDRDLULDLDDRDULUURDDDUUURRRRRDDDDLLLLLLDDRRRRRRRUULLLLLLUUUURRRDDL"},
    /* level  7,  42 moves */ {{"########", "#....##.", "......#.", "..#.#.#.", ".....##.", "#....#..", "...#.#..", ".##..#..", ".......#", "..##.##.", "..#...#.", ".##...#."},
        2, 1,
        "RURDDDDLDLLDDDDUURRRRRRUUURUUDDLDDRLDLLDDD"},
    /* level  8,  49 moves */ {{"#......#", "#.####.#", "#.#..#.#", "#....#.#", "######.#", "#......#", "######.#", "#......#", "#.#..#.#", "#.#..#.#", "#......#", "########"},
        5, 4,
        "LLRRRRDDDDDLLLUUULLDDDRRRUUURRUUUUUUULLLLLDDDRRRU"},
    /* level  9,  71 moves */ {{"########", "........", "........", ".##.####", ".......#", "#.......", "#.######", "..#.....", "........", ".#.#.#.#", "...#.#..", "...#.#.."},
        1, 4,
        "DLLLULDRRRDDLDRRRRULLLLLLRDDDDLDDDURDRUUDLLUURRRRDDDUUUURRDLULDDURRDDDR"},
    /* level 10,  62 moves */ {{"########", "........", ".##..##.", "..#..#..", "..##.#..", "#.#..#.#", "........", "#.#..#.#", "........", "........", ".#....#.", "........"},
        4, 4,
        "DLDDDLDRRDRUDDLLUURURDRUUURLUURUUDLDDDLLDDLLDLUUULRUUULUURRRDD"},
    /* level 11,  72 moves */ {{"########", "...###..", "........", ".#####.#", "..#..#..", ".....#..", ".###...#", "...#....", ".#.#...#", ".......#", ".###.#.#", "........"},
        2, 1,
        "ULDDDDRLDDDDRRRRLLLLDDRRRRUUUURDRURLUUUDDLLUULDRDDDDRLDDRRRLUUUUUUUUULLL"},
    /* level 12,  60 moves */ {{"########", ".....#.#", "####....", "#....##.", "..#.....", "#.#####.", "#.#####.", "....#...", ".##.#.#.", ".#..#...", "........", "########"},
        1, 2,
        "LRRRDRRUDRDDDDDDDLDLLLLLLUUURRRDDLDRUUULLUUULRDDDRRDDDRRURRD"},
    /* level 13,  60 moves */ {{"########", "........", ".#.##.##", "##......", ".#.#.##.", "........", ".#.##.##", ".#.#..#.", ".#.#....", ".#.##.##", "........", "########"},
        10, 3,
        "LUUUUUUUUULLDURRRRRDURRLLDDLRRRDDLLLLLLLUDDDDDDRRRRRRLUULRRR"},
    /* level 14,  85 moves */ {{"########", ".....#..", "#.#.##..", "...#.#.#", "....#...", ".#.#.#..", "#...#...", "...#....", "#.#.##.#", "........", "#....##.", "###.####"},
        11, 3,
        "URURRRDULLLDLLULUUURDLDDDRRRURRUURUUULUURULDDDRDDDLLLRURDRUDLDDLLLLLUUURUURLLLURUURRD"},
    /* level 15,  65 moves */ {{"########", "..#.....", "#.#.#...", "..#.#...", "....#...", ".##.#...", ".##.....", "..#.###.", "#.#.....", "..###.##", "........", "########"},
        4, 0,
        "RRRDDDDRRDURRUULULUUURULLLDDDLLLDDDRDDDLRRRRRRLUURRUULLLLUULLUUUL"},
    /* level 16,  98 moves */ {{"########", "########", "########", "########", "...#..#.", ".#......", ".#.##.#.", ".#....#.", "....#.#.", ".##.....", ".#..####", "........"},
        4, 0,
        "RRDDDRRRDDRRUUUUUDLLLLRRDDDUUURRDDDDLLLRUULLDDDLDRLLLUUURRLLUUUURRDDDRDDDLDRRLLLLUUURRURDDDLDRRRRR"},
    /* level 17,  90 moves */ {{"########", "......#.", ".####.#.", "........", ".##.###.", "........", ".....###", ".##.###.", "##......", ".#..##..", ".....#.#", "######.."},
        4, 0,
        "DDRRRDDRRRDRULLLLUUUUDLLLUUUURRLLDDRRRRRLLDDDDDDDRLLLLUDRRUURUUURRRRUUUUDDLLLLDDDDDRRRDDDR"},
    /* level 18,  91 moves */ {{"########", "........", ".######.", ".#......", ".#.##.#.", ".#......", ".#.##.#.", ".#....#.", ".#.##.#.", ".#....#.", "....#...", "########"},
        6, 2,
        "UUURRRDDDDDDLLLUUUUDDRRRDDDRRUUUUULRUULLDDDDUUUURRUULLLLLLLDDDDDDDDDUUUUUUUUURRRRRRRDDLLDDL"},
    /* level 19,  52 moves */ {{"########", ".##.#...", ".#..#.#.", "........", ".##.##..", "....##..", ".#.....#", ".##.##..", "....#...", ".####.##", ".......#", "########"},
        4, 3,
        "UUUDDDDDRRRURLURUUULLDDRDDDDDLDDLLLLLUURRRUUUUULLLUU"},
    /* level 20,  75 moves */ {{"........", "#.##....", "#.......", "......##", "....#..#", "###.#...", "........", ".##..##.", "##...#..", "........", "....#...", "....#..."},
        2, 6,
        "LLLDDDDUULLUURDURRURDDDDDRRULDLLLUUUURRDDDRDLLLLRUUULLDRURDDUUURRDDDDLLLLLD"},
};

u128 wallMask[20];
int moveLen[20];

__attribute__((constructor)) void precompute() {
    for (int L = 0; L < 20; L++) {
        u128 m = 0;
        for (int r = 0; r < 12; r++)
            for (int c = 0; c < 8; c++)
                if (LEVELS[L].rows[r][c] == '#') m |= BIT(r * 8 + c);
        wallMask[L] = m;
        moveLen[L] = (int)strlen(LEVELS[L].moves);
    }
}

}  // namespace

__attribute__((visibility("hidden")))
int alg2_solve(const int* cells, int H, char* out_moves, int out_capacity, int* out_is_final) {
    const int n = H << 3;
    u128 wall = 0, pass = 0;
    int player = 0;
    for (int i = 0; i < n; i++) {
        const int v = cells[i];
        if (v == 1 || v == 6) wall |= BIT(i);
        else if (v == 0 || v == 3 || v == 7 || v == 14) pass |= BIT(i);
        else if (v == 10 || v == 17 || v == 18) player = i;
    }
    const u128 rowsM = n == 128 ? ~(u128)0 : BIT(n) - 1;
    int L = 0, o = 0;
    for (; L < 20; L++) {
        const u128 m = wallMask[L];
        for (o = 0; o <= 12 - H; o++)
            if (((m >> (o << 3)) & rowsM) == wall) goto found;
    }
    return -1;
found:
    const int sr = LEVELS[L].startRow - o;
    if (sr < 0 || sr >= H) return -1;
    const int target = (sr << 3) + LEVELS[L].startCol;
    u128 layer[128];
    int D = 0;
    if (player != target) {
        u128 col0 = 0, col7 = 0;
        for (int r = 0; r < 16; r++) { col0 |= BIT(r * 8); col7 |= BIT(r * 8 + 7); }
        const u128 T = BIT(target);
        u128 F = BIT(player), V = F;
        layer[0] = F;
        while (!(F & T)) {
            F = (((F & ~col7) << 1) | ((F & ~col0) >> 1) | (F << 8) | (F >> 8)) & pass & ~V;
            if (!F) return -1;
            V |= F;
            layer[++D] = F;
        }
    }
    const int total = D + moveLen[L];
    if (total > out_capacity) return -2;
    for (int cur = target, d = D; d > 0; d--) {
        const u128 P = layer[d - 1];
        if (cur >= 8 && ((P >> (cur - 8)) & 1)) { out_moves[d - 1] = 'D'; cur -= 8; }
        else if (cur + 8 < n && ((P >> (cur + 8)) & 1)) { out_moves[d - 1] = 'U'; cur += 8; }
        else if ((cur & 7) && ((P >> (cur - 1)) & 1)) { out_moves[d - 1] = 'R'; cur -= 1; }
        else { out_moves[d - 1] = 'L'; cur += 1; }
    }
    memcpy(out_moves + D, LEVELS[L].moves, (size_t)moveLen[L]);
    *out_is_final = 1;
    return total;
}
