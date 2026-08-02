#define main lazy_pareto_solver_embedded_cli_main
#include "../solvers/lazy_pareto_solver.cpp"
#undef main

int main(int argc, char** argv) {
    using namespace qpareto;
    int W=3,H=3,walls=1,tt_bits=18,dominance_bits=16,transition_threshold=1;
    bool use_tt=true; int symmetry_mode=2;
    for(int i=1;i<argc;i++) {
        std::string a=argv[i];
        auto val=[&](auto& x){ if(i+1>=argc) throw std::runtime_error("missing arg"); std::stringstream ss(argv[++i]); ss>>x; };
        if(a=="--width") val(W); else if(a=="--height") val(H); else if(a=="--walls") val(walls);
        else if(a=="--tt-bits") val(tt_bits); else if(a=="--dominance-tt-bits") val(dominance_bits);
        else if(a=="--transition-cache-threshold") val(transition_threshold);
        else if(a=="--no-tt") use_tt=false;
        else if(a=="--no-symmetry") symmetry_mode=0;
        else if(a=="--mirror-only") symmetry_mode=1;
        else if(a=="--no-bounds"||a=="--no-pawn-table") {}
    }
    try {
        LazyEngine e(W,H,walls,1,symmetry_mode,65536,false,transition_threshold);
        ProofSolver ps(e,tt_bits,use_tt,false,2,0,0,unsigned(dominance_bits));
        int p1,p2,r1,r2,turn,target,depth;uint64_t hw,vw;size_t index=0;
        while(std::cin>>p1>>p2>>r1>>r2>>turn>>hw>>vw>>target>>depth) {
            uint64_t mask=hw|(vw<<e.S);uint32_t cfg=e.ensure_config(mask);State s;
            s.walls_mask=mask;s.cfg_id=cfg;s.p[0]=uint8_t(p1);s.p[1]=uint8_t(p2);
            s.walls[0]=uint8_t(r1);s.walls[1]=uint8_t(r2);s.turn=Player(turn);
            Player tw;if(e.terminal(s,tw)){std::cout<<index++<<" "<<int(tw==Player(target))<<" 0 0\n";continue;}
            auto result=ps.solve_from(s,3600.0,depth,depth,target);
            std::cout<<index++<<" "<<int(result.solved&&result.winner==Player(target))<<" "<<result.depth<<" "<<result.timeout<<"\n";
        }
    } catch(const std::exception&ex){std::cerr<<"error: "<<ex.what()<<"\n";return 2;}
    return 0;
}
