#define main lazy_specialized_solver_embedded_cli_main
#include "../src/lazy_specialized_solver.cpp"
#undef main

int main(int argc, char** argv) {
    using namespace qspec;
    int W=3,H=3,walls=1,tt_bits=18,transition_threshold=1,path_choice_weight=0,path_flow_weight=0,path_flow_cache_bits=18;
    size_t cache_reserve=65536;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    int local_touch_refine=0;
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    int zero_wall_threshold=0,zero_wall_max=4096;
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
    int tt_hint_first_mode=0;bool tt_hint_transform=true;
#endif
    bool use_tt=true,defer_cycle_safe=false; int symmetry_mode=2;
    for(int i=1;i<argc;i++) {
        std::string a=argv[i];
        auto val=[&](auto& x){ if(i+1>=argc) throw std::runtime_error("missing arg"); std::stringstream ss(argv[++i]); ss>>x; };
        if(a=="--width") val(W); else if(a=="--height") val(H); else if(a=="--walls") val(walls);
        else if(a=="--tt-bits") val(tt_bits); else if(a=="--transition-cache-threshold") val(transition_threshold);
        else if(a=="--cache-reserve") val(cache_reserve);
        else if(a=="--path-choice-weight") val(path_choice_weight);
        else if(a=="--path-flow-weight") val(path_flow_weight);
        else if(a=="--path-flow-cache-bits") val(path_flow_cache_bits);
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        else if(a=="--local-touch-refine") {
            std::string x; val(x);
            if(x=="all") local_touch_refine=-1;
            else { std::stringstream ss(x); char tail=0; if(!(ss>>local_touch_refine)||(ss>>tail)) throw std::runtime_error("invalid local touch refinement: "+x); }
        }
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        else if(a=="--zero-wall-tablebase-threshold") val(zero_wall_threshold);
        else if(a=="--zero-wall-tablebase-max") val(zero_wall_max);
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        else if(a=="--tt-hint-first-mode") {std::string x;val(x);if(x=="off")tt_hint_first_mode=0;else if(x=="all")tt_hint_first_mode=1;else if(x=="opponent")tt_hint_first_mode=2;else if(x=="target")tt_hint_first_mode=3;else if(x=="opponent-pawn")tt_hint_first_mode=4;else if(x=="opponent-wall")tt_hint_first_mode=5;else if(x=="order-only")tt_hint_first_mode=6;else throw std::runtime_error("invalid TT hint-first mode: "+x);}
        else if(a=="--no-tt-hint-first") tt_hint_first_mode=0;
        else if(a=="--no-tt-hint-transform") tt_hint_transform=false;
#endif
        else if(a=="--no-tt") use_tt=false;
        else if(a=="--defer-cycle-safe") defer_cycle_safe=true;
        else if(a=="--no-symmetry") symmetry_mode=0;
        else if(a=="--mirror-only") symmetry_mode=1;
        else if(a=="--no-bounds"||a=="--no-pawn-table") {}
        else if(a=="--help") {
            std::cout << "TSV stdin: p1 p2 remaining1 remaining2 turn hwalls vwalls target depth\n";
            return 0;
        }
    }
    try {
        LazyEngine e(W,H,walls,1,symmetry_mode,cache_reserve,false,transition_threshold,path_choice_weight,false,defer_cycle_safe,path_flow_weight,path_flow_cache_bits
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
            ,local_touch_refine
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
            ,zero_wall_threshold,zero_wall_max
#endif
        );
        ProofSolver ps(e,tt_bits,use_tt,false,2,0,0
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
            ,tt_hint_first_mode,tt_hint_transform
#endif
        );
        int p1,p2,r1,r2,turn,target,depth;
        uint64_t hw,vw;
        size_t index=0;
        while(std::cin>>p1>>p2>>r1>>r2>>turn>>hw>>vw>>target>>depth) {
            uint64_t mask=hw|(vw<<e.S);
            uint32_t cfg=e.ensure_config(mask);
            State s;
            s.walls_mask=mask;s.cfg_id=cfg;s.p[0]=uint8_t(p1);s.p[1]=uint8_t(p2);
            s.walls[0]=uint8_t(r1);s.walls[1]=uint8_t(r2);s.turn=Player(turn);
            Player terminal_winner;
            if(e.terminal(s,terminal_winner)) {
                std::cout<<index++<<" "<<int(terminal_winner==Player(target))<<" 0 0\n";
                continue;
            }
            auto result=ps.solve_from(s,3600.0,depth,depth,target);
            std::cout<<index++<<" "<<int(result.solved && result.winner==Player(target))
                     <<" "<<result.depth<<" "<<result.timeout<<"\n";
        }
    } catch(const std::exception& ex) {
        std::cerr<<"error: "<<ex.what()<<"\n";
        return 2;
    }
    return 0;
}
