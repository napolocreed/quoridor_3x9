#define main lazy_specialized_solver_embedded_main
#include "../../src/lazy_specialized_solver.cpp"
#undef main

#include <unordered_map>

namespace qdfpn {
using namespace qspec;

static constexpr uint32_t INF = 0x3fffffffU;

static inline uint32_t sat_add(uint32_t a, uint32_t b) {
    return (a >= INF || b >= INF || a > INF - b) ? INF : a + b;
}

static inline uint32_t threshold_transfer(uint32_t threshold, uint32_t aggregate, uint32_t child) {
    if (threshold >= INF) return INF;
    // Called only while aggregate < threshold. The selected child contributes to aggregate.
    uint64_t value = uint64_t(threshold) - aggregate + child;
    return value >= INF ? INF : uint32_t(value);
}

struct Key {
    uint64_t canonical = 0;
    uint8_t depth = 0;
    bool operator==(const Key& other) const {
        return canonical == other.canonical && depth == other.depth;
    }
};

struct KeyHash {
    size_t operator()(const Key& key) const noexcept {
        return size_t(mix64(key.canonical ^ (uint64_t(key.depth) * 0x9e3779b97f4a7c15ULL)));
    }
};

struct Node {
    State state{};
    uint32_t child_offset = 0;
    uint16_t child_count = 0;
    uint32_t pn = 1;
    uint32_t dn = 1;
    uint8_t depth = 0;
    bool expanded = false;
    bool busy = false;
};

struct Edge {
    uint32_t child = UINT32_MAX;
    uint16_t move = 0;
    uint16_t prior_pn = 1;
    uint16_t prior_dn = 1;
};

class DfpnSolver {
    LazyEngine& engine_;
    Player target_;
    bool cap_stocks_ = false;
    bool incremental_safe_ = false;
    bool rank_priors_ = false;
    int init_mode_ = 0;
    std::vector<Node> nodes_;
    std::vector<Edge> children_;
    std::unordered_map<Key, uint32_t, KeyHash> index_;
    Clock::time_point deadline_;
    uint64_t calls_ = 0;
    uint64_t expansions_ = 0;
    uint64_t updates_ = 0;
    uint64_t transposition_hits_ = 0;
    uint64_t threshold_returns_ = 0;
    uint64_t stalemates_seen_ = 0;
    uint64_t pending_edges_ = 0;
    uint64_t materialized_edges_ = 0;
    uint64_t max_calls_ = UINT64_MAX;
    size_t max_nodes_ = SIZE_MAX;
    bool timeout_ = false;

    static int relevant_depth(Player turn, Player target, int depth) {
        if (depth <= 0 || ((turn == target) == ((depth & 1) != 0))) return depth;
        return depth - 1;
    }

    void check_budget() {
        ++calls_;
        if (calls_ >= max_calls_) {
            timeout_ = true;
            throw SearchTimeout{};
        }
        if ((calls_ & 4095ULL) == 0 && Clock::now() >= deadline_) {
            timeout_ = true;
            throw SearchTimeout{};
        }
    }

    uint32_t add_node(State state, int depth) {
        engine_.resolve_state(state);
        depth = relevant_depth(state.turn, target_, depth);
        Key key{engine_.canonical_key(state, target_, depth, cap_stocks_), uint8_t(std::max(0, depth))};
        auto it = index_.find(key);
        if (it != index_.end()) {
            ++transposition_hits_;
            return it->second;
        }

        if (nodes_.size() >= max_nodes_) { timeout_ = true; throw SearchTimeout{}; }
        Node node;
        node.state = state;
        node.depth = uint8_t(std::max(0, depth));
        Player winner;
        if (engine_.terminal(state, winner)) {
            node.expanded = true;
            if (winner == target_) {
                node.pn = 0;
                node.dn = INF;
            } else {
                node.pn = INF;
                node.dn = 0;
            }
        } else if (depth <= 0) {
            node.expanded = true;
            node.pn = INF;
            node.dn = 0;
        } else if (init_mode_ > 0) {
            const auto& config = engine_.config_by_id(state.cfg_id);
            unsigned target = target_ == P1 ? 0u : 1u;
            unsigned opponent = 1u - target;
            int target_distance = target == 0 ? config.dist0[state.p[target]] : config.dist1[state.p[target]];
            int opponent_distance = opponent == 0 ? config.dist0[state.p[opponent]] : config.dist1[state.p[opponent]];
            int target_choices = engine_.shortest_options(state, target, config);
            int opponent_choices = engine_.shortest_options(state, opponent, config);
            auto estimate = [&](int distance, int choices) -> uint32_t {
                uint32_t base = uint32_t(std::max(1, distance));
                if (init_mode_ >= 2) base = std::min<uint32_t>(255, base * base);
                if (init_mode_ >= 3) base = std::min<uint32_t>(255, base + uint32_t(std::max(0, choices - 1) * 2));
                return std::max<uint32_t>(1, base);
            };
            node.pn = estimate(target_distance, target_choices);
            node.dn = estimate(opponent_distance, opponent_choices);
        }

        uint32_t id = uint32_t(nodes_.size());
        nodes_.push_back(std::move(node));
        index_.emplace(key, id);
        return id;
    }

    std::pair<uint32_t,uint32_t> edge_numbers(const Edge& edge) const {
        if (edge.child == UINT32_MAX) return {edge.prior_pn, edge.prior_dn};
        const Node& child = nodes_[edge.child];
        if (!child.expanded && rank_priors_) return {edge.prior_pn, edge.prior_dn};
        return {child.pn, child.dn};
    }

    State apply_move(const State& parent, uint16_t move) {
        State child = parent;
        unsigned me = parent.turn == P1 ? 0u : 1u;
        if (move < 0x100) {
            child.p[me] = uint8_t(move);
        } else {
            int wall = int(move - 0x100);
            child.walls_mask |= uint64_t(1) << wall;
            child.cfg_id = UINT32_MAX;
            --child.walls[me];
        }
        child.turn = other(parent.turn);
        return child;
    }

    uint32_t materialize_edge(uint32_t parent_id, uint16_t edge_index) {
        Edge& edge = children_[nodes_[parent_id].child_offset + edge_index];
        if (edge.child != UINT32_MAX) return edge.child;
        State child = apply_move(nodes_[parent_id].state, edge.move);
        engine_.resolve_state(child);
        uint32_t child_id = add_node(child, int(nodes_[parent_id].depth) - 1);
        // add_node may reallocate vectors, so reacquire the edge.
        children_[nodes_[parent_id].child_offset + edge_index].child = child_id;
        ++materialized_edges_;
        return child_id;
    }

    void recompute(uint32_t id) {
        Node& node = nodes_[id];
        if (!node.expanded || node.child_count == 0) return;
        uint32_t pn, dn;
        if (node.state.turn == target_) {
            pn = INF;
            dn = 0;
            for (uint16_t i = 0; i < node.child_count; ++i) {
                auto [child_pn, child_dn] = edge_numbers(children_[node.child_offset + i]);
                pn = std::min(pn, child_pn);
                dn = sat_add(dn, child_dn);
            }
        } else {
            pn = 0;
            dn = INF;
            for (uint16_t i = 0; i < node.child_count; ++i) {
                auto [child_pn, child_dn] = edge_numbers(children_[node.child_offset + i]);
                pn = sat_add(pn, child_pn);
                dn = std::min(dn, child_dn);
            }
        }
        node.pn = pn;
        node.dn = dn;
        ++updates_;
    }

    void expand(uint32_t id) {
        Node snapshot = nodes_[id];
        if (snapshot.expanded) return;
        std::array<LazyEngine::Child, 192> generated{};
        int count = engine_.generate(snapshot.state, target_, generated.data(), true);
        std::vector<Edge> child_edges;
        child_edges.reserve(count);
        for (int i = 0; i < count; ++i) {
            Edge edge;
            edge.move = generated[i].move;
            if (rank_priors_) {
                uint16_t rank = uint16_t(std::min(255, i + 1));
                if (snapshot.state.turn == target_) edge.prior_pn = rank;
                else edge.prior_dn = rank;
            }
            if (incremental_safe_ && generated[i].s.cfg_id == UINT32_MAX) {
                ++pending_edges_;
            } else {
                edge.child = add_node(generated[i].s, int(snapshot.depth) - 1);
            }
            child_edges.push_back(edge);
        }
        uint32_t offset = uint32_t(children_.size());
        children_.insert(children_.end(), child_edges.begin(), child_edges.end());
        Node& node = nodes_[id];
        node.child_offset = offset;
        node.child_count = uint16_t(count);
        node.expanded = true;
        if (count == 0) {
            ++stalemates_seen_;
            node.pn = INF;
            node.dn = 0;
        } else {
            recompute(id);
        }
        ++expansions_;
    }

    struct Selected {
        uint16_t edge_index = 0;
        uint32_t second = INF;
    };

    Selected select_child(const Node& node) const {
        Selected selected{0, INF};
        auto metric = [&](uint16_t edge_index) {
            auto [pn, dn] = edge_numbers(children_[node.child_offset + edge_index]);
            return node.state.turn == target_ ? pn : dn;
        };
        uint32_t best = metric(0);
        for (uint16_t i = 1; i < node.child_count; ++i) {
            uint32_t value = metric(i);
            if (value < best) {
                selected.second = best;
                selected.edge_index = i;
                best = value;
            } else if (value < selected.second) {
                selected.second = value;
            }
        }
        return selected;
    }

    void dfpn(uint32_t id, uint32_t threshold_pn, uint32_t threshold_dn) {
        check_budget();
        Node& entry = nodes_[id];
        if (entry.busy) {
            // Depth is part of the key, so this should be unreachable. Keep a hard guard instead of
            // silently manufacturing proof numbers if future changes violate that invariant.
            throw std::runtime_error("DF-PN recursion cycle despite depth-keyed state");
        }
        if (!entry.expanded) expand(id);
        recompute(id);
        if (nodes_[id].pn >= threshold_pn || nodes_[id].dn >= threshold_dn ||
            nodes_[id].pn == 0 || nodes_[id].dn == 0) {
            ++threshold_returns_;
            return;
        }

        nodes_[id].busy = true;
        try {
            while (nodes_[id].pn < threshold_pn && nodes_[id].dn < threshold_dn &&
                   nodes_[id].pn != 0 && nodes_[id].dn != 0) {
                Node snapshot = nodes_[id];
                Selected selected = select_child(snapshot);
                Edge selected_edge = children_[snapshot.child_offset + selected.edge_index];
                auto [current_child_pn, current_child_dn] = edge_numbers(selected_edge);
                uint32_t child_threshold_pn;
                uint32_t child_threshold_dn;

                if (snapshot.state.turn == target_) {
                    child_threshold_pn = std::min(threshold_pn, sat_add(selected.second, 1));
                    child_threshold_dn = threshold_transfer(threshold_dn, snapshot.dn, current_child_dn);
                } else {
                    child_threshold_pn = threshold_transfer(threshold_pn, snapshot.pn, current_child_pn);
                    child_threshold_dn = std::min(threshold_dn, sat_add(selected.second, 1));
                }

                child_threshold_pn = std::max(child_threshold_pn, sat_add(current_child_pn, 1));
                child_threshold_dn = std::max(child_threshold_dn, sat_add(current_child_dn, 1));
                uint32_t selected_id = materialize_edge(id, selected.edge_index);
                dfpn(selected_id, child_threshold_pn, child_threshold_dn);
                recompute(id);
                check_budget();
            }
        } catch (...) {
            nodes_[id].busy = false;
            throw;
        }
        nodes_[id].busy = false;
    }

public:
    struct Result {
        bool solved = false;
        bool value = false;
        bool timeout = false;
        uint32_t pn = 1;
        uint32_t dn = 1;
        uint64_t calls = 0;
        uint64_t expansions = 0;
        uint64_t updates = 0;
        uint64_t transposition_hits = 0;
        uint64_t threshold_returns = 0;
        uint64_t stalemates_seen = 0;
        uint64_t pending_edges = 0;
        uint64_t materialized_edges = 0;
        size_t graph_nodes = 0;
        size_t graph_edges = 0;
        double seconds = 0;
    };

    DfpnSolver(LazyEngine& engine, Player target, size_t reserve_nodes, bool cap_stocks, int init_mode, size_t max_nodes, bool incremental_safe, bool rank_priors)
        : engine_(engine), target_(target), cap_stocks_(cap_stocks), incremental_safe_(incremental_safe), rank_priors_(rank_priors), init_mode_(init_mode), max_nodes_(max_nodes) {
        nodes_.reserve(std::min(reserve_nodes, max_nodes_));
        children_.reserve(std::min(reserve_nodes * 3, max_nodes_ * 3));
        index_.reserve(std::min(reserve_nodes * 2, max_nodes_ * 2));
    }

    Result solve(State root, int depth, double seconds, uint64_t max_calls) {
        auto start = Clock::now();
        deadline_ = start + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
        max_calls_ = max_calls;
        uint32_t root_id = add_node(root, depth);
        try {
            dfpn(root_id, INF, INF);
        } catch (const SearchTimeout&) {
            timeout_ = true;
        }
        Result result;
        result.pn = nodes_[root_id].pn;
        result.dn = nodes_[root_id].dn;
        result.solved = result.pn == 0 || result.dn == 0;
        result.value = result.pn == 0;
        result.timeout = timeout_ || (!result.solved && Clock::now() >= deadline_);
        result.calls = calls_;
        result.expansions = expansions_;
        result.updates = updates_;
        result.transposition_hits = transposition_hits_;
        result.threshold_returns = threshold_returns_;
        result.stalemates_seen = stalemates_seen_;
        result.pending_edges = pending_edges_;
        result.materialized_edges = materialized_edges_;
        result.graph_nodes = nodes_.size();
        result.graph_edges = children_.size();
        result.seconds = std::chrono::duration<double>(Clock::now() - start).count();
        return result;
    }
};

} // namespace qdfpn

int main(int argc, char** argv) {
    using namespace qspec;
    using namespace qdfpn;
    int width = 4, height = 7, walls = 7, depth = 12, target_arg = 1;
    int order = 1, symmetry = 2, transition_threshold = 1, choice_weight = 0;
    double seconds = 60;
    size_t reserve_nodes = 1'000'000;
    size_t max_nodes = 10'000'000;
    uint64_t max_calls = UINT64_MAX;
    bool cap_stocks = false;
    bool incremental_safe = false;
    bool rank_priors = false;
    int init_mode = 0;
    std::string root_move, second_move, third_move;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto value = [&](auto& x) {
            if (++i >= argc) throw std::runtime_error("missing argument value");
            std::stringstream stream(argv[i]);
            stream >> x;
        };
        if (arg == "--width") value(width);
        else if (arg == "--height") value(height);
        else if (arg == "--walls") value(walls);
        else if (arg == "--depth") value(depth);
        else if (arg == "--target") value(target_arg);
        else if (arg == "--seconds") value(seconds);
        else if (arg == "--reserve-nodes") value(reserve_nodes);
        else if (arg == "--max-nodes") value(max_nodes);
        else if (arg == "--max-calls") value(max_calls);
        else if (arg == "--order") value(order);
        else if (arg == "--symmetry") value(symmetry);
        else if (arg == "--transition-cache-threshold") value(transition_threshold);
        else if (arg == "--path-choice-weight") value(choice_weight);
        else if (arg == "--horizon-stock-cap") cap_stocks = true;
        else if (arg == "--incremental-cycle-safe") incremental_safe = true;
        else if (arg == "--rank-priors") rank_priors = true;
        else if (arg == "--init-mode") value(init_mode);
        else if (arg == "--root-move") value(root_move);
        else if (arg == "--second-move") value(second_move);
        else if (arg == "--third-move") value(third_move);
        else if (arg == "--help") {
            std::cout << "lazy_dfpn_solver --width 4 --height 7 --walls 7 --depth 16 --target 1 "
                         "[--root-move P(5,2) --second-move P(1,2) --third-move H(5,2)]\n";
            return 0;
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }

    try {
        Player target = target_arg == 2 ? P2 : P1;
        LazyEngine engine(width, height, walls, order, symmetry, 65536, false,
                          transition_threshold, choice_weight, incremental_safe, incremental_safe);
        State root = engine.initial();
        auto parse_move = [&](const std::string& text) -> uint16_t {
            char kind = 0, tail = 0;
            int row = -1, col = -1;
            if (std::sscanf(text.c_str(), " %c(%d,%d)%c", &kind, &row, &col, &tail) != 3)
                throw std::runtime_error("invalid move label: " + text);
            if (kind == 'P') {
                if (row < 0 || row >= engine.H || col < 0 || col >= engine.W)
                    throw std::runtime_error("pawn move out of range: " + text);
                return uint16_t(row * engine.W + col);
            }
            if (kind == 'H' || kind == 'V') {
                if (row < 0 || row >= engine.R || col < 0 || col >= engine.C)
                    throw std::runtime_error("wall move out of range: " + text);
                int orientation = kind == 'V';
                return uint16_t(0x100 + orientation * engine.S + row * engine.C + col);
            }
            throw std::runtime_error("invalid move kind: " + text);
        };
        auto choose = [&](State state, const std::string& wanted, const char* label) {
            if (wanted.empty()) return state;
            engine.resolve_state(state);
            std::array<LazyEngine::Child, 192> children{};
            int count = engine.generate(state, target, children.data(), true);
            uint16_t code = parse_move(wanted);
            for (int i = 0; i < count; ++i) {
                if (children[i].move == code) {
                    std::cerr << "forcing " << label << "=" << wanted << " index=" << i << "\n";
                    return children[i].s;
                }
            }
            throw std::runtime_error(std::string("illegal named ") + label + ": " + wanted);
        };
        root = choose(root, root_move, "root");
        root = choose(root, second_move, "second");
        root = choose(root, third_move, "third");

        DfpnSolver solver(engine, target, reserve_nodes, cap_stocks, init_mode, max_nodes, incremental_safe, rank_priors);
        auto result = solver.solve(root, depth, seconds, max_calls);
        std::cout << "solved=" << result.solved
                  << " value=" << result.value
                  << " timeout=" << result.timeout
                  << " pn=" << result.pn
                  << " dn=" << result.dn
                  << " calls=" << result.calls
                  << " expansions=" << result.expansions
                  << " updates=" << result.updates
                  << " graph_nodes=" << result.graph_nodes
                  << " graph_edges=" << result.graph_edges
                  << " transposition_hits=" << result.transposition_hits
                  << " threshold_returns=" << result.threshold_returns
                  << " stalemates_seen=" << result.stalemates_seen
                  << " pending_edges=" << result.pending_edges
                  << " materialized_edges=" << result.materialized_edges
                  << " seconds=" << result.seconds
                  << " cache_configs=" << engine.cache_size()
                  << "\n";
        return result.solved ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << "\n";
        return 2;
    }
}
