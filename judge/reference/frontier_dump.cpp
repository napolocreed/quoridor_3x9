#define main frontier_solver_embedded_main
#include "../src/frontier_solver.cpp"
#undef main
#include <random>

using namespace qfrontier;

static std::string move_label(const Engine& e, uint16_t mv) {
    std::ostringstream o;
    if (mv < 0x100) {
        o << "P:" << unsigned(mv);
    } else {
        int bit = int(mv) - 0x100;
        int ori = bit / e.S;
        int z = bit % e.S;
        o << (ori ? "V:" : "H:") << (z / e.C) << ":" << (z % e.C);
    }
    return o.str();
}

int main(int argc, char** argv) {
    int W = 4, H = 3, walls = 3, samples = 100, plies = 25;
    bool exhaustive = false;
    uint64_t seed = 0x5eed1234ULL;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        auto val = [&](auto& x) {
            if (++i >= argc) throw std::runtime_error("missing value");
            std::stringstream ss(argv[i]);
            ss >> x;
        };
        if (a == "--width") val(W);
        else if (a == "--height") val(H);
        else if (a == "--walls") val(walls);
        else if (a == "--samples") val(samples);
        else if (a == "--plies") val(plies);
        else if (a == "--seed") val(seed);
        else if (a == "--exhaustive") exhaustive = true;
        else if (a == "--help") {
            std::cout << "frontier_dump --width 4 --height 3 --walls 3 --samples 500 --seed 12345\n";
            return 0;
        }
    }

    Engine e(W, H, walls, 0);
    e.precompute(true);
    auto emit = [&](const State& s) {
        std::array<Engine::Child, 192> ch{};
        int n = e.generate(s, P1, ch.data(), false);
        uint64_t mask = e.cfg_masks[s.cfg];
        uint64_t low = (e.S == 64 ? ~0ULL : ((1ULL << e.S) - 1ULL));
        std::vector<std::string> labels;
        labels.reserve(n);
        for (int i = 0; i < n; i++) labels.push_back(move_label(e, ch[i].move));
        std::sort(labels.begin(), labels.end());
        std::cout << "{\"p1\":" << unsigned(s.p[0])
                  << ",\"p2\":" << unsigned(s.p[1])
                  << ",\"r1\":" << unsigned(s.walls[0])
                  << ",\"r2\":" << unsigned(s.walls[1])
                  << ",\"turn\":" << unsigned(s.turn)
                  << ",\"hw\":" << (mask & low)
                  << ",\"vw\":" << (mask >> e.S)
                  << ",\"moves\":[";
        for (size_t i = 0; i < labels.size(); i++) {
            if (i) std::cout << ',';
            std::cout << '"' << labels[i] << '"';
        }
        std::cout << "]}\n";
    };

    if (exhaustive) {
        for (uint32_t cfg = 0; cfg < e.cfg_masks.size(); ++cfg) {
            int placed = e.cfg_placed[cfg];
            int remain_total = 2 * walls - placed;
            for (int r1 = 0; r1 <= walls; ++r1) {
                int r2 = remain_total - r1;
                if (r2 < 0 || r2 > walls) continue;
                for (int p1 = 0; p1 < e.N; ++p1) {
                    if (e.distance(P1,cfg,uint8_t(p1)) == 255) continue;
                    for (int p2 = 0; p2 < e.N; ++p2) {
                        if (p1 == p2 || e.distance(P2,cfg,uint8_t(p2)) == 255) continue;
                        if (e.row(uint8_t(p1)) == 0 || e.row(uint8_t(p2)) == e.H - 1) continue;
                        for (int turn = 0; turn < 2; ++turn) {
                            State st; st.cfg=cfg; st.p[0]=uint8_t(p1); st.p[1]=uint8_t(p2);
                            st.walls[0]=uint8_t(r1); st.walls[1]=uint8_t(r2); st.turn=Player(turn);
                            emit(st);
                        }
                    }
                }
            }
        }
        return 0;
    }

    std::mt19937_64 rng(seed);
    State s = e.initial();
    int emitted = 0;
    for (int k = 0; emitted < samples && k < samples * (plies + 5); ++k) {
        Player win;
        if (e.terminal(s, win)) s = e.initial();
        std::array<Engine::Child, 192> ch{};
        int n = e.generate(s, P1, ch.data(), false);
        if (n <= 0) {
            s = e.initial();
            continue;
        }
        emit(s);
        ++emitted;
        std::uniform_int_distribution<int> pick(0, n - 1);
        s = ch[pick(rng)].s;
        if ((k + 1) % plies == 0) s = e.initial();
    }
}
