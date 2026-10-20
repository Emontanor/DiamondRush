__attribute__((visibility("hidden"))) int alg1_solve(const int* cells, int H, char* out_moves, int out_capacity,
                                                    int* out_is_final);
__attribute__((visibility("hidden"))) int alg2_solve(const int* cells, int H, char* out_moves, int out_capacity,
                                                    int* out_is_final);

extern "C" __attribute__((visibility("default")))
int dr_solve(const int* cells, int n, int use_algorithm_1, char* out_moves, int out_capacity, int* out_is_final) {
    if (n & 7) return -1;
    const int H = n >> 3;
    if (H < 1 || H > 16) return -1;
    unsigned bad = 0;
    int np = 0;
    for (int i = 0; i < n; i++) {
        const unsigned v = (unsigned)cells[i];
        bad |= v > 19;
        np += (v == 10) | (v == 17) | (v == 18);
    }
    if (bad | (np != 1)) return -1;
    return use_algorithm_1 ? alg1_solve(cells, H, out_moves, out_capacity, out_is_final)
                           : alg2_solve(cells, H, out_moves, out_capacity, out_is_final);
}
