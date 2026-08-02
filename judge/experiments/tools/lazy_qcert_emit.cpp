#include <cmath>
#include <deque>
#include <filesystem>
#include <fstream>
#include <optional>
#include <random>
#include <type_traits>
#include <unordered_map>

#define main lazy_specialized_solver_embedded_main
#include "../../src/lazy_specialized_solver.cpp"
#undef main

namespace {
using namespace qspec;

struct CertEntry {
    State state{};
    int budget = -1;
    uint16_t move = 0xffff;
    bool dirty = false;
};

class CertificateBuilder {
    LazyEngine& engine_;
    ProofSolver& oracle_;
    Player target_;
    bool exact_dmin_;
    std::vector<std::array<LazyEngine::Child,192>> scratch_;
    std::unordered_map<uint64_t,CertEntry,U64Hash> entries_;
    std::deque<uint64_t> work_;
    uint64_t root_key_ = 0;
    std::optional<uint16_t> root_witness_;

    uint64_t raw_key(const State& state) const {
        if(2*engine_.S>39||engine_.walls_each>31)throw std::runtime_error("certificate raw key domain exceeded");
        uint64_t key=state.walls_mask;
        key|=uint64_t(state.p[0])<<39;
        key|=uint64_t(state.p[1])<<44;
        key|=uint64_t(state.walls[0])<<49;
        key|=uint64_t(state.walls[1])<<54;
        key|=uint64_t(state.turn)<<59;
        return key;
    }

    bool terminal_win(const State& state) const {
        Player winner;
        return engine_.terminal(state,winner)&&winner==target_;
    }

    bool prove(State state,int budget) {
        if(budget<=0)return terminal_win(state);
        return oracle_.prove(state,target_,budget,scratch_,0);
    }

    int exact_dmin(State state,int upper) {
        Player winner;
        if(engine_.terminal(state,winner))return winner==target_?0:-1;
        upper=ProofSolver::target_relevant_depth(state.turn,target_,upper);
        const int first=state.turn==target_?1:2;
        if(upper<first||!prove(state,upper))return -1;
        int lo=0,hi=(upper-first)/2;
        while(lo<hi){
            int mid=lo+(hi-lo)/2;
            int depth=first+2*mid;
            if(prove(state,depth))hi=mid;else lo=mid+1;
        }
        return first+2*lo;
    }

    void ensure(State state,int upper) {
        engine_.resolve_state(state);
        Player winner;
        if(engine_.terminal(state,winner)){
            if(winner!=target_)throw std::runtime_error("strategy reaches an opponent terminal");
            return;
        }
        upper=ProofSolver::target_relevant_depth(state.turn,target_,upper);
        if(upper<=0)throw std::runtime_error("non-terminal certificate child has no positive budget");
        const uint64_t key=raw_key(state);
        auto found=entries_.find(key);
        if(exact_dmin_&&found!=entries_.end()){
            if(found->second.budget>upper)throw std::runtime_error("cached dmin exceeds incoming certified budget");
            return;
        }
        if(!exact_dmin_&&found!=entries_.end()&&found->second.budget<=upper)return;

        int budget=upper;
        if(exact_dmin_){
            budget=exact_dmin(state,upper);
            if(budget<1)throw std::runtime_error("state is not winning within its incoming budget");
        }else if(!(key==root_key_&&root_witness_)&&!prove(state,budget)){
            throw std::runtime_error("rank propagation reached a state not proved within its budget");
        }

        if(found==entries_.end()){
            entries_.emplace(key,CertEntry{state,budget,0xffff,true});
        }else{
            found->second.budget=budget;
            found->second.move=0xffff;
            found->second.dirty=true;
        }
        work_.push_back(key);
    }

    void expand(uint64_t key) {
        auto it=entries_.find(key);
        if(it==entries_.end()||!it->second.dirty)return;
        it->second.dirty=false;
        State state=it->second.state;
        const int budget=it->second.budget;
        std::array<LazyEngine::Child,192> children{};
        int count=engine_.generate(state,target_,children.data(),false);
        if(count<=0)throw std::runtime_error("certificate expansion reached a stalemate");

        if(state.turn==target_){
            int chosen=-1;
            if(key==root_key_&&root_witness_){
                for(int i=0;i<count;i++)if(children[i].move==*root_witness_){chosen=i;break;}
                if(chosen<0)throw std::runtime_error("root witness is not legal");
                Player winner;
                bool terminal=engine_.terminal(children[chosen].s,winner);
                if((terminal&&winner!=target_)||(!terminal&&!prove(children[chosen].s,budget-1))){
                    throw std::runtime_error("root witness does not prove the requested bound");
                }
            }else{
                for(int i=0;i<count;i++){
                    Player winner;
                    bool terminal=engine_.terminal(children[i].s,winner);
                    if((terminal&&winner==target_)||(!terminal&&prove(children[i].s,budget-1))){chosen=i;break;}
                }
            }
            if(chosen<0)throw std::runtime_error("proved target node has no certifiable child");
            entries_.at(key).move=children[chosen].move;
            Player winner;
            if(!engine_.terminal(children[chosen].s,winner))ensure(children[chosen].s,budget-1);
            else if(winner!=target_)throw std::runtime_error("chosen move loses immediately");
        }else{
            entries_.at(key).move=0xffff;
            for(int i=0;i<count;i++){
                Player winner;
                if(engine_.terminal(children[i].s,winner)){
                    if(winner!=target_)throw std::runtime_error("opponent has an immediate winning response");
                }else ensure(children[i].s,budget-1);
            }
        }
    }

    std::string move_label(uint16_t move) const {
        std::ostringstream out;
        if(move<0x100)out<<"P:"<<unsigned(move);
        else{
            int wall=int(move)-0x100,orientation=wall/engine_.S,slot=wall%engine_.S;
            out<<(orientation?"V:":"H:")<<(slot/engine_.C)<<":"<<(slot%engine_.C);
        }
        return out.str();
    }

    void write_state(std::ostream& out,const State& state) const {
        const uint64_t low=(uint64_t(1)<<engine_.S)-1;
        out<<"\"p1\":"<<unsigned(state.p[0])
           <<",\"p2\":"<<unsigned(state.p[1])
           <<",\"r1\":"<<unsigned(state.walls[0])
           <<",\"r2\":"<<unsigned(state.walls[1])
           <<",\"turn\":"<<unsigned(state.turn)
           <<",\"hw\":"<<(state.walls_mask&low)
           <<",\"vw\":"<<(state.walls_mask>>engine_.S);
    }

public:
    CertificateBuilder(LazyEngine& engine,ProofSolver& oracle,Player target,int max_depth,
                       bool exact_dmin,size_t reserve,std::optional<uint16_t> root_witness)
        :engine_(engine),oracle_(oracle),target_(target),
         exact_dmin_(exact_dmin),scratch_(size_t(max_depth)+2),root_witness_(root_witness){
        entries_.reserve(reserve);
    }

    int build(State root,int upper) {
        engine_.resolve_state(root);
        root_key_=raw_key(root);
        ensure(root,upper);
        uint64_t expansions=0;
        while(!work_.empty()){
            uint64_t key=work_.front();work_.pop_front();
            expand(key);
            if((++expansions&((1ULL<<20)-1))==0){
                std::cerr<<"qcert_progress expansions="<<expansions<<" nodes="<<entries_.size()
                         <<" pending="<<work_.size()<<" proof_nodes="<<oracle_.node_count()<<"\n";
            }
        }
        return entries_.at(root_key_).budget;
    }

    std::pair<uint64_t,uint64_t> validate() {
        uint64_t edges=0,target_nodes=0;
        for(const auto& [key,entry]:entries_){
            (void)key;
            std::array<LazyEngine::Child,192> children{};
            int count=engine_.generate(entry.state,target_,children.data(),false);
            if(count<=0||entry.budget<1)throw std::runtime_error("invalid final certificate node");
            auto check_child=[&](const State& child){
                Player winner;
                if(engine_.terminal(child,winner)){
                    if(winner!=target_)throw std::runtime_error("final certificate contains a losing terminal edge");
                    return;
                }
                auto found=entries_.find(raw_key(child));
                if(found==entries_.end()||found->second.budget>entry.budget-1){
                    throw std::runtime_error("final certificate has a missing or non-decreasing edge");
                }
            };
            if(entry.state.turn==target_){
                ++target_nodes;
                auto chosen=std::find_if(children.begin(),children.begin()+count,[&](const auto& child){return child.move==entry.move;});
                if(chosen==children.begin()+count)throw std::runtime_error("final target move is not legal");
                check_child(chosen->s);++edges;
            }else for(int i=0;i<count;i++){check_child(children[i].s);++edges;}
        }
        return {target_nodes,edges};
    }

    void write(const std::filesystem::path& output,const State& root,int header_bound) const {
        if(std::filesystem::exists(output))throw std::runtime_error("refusing to overwrite existing certificate");
        std::random_device entropy;
        uint64_t token=(uint64_t(entropy())<<32)^uint64_t(entropy())^
                       uint64_t(Clock::now().time_since_epoch().count());
        std::filesystem::path partial=output;
        partial += ".partial."+std::to_string(token);
        if(std::filesystem::exists(partial))throw std::runtime_error("partial certificate name collision");
        std::ofstream out(partial,std::ios::binary);
        if(!out)throw std::runtime_error("cannot open partial certificate");
        out<<"{\"type\":\"header\",\"format\":\"qcert-1\",\"width\":"<<engine_.W
           <<",\"height\":"<<engine_.H<<",\"walls\":"<<engine_.walls_each
           <<",\"target\":"<<unsigned(target_)<<",\"bound\":"<<header_bound<<",\"root\":{";
        write_state(out,root);out<<"}}\n";
        std::vector<uint64_t> keys;keys.reserve(entries_.size());
        for(const auto& [key,entry]:entries_){(void)entry;keys.push_back(key);}
        std::sort(keys.begin(),keys.end());
        for(uint64_t key:keys){
            const auto& entry=entries_.at(key);
            out<<"{\"type\":\"node\",";write_state(out,entry.state);out<<",\"d\":"<<entry.budget;
            if(entry.state.turn==target_)out<<",\"move\":\""<<move_label(entry.move)<<"\"";
            out<<"}\n";
        }
        out.flush();
        if(!out)throw std::runtime_error("certificate write failed");
        out.close();
        if(!out)throw std::runtime_error("certificate close failed");
        std::error_code install_error;
        std::filesystem::create_hard_link(partial,output,install_error);
        if(install_error){
            std::error_code ignored;
            std::filesystem::remove(partial,ignored);
            throw std::runtime_error("cannot install certificate without overwriting: "+install_error.message());
        }
        std::error_code cleanup_error;
        std::filesystem::remove(partial,cleanup_error);
        if(cleanup_error)std::cerr<<"warning: installed certificate but could not remove "<<partial<<"\n";
    }

    size_t size() const{return entries_.size();}
};

uint16_t parse_move(const LazyEngine& engine,const std::string& text) {
    char kind=0,tail=0;int row=-1,column=-1;
    if(std::sscanf(text.c_str()," %c(%d,%d)%c",&kind,&row,&column,&tail)!=3)throw std::runtime_error("invalid named move: "+text);
    if(kind=='P'){
        if(row<0||row>=engine.H||column<0||column>=engine.W)throw std::runtime_error("pawn move outside board");
        return uint16_t(row*engine.W+column);
    }
    if(kind=='H'||kind=='V'){
        if(row<0||row>=engine.R||column<0||column>=engine.C)throw std::runtime_error("wall move outside board");
        return uint16_t(0x100+(kind=='V'?engine.S:0)+row*engine.C+column);
    }
    throw std::runtime_error("unknown move kind: "+text);
}

State apply_named(LazyEngine& engine,State state,Player target,const std::string& text) {
    engine.resolve_state(state);
    uint16_t wanted=parse_move(engine,text);
    std::array<LazyEngine::Child,192> children{};
    int count=engine.generate(state,target,children.data(),false);
    for(int i=0;i<count;i++)if(children[i].move==wanted)return children[i].s;
    throw std::runtime_error("named prefix move is not legal: "+text);
}
} // namespace

int main(int argc,char** argv) {
    using namespace qspec;
    int width=3,height=3,walls=1,target_arg=0,bound=-1,tt_bits=24,tt_ways=2;
    int transition_threshold=1,path_choice_weight=0,path_flow_weight=0,path_flow_cache_bits=18;
    int order=1,symmetry=2;size_t cache_reserve=65536,certificate_reserve=65536;
    double seconds=3600;std::string output,budget_mode="rank",root_move,second_move,third_move,witness_move;
    try{
    for(int i=1;i<argc;i++){
        std::string arg=argv[i];
        auto value=[&](auto& out){
            if(i+1>=argc)throw std::runtime_error("missing argument value");
            if constexpr(std::is_same_v<std::decay_t<decltype(out)>,std::string>)out=argv[++i];
            else{std::stringstream in(argv[++i]);in>>out;if(!in||!in.eof())throw std::runtime_error("invalid argument value");}
        };
        if(arg=="--width")value(width);else if(arg=="--height")value(height);else if(arg=="--walls")value(walls);
        else if(arg=="--target")value(target_arg);else if(arg=="--bound")value(bound);else if(arg=="--output")value(output);
        else if(arg=="--seconds")value(seconds);else if(arg=="--tt-bits")value(tt_bits);else if(arg=="--tt-ways")value(tt_ways);
        else if(arg=="--cache-reserve")value(cache_reserve);else if(arg=="--certificate-reserve")value(certificate_reserve);
        else if(arg=="--transition-cache-threshold")value(transition_threshold);else if(arg=="--path-choice-weight")value(path_choice_weight);
        else if(arg=="--path-flow-weight")value(path_flow_weight);else if(arg=="--path-flow-cache-bits")value(path_flow_cache_bits);
        else if(arg=="--order")value(order);else if(arg=="--budget-mode")value(budget_mode);
        else if(arg=="--root-move")value(root_move);else if(arg=="--second-move")value(second_move);else if(arg=="--third-move")value(third_move);
        else if(arg=="--witness-move")value(witness_move);else if(arg=="--no-symmetry")symmetry=0;else if(arg=="--mirror-only")symmetry=1;
        else if(arg=="--no-bounds"||arg=="--no-pawn-table"){}
        else if(arg=="--help"){
            std::cout<<"lazy_qcert_emit --width 3 --height 9 --walls 10 --target 1 --bound 35 --witness-move P(7,1) --output cert.jsonl [--budget-mode rank|exact-dmin]\n";
            return 0;
        }else throw std::runtime_error("unknown argument: "+arg);
    }
        if(target_arg!=1&&target_arg!=2)throw std::runtime_error("--target must be 1 or 2");
        if(bound<1||bound>=255)throw std::runtime_error("--bound must be 1..254");
        if(walls<0||walls>31)throw std::runtime_error("--walls must be 0..31");
        if(tt_bits<10||tt_bits>30)throw std::runtime_error("--tt-bits must be 10..30");
        if(tt_ways!=2&&tt_ways!=4)throw std::runtime_error("--tt-ways must be 2 or 4");
        if(!std::isfinite(seconds)||!(seconds>0))throw std::runtime_error("--seconds must be finite and positive");
        if(output.empty())throw std::runtime_error("--output is required");
        if(budget_mode!="rank"&&budget_mode!="exact-dmin")throw std::runtime_error("unknown budget mode");
        if(root_move.empty()&&!second_move.empty())throw std::runtime_error("--second-move requires --root-move");
        if(second_move.empty()&&!third_move.empty())throw std::runtime_error("--third-move requires --second-move");
        Player target=target_arg==1?P1:P2;
        LazyEngine engine(width,height,walls,order,symmetry,cache_reserve,false,transition_threshold,
                          path_choice_weight,false,false,path_flow_weight,path_flow_cache_bits);
        State root=engine.initial();
        if(!root_move.empty())root=apply_named(engine,root,target,root_move);
        if(!second_move.empty())root=apply_named(engine,root,target,second_move);
        if(!third_move.empty())root=apply_named(engine,root,target,third_move);
        Player root_winner;
        if(engine.terminal(root,root_winner))throw std::runtime_error("certificate root must be non-terminal");
        if(!witness_move.empty()&&root.turn!=target)throw std::runtime_error("--witness-move requires target to move at certificate root");
        std::optional<uint16_t> witness;
        if(!witness_move.empty())witness=parse_move(engine,witness_move);

        ProofSolver oracle(engine,tt_bits,true,false,tt_ways,0,0);
        auto proof=oracle.solve_from(root,seconds,bound,bound,int(target));
        if(proof.timeout)throw std::runtime_error("root proof timed out");
        if(!proof.solved||proof.winner!=target)throw std::runtime_error("root is not proved for target at requested bound");
        const uint64_t root_proof_nodes=oracle.node_count();

        CertificateBuilder builder(engine,oracle,target,bound,budget_mode=="exact-dmin",certificate_reserve,witness);
        int root_budget=builder.build(root,proof.depth);
        auto [target_nodes,edges]=builder.validate();
        builder.write(output,root,bound);
        const uint64_t total_proof_nodes=oracle.node_count();
        std::cout<<"qcert_result format=qcert-1 target="<<target_arg<<" bound="<<bound
                 <<" root_budget="<<root_budget<<" nodes="<<builder.size()<<" target_nodes="<<target_nodes
                 <<" edges="<<edges<<" budget_mode="<<budget_mode<<" initial_proof_nodes="<<root_proof_nodes
                 <<" extraction_nodes="<<(total_proof_nodes-root_proof_nodes)<<" proof_nodes="<<total_proof_nodes
                 <<" stalemates_seen="<<oracle.stalemate_count()<<" cache_configs="<<engine.cache_size()
                 <<" output="<<std::quoted(output)<<"\n";
    }catch(const SearchTimeout&){std::cerr<<"error: certificate extraction timed out\n";return 3;}
    catch(const std::exception& error){std::cerr<<"error: "<<error.what()<<"\n";return 2;}
    return 0;
}
