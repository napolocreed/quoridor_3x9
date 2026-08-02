#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <optional>
#include <queue>
#include <stdexcept>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <map>

using Clock = std::chrono::steady_clock;

namespace qfrontier {

static inline uint64_t mix64(uint64_t x) {
    x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
    x ^= x >> 27; x *= 0x94d049bb133111ebULL;
    x ^= x >> 31; return x;
}
struct U64Hash { size_t operator()(uint64_t x) const noexcept { return size_t(mix64(x)); } };

enum Player : uint8_t { P1 = 0, P2 = 1 };
static inline Player other(Player p) { return p == P1 ? P2 : P1; }

struct State {
    uint32_t cfg = 0;
    uint8_t p[2]{};
    uint8_t walls[2]{};
    Player turn = P1;
};

struct TTEntry {
    uint64_t key = 0;
    uint16_t win_depth = 0xffff; // smallest depth proving target win
    uint16_t fail_depth = 0;     // largest depth failing to prove target win
    uint16_t best_move = 0xffff; // iterative-deepening/PV ordering hint
    uint8_t generation = 0;
    uint8_t pad = 0;
};
static_assert(sizeof(TTEntry) == 16);

class TransTable {
    std::vector<TTEntry> t_;
    size_t mask_ = 0;
    uint8_t generation_ = 1;
    inline std::pair<size_t,size_t> slots(uint64_t key) const {
        uint64_t h=mix64(key);
        size_t a=size_t(h)&mask_;
        size_t b=size_t(mix64(h^0x9e3779b97f4a7c15ULL))&mask_;
        if(a==b) b=(b+1)&mask_;
        return {a,b};
    }
    static int quality(const TTEntry& e,uint8_t gen) {
        if(e.key==0) return -1000000;
        int q=(e.generation==gen?10000:0)+int(e.fail_depth);
        if(e.win_depth!=0xffff) q+=2000-int(e.win_depth);
        if(e.best_move!=0xffff) q+=50;
        return q;
    }
public:
    explicit TransTable(unsigned pow2 = 24) {
        if (pow2 < 10 || pow2 > 30) throw std::runtime_error("tt bits must be 10..30");
        t_.resize(size_t(1) << pow2);
        mask_ = t_.size() - 1;
    }
    void new_generation() { if (++generation_ == 0) generation_ = 1; }
    size_t bytes() const { return t_.size() * sizeof(TTEntry); }
    bool probe(uint64_t key, int depth, bool &value, uint16_t &hint) const {
        auto [a,b]=slots(key); hint=0xffff;
        for(size_t i:{a,b}) {
            const TTEntry &e=t_[i];
            if(e.key!=key) continue;
            hint=e.best_move;
            if(e.win_depth != 0xffff && depth >= int(e.win_depth)) { value = true; return true; }
            if(depth <= int(e.fail_depth)) { value = false; return true; }
            return false;
        }
        return false;
    }
    void record(uint64_t key, int depth, bool value, uint16_t best_move) {
        auto [a,b]=slots(key);
        TTEntry *e=nullptr;
        if(t_[a].key==key) e=&t_[a];
        else if(t_[b].key==key) e=&t_[b];
        else e=quality(t_[a],generation_)<=quality(t_[b],generation_)?&t_[a]:&t_[b];
        if(e->key != key) {
            *e = TTEntry{};
            e->key = key;
        }
        e->generation = generation_;
        if(value) e->win_depth = uint16_t(std::min<int>(e->win_depth, depth));
        else e->fail_depth = uint16_t(std::max<int>(e->fail_depth, depth));
        if(best_move!=0xffff) e->best_move=best_move;
    }
};
class Engine {
public:
    int W, H, C, R, S, N;
    int walls_each;
    int max_total_walls;
    int order_mode = 1;
    uint64_t all_cell_mask;

    std::vector<uint64_t> cfg_masks;
    std::vector<uint8_t> cfg_placed;
    std::unordered_map<uint64_t, uint32_t, U64Hash> cfg_index;
    std::vector<uint8_t> clear_dirs; // [cfg*N + sq], bits UDLR
    std::vector<uint8_t> dist[2];    // [cfg*N + sq]
    static constexpr int LANDMARKS=4;
    std::vector<uint8_t> landmark_dist; // [cfg*N*LANDMARKS + sq*LANDMARKS + landmark]
    std::vector<uint64_t> reach[2];
    std::vector<uint32_t> trans_off;
    std::vector<uint32_t> trans;
    std::vector<uint32_t> mirror_cfg;
    std::vector<uint32_t> rotate_cfg;
    std::vector<uint8_t> mirror_sq, rotate_sq;
    std::vector<std::array<uint8_t,4>> neigh;
    std::vector<uint64_t> wall_conflict;

    Engine(int width, int height, int walls, int ordering = 1)
        : W(width), H(height), C(width-1), R(height-1), S(C*R), N(width*height),
          walls_each(walls), max_total_walls(std::min(2*walls, C*R*2)),
          all_cell_mask(N == 64 ? ~0ULL : ((1ULL << N) - 1ULL)) {
        order_mode = ordering;
        if (W < 2 || H < 2 || N > 64 || 2*S > 63) throw std::runtime_error("unsupported dimensions");
        init_geometry();
    }

    static std::string human_bytes(size_t x) {
        const char* u[] = {"B","KiB","MiB","GiB"}; int k=0; double v=x;
        while(v>=1024 && k<3){v/=1024;k++;}
        std::ostringstream o; o<<std::fixed<<std::setprecision(k?1:0)<<v<<u[k]; return o.str();
    }

    void precompute(bool keep_index = true) {
        auto t0=Clock::now();
        enumerate_configs();
        std::cerr << "configs=" << cfg_masks.size() << " enumerate="
                  << std::chrono::duration<double>(Clock::now()-t0).count() << "s\n";
        auto t1=Clock::now();
        build_index();
        std::cerr << "index=" << cfg_index.size() << " time="
                  << std::chrono::duration<double>(Clock::now()-t1).count() << "s\n";
        auto t2=Clock::now();
        build_board_tables();
        std::cerr << "board tables time=" << std::chrono::duration<double>(Clock::now()-t2).count() << "s\n";
        auto t3=Clock::now();
        build_symmetry();
        std::cerr << "symmetry time=" << std::chrono::duration<double>(Clock::now()-t3).count() << "s\n";
        auto t4=Clock::now();
        build_transitions();
        std::cerr << "transitions=" << trans.size() << " time="
                  << std::chrono::duration<double>(Clock::now()-t4).count() << "s\n";
        if (!keep_index) { cfg_index.clear(); cfg_index.rehash(0); }
        size_t bytes = cfg_masks.size()*8 + cfg_placed.size() + clear_dirs.size() +
            dist[0].size()+dist[1].size()+landmark_dist.size()+reach[0].size()*8+reach[1].size()*8+
            trans_off.size()*4+trans.size()*4+mirror_cfg.size()*4+rotate_cfg.size()*4;
        std::cerr << "dense_tables~" << human_bytes(bytes) << " total_precompute="
                  << std::chrono::duration<double>(Clock::now()-t0).count() << "s\n";
    }

    State initial() const {
        State s;
        s.cfg=0; // empty mask is first after sort
        s.p[0]=uint8_t((H-1)*W+W/2);
        s.p[1]=uint8_t(W/2);
        s.walls[0]=s.walls[1]=uint8_t(walls_each);
        s.turn=P1;
        return s;
    }

    inline int row(uint8_t p) const { return p/W; }
    inline int col(uint8_t p) const { return p%W; }
    inline uint8_t sq(int r,int c) const { return uint8_t(r*W+c); }
    inline int slot(int r,int c) const { return r*C+c; }
    inline bool terminal(const State& s, Player &winner) const {
        if (row(s.p[0])==0) { winner=P1; return true; }
        if (row(s.p[1])==H-1) { winner=P2; return true; }
        return false;
    }

    struct Child { State s; int score; uint16_t move; };

    int generate(const State& s, Player target, Child* out, bool ordered=true) const {
        Player win;
        if (terminal(s,win)) return 0;
        int nout=0;
        int me=int(s.turn), op=1-me;
        uint8_t mp=s.p[me], opp=s.p[op];
        uint8_t cd=clear_dirs[size_t(s.cfg)*N+mp];
        bool seen[64]{};
        static constexpr int opposite[4]={1,0,3,2};
        static constexpr int perpA[4]={2,2,0,0};
        static constexpr int perpB[4]={3,3,1,1};
        for(int d=0;d<4;d++) if(cd&(1u<<d)) {
            uint8_t q=neigh[mp][d];
            if(q==255) continue;
            if(q!=opp) {
                if(!seen[q]) { seen[q]=true; State t=s; t.p[me]=q; t.turn=other(s.turn); out[nout++]={t, static_eval(t,target),uint16_t(q)}; }
            } else {
                uint8_t od=clear_dirs[size_t(s.cfg)*N+opp];
                if(od&(1u<<d)) {
                    uint8_t z=neigh[opp][d];
                    if(z!=255 && !seen[z]) { seen[z]=true; State t=s; t.p[me]=z; t.turn=other(s.turn); out[nout++]={t, static_eval(t,target)+40,uint16_t(z)}; }
                } else {
                    for(int pd : {perpA[d],perpB[d]}) if(od&(1u<<pd)) {
                        uint8_t z=neigh[opp][pd];
                        if(z!=255 && !seen[z]) { seen[z]=true; State t=s; t.p[me]=z; t.turn=other(s.turn); out[nout++]={t, static_eval(t,target)+20,uint16_t(z)}; }
                    }
                }
            }
        }
        if(s.walls[me]>0) {
            uint32_t a=trans_off[s.cfg], b=trans_off[s.cfg+1];
            for(uint32_t i=a;i<b;i++) {
                uint32_t nc=trans[i];
                if(((reach[0][nc]>>s.p[0])&1ULL)==0 || ((reach[1][nc]>>s.p[1])&1ULL)==0) continue;
                State t=s; t.cfg=nc; --t.walls[me]; t.turn=other(s.turn);
                int sc=static_eval(t,target);
                // Reward walls that lengthen the opponent path and preserve own path.
                int before_op=dist[op][size_t(s.cfg)*N+s.p[op]], after_op=dist[op][size_t(nc)*N+s.p[op]];
                int before_me=dist[me][size_t(s.cfg)*N+s.p[me]], after_me=dist[me][size_t(nc)*N+s.p[me]];
                int tactical=(after_op-before_op)*80-(after_me-before_me)*55;
                if(me!=int(target)) tactical=-tactical;
                uint64_t added=cfg_masks[nc]^cfg_masks[s.cfg];
                uint16_t mv=uint16_t(0x100u+std::countr_zero(added));
                out[nout++]={t,sc+(order_mode==0?0:tactical),mv};
            }
        }
        if(ordered && nout>1) {
            // Move lists are short and this avoids the abstraction overhead of std::sort in the hot path.
            bool desc=(s.turn==target);
            for(int i=1;i<nout;i++) {
                Child x=out[i]; int j=i;
                while(j>0 && (desc ? out[j-1].score < x.score : out[j-1].score > x.score)) {
                    out[j]=out[j-1]; --j;
                }
                out[j]=x;
            }
        }
        return nout;
    }

    inline bool structurally_saturated(uint32_t cfg) const {
        return trans_off[cfg]==trans_off[cfg+1];
    }

    int static_eval(const State& s, Player target) const {
        Player win;
        if(terminal(s,win)) return win==target?1000000:-1000000;
        int t=int(target), o=1-t;
        int dt=dist[t][size_t(s.cfg)*N+s.p[t]];
        int do_=dist[o][size_t(s.cfg)*N+s.p[o]];
        if(order_mode==0) return (do_-dt) + int(s.walls[t])-int(s.walls[o]);
        int score=(do_-dt)*120 + (int(s.walls[t])-int(s.walls[o]))*7;
        int prog_t = t==0 ? (H-1-row(s.p[t])) : row(s.p[t]);
        int prog_o = o==0 ? (H-1-row(s.p[o])) : row(s.p[o]);
        score += (prog_t-prog_o)*3;
        if(dt==1) score += s.turn==target?700:300;
        if(do_==1) score -= s.turn==Player(o)?700:300;
        return score;
    }

    uint64_t canonical_key(const State& s, Player target) const {
        auto pack=[&](uint32_t cfg,uint8_t p0,uint8_t p1,uint8_t w0,uint8_t w1,Player turn,Player tar){
            uint64_t x=cfg;
            x=(x<<6)|p0; x=(x<<6)|p1; x=(x<<5)|w0; x=(x<<5)|w1; x=(x<<1)|uint64_t(turn); x=(x<<1)|uint64_t(tar);
            return x+1; // reserve zero for empty TT slots
        };
        uint64_t a=pack(s.cfg,s.p[0],s.p[1],s.walls[0],s.walls[1],s.turn,target);
        uint64_t b=pack(mirror_cfg[s.cfg],mirror_sq[s.p[0]],mirror_sq[s.p[1]],s.walls[0],s.walls[1],s.turn,target);
        uint64_t c=pack(rotate_cfg[s.cfg],rotate_sq[s.p[1]],rotate_sq[s.p[0]],s.walls[1],s.walls[0],other(s.turn),other(target));
        uint32_t rm=mirror_cfg[rotate_cfg[s.cfg]];
        uint8_t rp0=mirror_sq[rotate_sq[s.p[1]]], rp1=mirror_sq[rotate_sq[s.p[0]]];
        uint64_t d=pack(rm,rp0,rp1,s.walls[1],s.walls[0],other(s.turn),other(target));
        return std::min(std::min(a,b),std::min(c,d));
    }

private:
    void init_geometry() {
        neigh.resize(N);
        mirror_sq.resize(N); rotate_sq.resize(N);
        for(int r=0;r<H;r++)for(int c=0;c<W;c++){
            int p=r*W+c;
            neigh[p]={uint8_t(r>0?p-W:255),uint8_t(r+1<H?p+W:255),uint8_t(c>0?p-1:255),uint8_t(c+1<W?p+1:255)};
            mirror_sq[p]=sq(r,W-1-c);
            rotate_sq[p]=sq(H-1-r,W-1-c);
        }
        wall_conflict.assign(2*S,0);
        auto wi=[&](int ori,int r,int c){return ori*S+slot(r,c);};
        for(int r=0;r<R;r++)for(int c=0;c<C;c++){
            int h=wi(0,r,c), v=wi(1,r,c);
            wall_conflict[h]|=1ULL<<h; wall_conflict[v]|=1ULL<<v;
            wall_conflict[h]|=1ULL<<v; wall_conflict[v]|=1ULL<<h;
            if(c>0){int j=wi(0,r,c-1);wall_conflict[h]|=1ULL<<j;wall_conflict[j]|=1ULL<<h;}
            if(c+1<C){int j=wi(0,r,c+1);wall_conflict[h]|=1ULL<<j;wall_conflict[j]|=1ULL<<h;}
            if(r>0){int j=wi(1,r-1,c);wall_conflict[v]|=1ULL<<j;wall_conflict[j]|=1ULL<<v;}
            if(r+1<R){int j=wi(1,r+1,c);wall_conflict[v]|=1ULL<<j;wall_conflict[j]|=1ULL<<v;}
        }
    }

    void enumerate_configs() {
        struct RowState { uint32_t h=0,v=0; uint8_t count=0; };
        std::vector<RowState> rows;
        int total=1; for(int i=0;i<C;i++) total*=3;
        for(int x=0;x<total;x++){
            int y=x; RowState st; bool ok=true;
            std::vector<int> a(C);
            for(int c=0;c<C;c++){a[c]=y%3;y/=3; if(a[c])st.count++; if(a[c]==1)st.h|=1u<<c; else if(a[c]==2)st.v|=1u<<c;}
            for(int c=0;c+1<C;c++) if(a[c]==1&&a[c+1]==1) ok=false;
            if(ok) rows.push_back(st);
        }
        cfg_masks.clear(); cfg_placed.clear();
        std::function<void(int,uint32_t,uint64_t,uint64_t,int)> rec = [&](int r,uint32_t prev_v,uint64_t hm,uint64_t vm,int count){
            if(count>max_total_walls) return;
            if(r==R){ cfg_masks.push_back(hm|(vm<<S)); cfg_placed.push_back(uint8_t(count)); return; }
            for(auto &st:rows){
                if(prev_v & st.v) continue;
                rec(r+1,st.v,hm|(uint64_t(st.h)<<(r*C)),vm|(uint64_t(st.v)<<(r*C)),count+st.count);
            }
        };
        rec(0,0,0,0,0);
        std::vector<size_t> ord(cfg_masks.size()); std::iota(ord.begin(),ord.end(),0);
        std::sort(ord.begin(),ord.end(),[&](size_t a,size_t b){return cfg_masks[a]<cfg_masks[b];});
        std::vector<uint64_t> nm; std::vector<uint8_t> np; nm.reserve(ord.size());np.reserve(ord.size());
        for(size_t i:ord){nm.push_back(cfg_masks[i]);np.push_back(cfg_placed[i]);}
        cfg_masks.swap(nm); cfg_placed.swap(np);
        if(cfg_masks.empty()||cfg_masks[0]!=0) throw std::runtime_error("empty config missing");
    }

    void build_index() {
        cfg_index.clear(); cfg_index.reserve(size_t(cfg_masks.size()*1.35));
        for(uint32_t i=0;i<cfg_masks.size();i++) cfg_index.emplace(cfg_masks[i],i);
    }

    uint8_t compute_clear(uint64_t mask,int r,int c) const {
        uint64_t hm=mask&((1ULL<<S)-1), vm=mask>>S;
        uint8_t z=0;
        if(r>0){int br=r-1; bool b=(c<C&&((hm>>slot(br,c))&1))||(c>0&&((hm>>slot(br,c-1))&1)); if(!b)z|=1u<<0;}
        if(r+1<H){int br=r; bool b=(c<C&&((hm>>slot(br,c))&1))||(c>0&&((hm>>slot(br,c-1))&1)); if(!b)z|=1u<<1;}
        if(c>0){int bc=c-1; bool b=(r<R&&((vm>>slot(r,bc))&1))||(r>0&&((vm>>slot(r-1,bc))&1)); if(!b)z|=1u<<2;}
        if(c+1<W){int bc=c; bool b=(r<R&&((vm>>slot(r,bc))&1))||(r>0&&((vm>>slot(r-1,bc))&1)); if(!b)z|=1u<<3;}
        return z;
    }

    void build_board_tables() {
        size_t M=cfg_masks.size();
        clear_dirs.resize(M*N); dist[0].resize(M*N); dist[1].resize(M*N); reach[0].resize(M); reach[1].resize(M);
        landmark_dist.resize(M*N*LANDMARKS);
        std::array<uint8_t,64> q{};
        for(size_t ci=0;ci<M;ci++){
            uint64_t mask=cfg_masks[ci];
            for(int p=0;p<N;p++) clear_dirs[ci*N+p]=compute_clear(mask,p/W,p%W);
            for(int pl=0;pl<2;pl++){
                uint8_t* dd=dist[pl].data()+ci*N; std::fill(dd,dd+N,uint8_t(255));
                int head=0,tail=0; int gr=pl==0?0:H-1;
                for(int c=0;c<W;c++){uint8_t p=sq(gr,c);dd[p]=0;q[tail++]=p;}
                uint64_t rm=0;
                while(head<tail){uint8_t p=q[head++];rm|=1ULL<<p;uint8_t cd=clear_dirs[ci*N+p];for(int d=0;d<4;d++)if(cd&(1u<<d)){uint8_t z=neigh[p][d];if(z!=255&&dd[z]==255){dd[z]=uint8_t(dd[p]+1);q[tail++]=z;}}}
                reach[pl][ci]=rm;
            }
            const uint8_t landmarks[LANDMARKS]={sq(0,0),sq(0,W-1),sq(H-1,0),sq(H-1,W-1)};
            for(int li=0;li<LANDMARKS;li++){
                std::array<uint8_t,64> ld;ld.fill(255);int head=0,tail=0;uint8_t st=landmarks[li];ld[st]=0;q[tail++]=st;
                while(head<tail){uint8_t pp=q[head++];uint8_t cd=clear_dirs[ci*N+pp];for(int d=0;d<4;d++)if(cd&(1u<<d)){uint8_t z=neigh[pp][d];if(z!=255&&ld[z]==255){ld[z]=uint8_t(ld[pp]+1);q[tail++]=z;}}}
                for(int pp=0;pp<N;pp++)landmark_dist[(ci*N+pp)*LANDMARKS+li]=ld[pp];
            }
            if((ci&262143)==0 && ci) std::cerr<<"  board "<<ci<<"/"<<M<<"\r"<<std::flush;
        }
        std::cerr<<"\n";
    }

    uint64_t transform_mask(uint64_t m,bool mirror,bool rotate) const {
        uint64_t out=0;
        for(int ori=0;ori<2;ori++)for(int r=0;r<R;r++)for(int c=0;c<C;c++){
            int bit=ori*S+slot(r,c); if(!((m>>bit)&1ULL))continue;
            int rr=r,cc=c;
            if(rotate){rr=R-1-rr;cc=C-1-cc;}
            if(mirror)cc=C-1-cc;
            out|=1ULL<<(ori*S+slot(rr,cc));
        }
        return out;
    }
    void build_symmetry() {
        size_t M=cfg_masks.size();mirror_cfg.resize(M);rotate_cfg.resize(M);
        for(uint32_t i=0;i<M;i++){
            auto im=cfg_index.find(transform_mask(cfg_masks[i],true,false));
            auto ir=cfg_index.find(transform_mask(cfg_masks[i],false,true));
            if(im==cfg_index.end()||ir==cfg_index.end())throw std::runtime_error("symmetry config missing");
            mirror_cfg[i]=im->second;rotate_cfg[i]=ir->second;
        }
    }
    void build_transitions() {
        size_t M=cfg_masks.size();trans_off.resize(M+1);
        size_t expected=0;for(size_t i=0;i<M;i++)expected+=cfg_placed[i]; // same as number of reverse-removal edges if full closure
        trans.reserve(expected);
        for(uint32_t i=0;i<M;i++){
            trans_off[i]=uint32_t(trans.size());
            if(cfg_placed[i]>=max_total_walls) continue;
            uint64_t m=cfg_masks[i];
            for(int w=0;w<2*S;w++) if((m&wall_conflict[w])==0){
                uint64_t nm=m|(1ULL<<w); auto it=cfg_index.find(nm); if(it!=cfg_index.end())trans.push_back(it->second);
            }
            if((i&262143)==0 && i) std::cerr<<"  trans "<<i<<"/"<<M<<"\r"<<std::flush;
        }
        trans_off[M]=uint32_t(trans.size());std::cerr<<"\n";
    }
};

class ProofSolver {
    const Engine &e;
    TransTable tt;
    bool use_distance_bound = true;
    bool use_pawn_table = true;
    Clock::time_point deadline;
    bool timed_out=false;
    uint64_t nodes=0, tt_hits=0, cutoffs=0, pawn_table_hits=0;
    int max_children=192;
    struct PawnTable { std::vector<uint8_t> winner; std::vector<uint16_t> dtm; };
    std::unordered_map<uint32_t,PawnTable> pawn_tables;

    inline int pawn_index(uint8_t p0,uint8_t p1,Player turn) const {
        return (int(turn)*e.N+int(p0))*e.N+int(p1);
    }
    PawnTable build_pawn_table(uint32_t cfg) {
        const int SZ=2*e.N*e.N;
        std::vector<uint32_t> off(SZ+1); std::vector<uint16_t> edges;
        edges.reserve(size_t(SZ)*4);
        std::array<Engine::Child,192> ch{};
        for(int t=0;t<2;t++)for(int p0=0;p0<e.N;p0++)for(int p1=0;p1<e.N;p1++) {
            int id=(t*e.N+p0)*e.N+p1; off[id]=uint32_t(edges.size());
            if(p0==p1) continue;
            State st;st.cfg=cfg;st.p[0]=uint8_t(p0);st.p[1]=uint8_t(p1);st.walls[0]=st.walls[1]=0;st.turn=Player(t);
            Player win;if(e.terminal(st,win))continue;
            int n=e.generate(st,P1,ch.data(),false);
            for(int i=0;i<n;i++)edges.push_back(uint16_t(pawn_index(ch[i].s.p[0],ch[i].s.p[1],ch[i].s.turn)));
        }
        off[SZ]=uint32_t(edges.size());
        std::vector<uint32_t> pc(SZ,0);
        for(uint16_t c:edges)++pc[c];
        std::vector<uint32_t> po(SZ+1);for(int i=0;i<SZ;i++)po[i+1]=po[i]+pc[i];
        std::vector<uint16_t> parents(edges.size());std::vector<uint32_t> nx=po;
        for(int pidx=0;pidx<SZ;pidx++)for(uint32_t j=off[pidx];j<off[pidx+1];j++)parents[nx[edges[j]]++]=uint16_t(pidx);
        PawnTable tab;tab.winner.assign(SZ,255);tab.dtm.assign(SZ,0);
        std::vector<uint16_t> rem(SZ);std::vector<uint16_t> maxd(SZ,0);
        using Q=std::pair<uint16_t,uint16_t>;std::priority_queue<Q,std::vector<Q>,std::greater<Q>> q;
        for(int t=0;t<2;t++)for(int p0=0;p0<e.N;p0++)for(int p1=0;p1<e.N;p1++) {
            int id=(t*e.N+p0)*e.N+p1;if(p0==p1)continue;
            rem[id]=uint16_t(off[id+1]-off[id]);
            State st;st.cfg=cfg;st.p[0]=uint8_t(p0);st.p[1]=uint8_t(p1);st.turn=Player(t);
            Player win;if(e.terminal(st,win)){tab.winner[id]=uint8_t(win);q.push({0,uint16_t(id)});}
        }
        while(!q.empty()) {
            auto [d,c]=q.top();q.pop();if(tab.dtm[c]!=d)continue;
            Player w=Player(tab.winner[c]);
            for(uint32_t k=po[c];k<po[c+1];k++) {
                int par=parents[k];if(tab.winner[par]!=255)continue;
                Player mover=Player(par/(e.N*e.N));
                if(mover==w) {
                    tab.winner[par]=uint8_t(w);tab.dtm[par]=uint16_t(d+1);q.push({tab.dtm[par],uint16_t(par)});
                } else {
                    if(d>maxd[par])maxd[par]=d;
                    if(rem[par]>0)--rem[par];
                    if(rem[par]==0) {tab.winner[par]=uint8_t(w);tab.dtm[par]=uint16_t(maxd[par]+1);q.push({tab.dtm[par],uint16_t(par)});}
                }
            }
        }
        return tab;
    }
    std::optional<std::pair<Player,int>> pawn_only_result(const State& s) {
        if(!(e.structurally_saturated(s.cfg)||(s.walls[0]==0&&s.walls[1]==0)))return std::nullopt;
        auto it=pawn_tables.find(s.cfg);
        if(it==pawn_tables.end())it=pawn_tables.emplace(s.cfg,build_pawn_table(s.cfg)).first;
        int id=pawn_index(s.p[0],s.p[1],s.turn);uint8_t w=it->second.winner[id];
        ++pawn_table_hits;
        if(w==255)return std::make_pair(P1,-1); // -1 encodes a draw
        return std::make_pair(Player(w),int(it->second.dtm[id]));
    }
public:
    struct Result { bool solved=false; Player winner=P1; int depth=-1; uint64_t nodes=0,tt_hits=0,cutoffs=0,pawn_table_hits=0; double seconds=0; bool timeout=false; };
    ProofSolver(const Engine& eng,unsigned tt_bits,bool bounds=true,bool pawn_table=true):
        e(eng),tt(tt_bits),use_distance_bound(bounds),use_pawn_table(pawn_table) {
        std::cerr<<"TT="<<Engine::human_bytes(tt.bytes())
                 <<" bounds="<<use_distance_bound<<" pawn_table="<<use_pawn_table<<"\n";
    }
    static inline int target_relevant_depth(Player turn, Player target, int depth) {
        if(depth<=0 || ((turn==target)==((depth&1)!=0))) return depth;
        return depth-1;
    }
    bool prove(const State& s,Player target,int depth,
               std::vector<std::array<Engine::Child,192>>& move_lists,int ply) {
        ++nodes;
        if((nodes&16383ULL)==0 && Clock::now()>=deadline){timed_out=true;throw 1;}
        Player win;
        if(e.terminal(s,win)) return win==target;
        // A target can only finish on its own move. Canonicalising the remaining depth parity
        // at every node sharply increases TT reuse and removes searches that cannot add a proof.
        depth=target_relevant_depth(s.turn,target,depth);
        if(depth<=0) return false;
        if(use_distance_bound) {
            // False-only reachability pruning. Disabling it provides a slower audit mode.
            int ti=int(target), oi=1-ti;
            int graph_d=e.dist[ti][size_t(s.cfg)*e.N+s.p[ti]];
            int contact_lb=std::abs(e.row(s.p[ti])-e.row(s.p[oi]))+std::abs(e.col(s.p[ti])-e.col(s.p[oi]));
            size_t lb0=(size_t(s.cfg)*e.N+s.p[ti])*Engine::LANDMARKS;
            size_t lb1=(size_t(s.cfg)*e.N+s.p[oi])*Engine::LANDMARKS;
            bool separated=false;
            for(int li=0;li<Engine::LANDMARKS;li++){
                int a=e.landmark_dist[lb0+li],b=e.landmark_dist[lb1+li];
                if((a==255)!=(b==255))separated=true;
                else if(a!=255)contact_lb=std::max(contact_lb,std::abs(a-b));
            }
            int min_target_moves;
            if(separated) min_target_moves=graph_d;
            else {
                if(s.turn!=target && contact_lb>1)--contact_lb;
                int pre_jump=std::max(1,contact_lb)/2;
                int jump_plan=std::max(pre_jump+1,(graph_d+pre_jump+1)/2);
                min_target_moves=std::min(graph_d,jump_plan);
            }
            int target_turns=(s.turn==target)?(depth+1)/2:depth/2;
            if(min_target_moves>target_turns)return false;
        }
        uint64_t key=e.canonical_key(s,target);
        bool cached; uint16_t hint=0xffff;
        if(tt.probe(key,depth,cached,hint)){++tt_hits;return cached;}
        if(use_pawn_table) if(auto po=pawn_only_result(s)) {
            bool exact=(po->second<0)?false:(po->first==target && po->second<=depth);
            tt.record(key,depth,exact,0xffff);
            return exact;
        }
        auto &ch=move_lists[ply];
        int n=e.generate(s,target,ch.data(),true);
        if(n==0){tt.record(key,depth,false,0xffff);return false;}
        if(hint!=0xffff) {
            for(int i=0;i<n;i++) if(ch[i].move==hint) { if(i) std::swap(ch[0],ch[i]); break; }
        }
        bool result; uint16_t best=0xffff; uint64_t hardest=0;
        if(s.turn==target){
            result=false;
            for(int i=0;i<n;i++) {
                uint64_t before=nodes;
                if(prove(ch[i].s,target,depth-1,move_lists,ply+1)){result=true;best=ch[i].move;++cutoffs;break;}
                uint64_t cost=nodes-before; if(cost>hardest){hardest=cost;best=ch[i].move;}
            }
        } else {
            result=true;
            for(int i=0;i<n;i++) {
                uint64_t before=nodes;
                if(!prove(ch[i].s,target,depth-1,move_lists,ply+1)){result=false;best=ch[i].move;++cutoffs;break;}
                uint64_t cost=nodes-before; if(cost>hardest){hardest=cost;best=ch[i].move;}
            }
        }
        tt.record(key,depth,result,best);
        return result;
    }
    Result solve_from(State root,double seconds,int max_depth,int start_depth=1,int target_filter=-1) {
        Result out;auto t0=Clock::now();deadline=t0+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
        tt.new_generation();
        std::vector<std::array<Engine::Child,192>> move_lists(size_t(max_depth)+2);
        int last_checked[2]={0,0};
        for(int d=start_depth;d<=max_depth;d++){
            for(Player target:{P1,P2}){
                if(target_filter>=0 && int(target)!=target_filter) continue;
                int rd=target_relevant_depth(root.turn,target,d);
                if(rd<=0 || rd<=last_checked[int(target)]) continue;
                last_checked[int(target)]=rd;
                uint64_t before=nodes;
                bool ok=false;
                try{ok=prove(root,target,rd,move_lists,0);}catch(int){out.timeout=true;goto done;}
                std::cerr<<"depth="<<rd<<" target="<<(target==P1?1:2)<<" proven="<<ok
                         <<" nodes="<<(nodes-before)<<" total="<<nodes<<" elapsed="
                         <<std::chrono::duration<double>(Clock::now()-t0).count()<<"s tt_hits="<<tt_hits<<"\n";
                if(ok){out.solved=true;out.winner=target;out.depth=rd;goto done;}
                if(Clock::now()>=deadline){out.timeout=true;goto done;}
            }
        }
    done:
        out.nodes=nodes;out.tt_hits=tt_hits;out.cutoffs=cutoffs;out.pawn_table_hits=pawn_table_hits;out.seconds=std::chrono::duration<double>(Clock::now()-t0).count();
        return out;
    }
    Result solve(double seconds,int max_depth,int start_depth=1,int target_filter=-1) {
        return solve_from(e.initial(),seconds,max_depth,start_depth,target_filter);
    }
};

} // namespace

int main(int argc,char**argv){
    using namespace qfrontier;
    int W=3,H=9,walls=8,max_depth=80,start_depth=1,tt_bits=24,order_mode=1,target_filter=-1,root_index=-1,root_index2=-1,jobs=3,child_depth=-1;double seconds=60;bool precompute_only=false,list_root=false,list_second=false,parallel_second=false,use_bounds=true,use_pawn_table=true;
    for(int i=1;i<argc;i++){
        std::string a=argv[i];auto val=[&](auto&x){if(i+1>=argc)throw std::runtime_error("missing arg");std::stringstream ss(argv[++i]);ss>>x;};
        if(a=="--width")val(W);else if(a=="--height")val(H);else if(a=="--walls")val(walls);else if(a=="--max-depth")val(max_depth);
        else if(a=="--start-depth")val(start_depth);else if(a=="--target")val(target_filter);
        else if(a=="--root-index")val(root_index);else if(a=="--root-index2")val(root_index2);else if(a=="--list-root")list_root=true;else if(a=="--list-second")list_second=true;else if(a=="--parallel-second")parallel_second=true;else if(a=="--jobs")val(jobs);else if(a=="--child-depth")val(child_depth);
        else if(a=="--seconds")val(seconds);else if(a=="--tt-bits")val(tt_bits);else if(a=="--order")val(order_mode);else if(a=="--precompute-only")precompute_only=true;else if(a=="--no-bounds")use_bounds=false;else if(a=="--no-pawn-table")use_pawn_table=false;
        else if(a=="--help"){std::cout<<"frontier_solver --width 3 --height 9 --walls 8 --seconds 600 --max-depth 120 --tt-bits 25 [--no-bounds] [--no-pawn-table]\n";return 0;}
    }
    try{
        Engine e(W,H,walls,order_mode);e.precompute(false);
        if(precompute_only)return 0;
        if(target_filter==1)target_filter=0; else if(target_filter==2)target_filter=1; else target_filter=-1;
        State root=e.initial();
        auto label=[&](uint16_t mv){
            std::ostringstream o;
            if(mv<0x100){int q=mv;o<<"P("<<(q/e.W)<<","<<(q%e.W)<<")";}
            else {int bit=mv-0x100,ori=bit/e.S,z=bit%e.S;o<<(ori?"V":"H")<<"("<<(z/e.C)<<","<<(z%e.C)<<")";}
            return o.str();
        };
        auto choose_child=[&](State st,int index,bool list,const char* prefix)->std::optional<State>{
            std::array<Engine::Child,192> ch{};Player tar=target_filter==1?P2:P1;
            int n=e.generate(st,tar,ch.data(),true);
            for(int i=0;i<n;i++)std::cerr<<prefix<<"["<<i<<"] move="<<label(ch[i].move)<<" score="<<ch[i].score<<"\n";
            if(list)return std::nullopt;
            if(index<0||index>=n)throw std::runtime_error("bad forced index");
            std::cerr<<"forcing "<<prefix<<"["<<index<<"] move="<<label(ch[index].move)<<"\n";
            return ch[index].s;
        };
        if(list_root){choose_child(root,-1,true,"root");return 0;}
        if(root_index>=0){root=*choose_child(root,root_index,false,"root");}
        if(list_second){choose_child(root,-1,true,"second");return 0;}
        if(root_index2>=0){if(root_index<0)throw std::runtime_error("root-index2 requires root-index");root=*choose_child(root,root_index2,false,"second");}
        if(parallel_second) {
            if(root_index<0)throw std::runtime_error("parallel-second requires root-index");
            if(child_depth<1)child_depth=max_depth-2;
            std::array<Engine::Child,192> raw{};Player target=target_filter==1?P2:P1;
            int nr=e.generate(root,target,raw.data(),true);
            struct Task{int rep;State st;uint64_t key;std::vector<int> aliases;};
            std::vector<Task> tasks;std::unordered_map<uint64_t,int,U64Hash> bykey;
            for(int i=0;i<nr;i++){
                uint64_t k=e.canonical_key(raw[i].s,target);
                auto it=bykey.find(k);
                if(it==bykey.end()){int z=tasks.size();bykey[k]=z;tasks.push_back({i,raw[i].s,k,{i}});}
                else tasks[it->second].aliases.push_back(i);
            }
            std::cerr<<"parallel children raw="<<nr<<" unique="<<tasks.size()<<" jobs="<<jobs<<" depth="<<child_depth<<" warm="<<std::max(1,child_depth-2)<<"\n";
            struct Wire{uint64_t nodes,tt_hits,cutoffs,pawn;double secs;int solved,winner,depth,timeout;};
            struct Active{pid_t pid;int fd;int task;};std::vector<Active> active;
            int next=0,done=0;bool any_false=false,any_timeout=false;
            auto launch=[&](int ti){
                int fds[2];if(pipe(fds))throw std::runtime_error("pipe failed");pid_t pid=fork();if(pid<0)throw std::runtime_error("fork failed");
                if(pid==0){close(fds[0]);ProofSolver ps(e,tt_bits,use_bounds,use_pawn_table);auto r=ps.solve_from(tasks[ti].st,seconds,child_depth,std::max(1,child_depth-2),int(target));
                    Wire w{r.nodes,r.tt_hits,r.cutoffs,r.pawn_table_hits,r.seconds,int(r.solved),int(r.winner),r.depth,int(r.timeout)};(void)!write(fds[1],&w,sizeof(w));close(fds[1]);_exit(0);}
                close(fds[1]);active.push_back({pid,fds[0],ti});
            };
            while(done<int(tasks.size())){
                while(next<int(tasks.size())&&int(active.size())<std::max(1,jobs))launch(next++);
                int status=0;pid_t p=waitpid(-1,&status,0);if(p<0)throw std::runtime_error("waitpid failed");
                auto it=std::find_if(active.begin(),active.end(),[&](auto&a){return a.pid==p;});if(it==active.end())throw std::runtime_error("unknown child");
                Wire w{};ssize_t got=read(it->fd,&w,sizeof(w));close(it->fd);int ti=it->task;active.erase(it);++done;
                bool ok=got==sizeof(w)&&WIFEXITED(status)&&WEXITSTATUS(status)==0;
                std::cout<<"child_rep="<<tasks[ti].rep<<" aliases=";for(size_t j=0;j<tasks[ti].aliases.size();j++){if(j)std::cout<<",";std::cout<<tasks[ti].aliases[j];}
                std::cout<<" ok="<<ok<<" proven="<<(ok?w.solved:0)<<" timeout="<<(ok?w.timeout:1)<<" nodes="<<(ok?w.nodes:0)<<" seconds="<<(ok?w.secs:0)<<"\n"<<std::flush;
                if(!ok||w.timeout)any_timeout=true;else if(!w.solved)any_false=true;
            }
            std::cout<<"parallel_result proven="<<(!any_false&&!any_timeout)<<" disproven="<<any_false<<" unresolved="<<any_timeout<<" total_depth="<<(child_depth+2)<<"\n";
            return (!any_false&&!any_timeout)?0:(any_false?1:3);
        }
        ProofSolver ps(e,tt_bits,use_bounds,use_pawn_table);auto r=ps.solve_from(root,seconds,max_depth,start_depth,target_filter);
        std::cout<<"width="<<W<<" height="<<H<<" walls="<<walls<<" solved="<<r.solved;
        if(r.solved)std::cout<<" winner="<<(r.winner==P1?1:2)<<" depth="<<r.depth;
        std::cout<<" nodes="<<r.nodes<<" tt_hits="<<r.tt_hits<<" cutoffs="<<r.cutoffs<<" pawn_table_hits="<<r.pawn_table_hits<<" seconds="<<r.seconds<<" timeout="<<r.timeout<<"\n";
    }catch(const std::exception&ex){std::cerr<<"error: "<<ex.what()<<"\n";return 2;}
}
