#define main lazy_specialized_solver_embedded_main
#include "../src/lazy_specialized_solver.cpp"
#undef main
#include <random>

using namespace qspec;

static std::string move_label(const LazyEngine& e, uint16_t mv) {
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
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    int local_touch_refine = 0;
#endif
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
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        else if (a == "--local-touch-refine") {
            std::string x; val(x);
            if (x == "all") local_touch_refine = -1;
            else { std::stringstream ss(x); char tail=0; if (!(ss >> local_touch_refine) || (ss >> tail)) throw std::runtime_error("invalid local touch refinement: " + x); }
        }
#endif
        else if (a == "--help") {
            std::cout << "lazy_frontier_dump --width 4 --height 3 --walls 3 --samples 500 --seed 12345\n";
            return 0;
        }
    }

    LazyEngine e(W, H, walls, 0, 2, 65536, false, 1, 0, false, false, 0, 18
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        , local_touch_refine
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        , 0, 0
#endif
    );
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    const bool ordered_for_refinement = local_touch_refine != 0;
#else
    const bool ordered_for_refinement = false;
#endif
    auto emit = [&](State s) {
        e.resolve_state(s);
        std::array<LazyEngine::Child, 192> ch{};
        int n = e.generate(s, P1, ch.data(), ordered_for_refinement);
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
                  << ",\"hw\":" << (s.walls_mask & low)
                  << ",\"vw\":" << (s.walls_mask >> e.S)
                  << ",\"moves\":[";
        for (size_t i = 0; i < labels.size(); i++) {
            if (i) std::cout << ',';
            std::cout << '"' << labels[i] << '"';
        }
        std::cout << "]}\n";
    };

    std::mt19937_64 rng(seed);
    State s = e.initial();
    int emitted = 0;
    for (int k = 0; emitted < samples && k < samples * (plies + 5); ++k) {
        e.resolve_state(s);
        Player win;
        if (e.terminal(s, win)) s = e.initial();
        std::array<LazyEngine::Child, 192> ch{};
        int n = e.generate(s, P1, ch.data(), ordered_for_refinement);
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
