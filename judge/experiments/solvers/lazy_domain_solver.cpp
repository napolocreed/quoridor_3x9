#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;

namespace qdomain {

static inline uint64_t mix64(uint64_t x) {
    x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
    x ^= x >> 27; x *= 0x94d049bb133111ebULL;
    x ^= x >> 31; return x;
}
struct U64Hash { size_t operator()(uint64_t x) const noexcept { return size_t(mix64(x)); } };


class FlatMaskIndex {
    std::vector<uint64_t> keys_; // mask + 1; zero means empty
    std::vector<uint32_t> vals_;
    size_t mask_ = 0;
    size_t size_ = 0;

    void rehash(size_t cap) {
        size_t n=1; while(n<cap)n<<=1;
        std::vector<uint64_t> oldk=std::move(keys_);
        std::vector<uint32_t> oldv=std::move(vals_);
        keys_.assign(n,0); vals_.resize(n); mask_=n-1; size_=0;
        for(size_t i=0;i<oldk.size();++i) if(oldk[i]) insert_raw(oldk[i]-1,oldv[i]);
    }
    void insert_raw(uint64_t key,uint32_t value) {
        size_t i=size_t(mix64(key))&mask_; while(keys_[i])i=(i+1)&mask_;
        keys_[i]=key+1; vals_[i]=value; ++size_;
    }
public:
    explicit FlatMaskIndex(size_t reserve=1024){rehash(std::max<size_t>(16,reserve*2));}
    uint32_t find(uint64_t key) const {
        size_t i=size_t(mix64(key))&mask_; uint64_t stored=key+1;
        while(true){uint64_t k=keys_[i];if(!k)return UINT32_MAX;if(k==stored)return vals_[i];i=(i+1)&mask_;}
    }
    void insert(uint64_t key,uint32_t value){if((size_+1)*10>keys_.size()*7)rehash(keys_.size()*2);insert_raw(key,value);}
    size_t bytes()const{return keys_.capacity()*sizeof(uint64_t)+vals_.capacity()*sizeof(uint32_t);}
};

enum Player : uint8_t { P1 = 0, P2 = 1 };
static inline Player other(Player p) { return p == P1 ? P2 : P1; }

struct State {
    uint64_t walls_mask = 0;
    uint32_t cfg_id = 0;
    uint8_t p[2]{};
    uint8_t walls[2]{};
    Player turn = P1;
};

class TransTable {
    std::vector<uint64_t> keys_;
    std::vector<uint32_t> meta_;
    size_t mask_ = 0;
    size_t bucket_mask_ = 0;
    int ways_ = 2;
    static constexpr uint8_t WIN_NONE = 0xff;
    static constexpr uint16_t MOVE_NONE = 0x1ff;
    static uint32_t pack_meta(uint8_t win_depth,uint8_t fail_depth,uint16_t best_move) {
        return uint32_t(win_depth) | (uint32_t(fail_depth)<<8) | (uint32_t(best_move&0x1ff)<<16);
    }
    static uint8_t win_depth(uint32_t m) { return uint8_t(m); }
    static uint8_t fail_depth(uint32_t m) { return uint8_t(m>>8); }
    static uint16_t best_move(uint32_t m) { return uint16_t((m>>16)&0x1ff); }
    inline std::pair<size_t,size_t> slots(uint64_t key) const {
        uint64_t h=mix64(key);
        size_t a=size_t(h)&mask_;
        size_t b=size_t(mix64(h^0x9e3779b97f4a7c15ULL))&mask_;
        if(a==b) b=(b+1)&mask_;
        return {a,b};
    }
    int quality(size_t i) const {
        if(keys_[i]==0) return -1000000;
        uint32_t m=meta_[i];
        int q=int(fail_depth(m));
        uint8_t w=win_depth(m);
        if(w!=WIN_NONE) q+=2000-int(w);
        if(best_move(m)!=MOVE_NONE) q+=50;
        return q;
    }
public:
    explicit TransTable(unsigned pow2 = 24,int ways=2) {
        if(pow2<10 || pow2>30) throw std::runtime_error("tt bits must be 10..30");
        if(ways!=2&&ways!=4) throw std::runtime_error("tt ways must be 2 or 4");
        ways_=ways;size_t n=size_t(1)<<pow2;
        keys_.assign(n,0);meta_.assign(n,pack_meta(WIN_NONE,0,MOVE_NONE));mask_=n-1;
        if(ways_==4)bucket_mask_=(n/4)-1;
    }
    size_t bytes() const { return keys_.size()*sizeof(uint64_t)+meta_.size()*sizeof(uint32_t); }
    bool probe(uint64_t key,int depth,bool& value,uint16_t& hint) const {
        hint=0xffff;
        if(ways_==2){
            auto [a,b]=slots(key);
            for(size_t i:{a,b}){if(keys_[i]!=key)continue;uint32_t m=meta_[i];uint16_t bm=best_move(m);hint=(bm==MOVE_NONE?0xffff:bm);uint8_t wd=win_depth(m),fd=fail_depth(m);if(wd!=WIN_NONE&&depth>=int(wd)){value=true;return true;}if(depth<=int(fd)){value=false;return true;}return false;}
            return false;
        }
        size_t base=(size_t(mix64(key))&bucket_mask_)*4;
        for(size_t i=base;i<base+4;i++){if(keys_[i]!=key)continue;uint32_t m=meta_[i];uint16_t bm=best_move(m);hint=(bm==MOVE_NONE?0xffff:bm);uint8_t wd=win_depth(m),fd=fail_depth(m);if(wd!=WIN_NONE&&depth>=int(wd)){value=true;return true;}if(depth<=int(fd)){value=false;return true;}return false;}
        return false;
    }

    void record(uint64_t key,int depth,bool value,uint16_t move) {
        if(depth<0||depth>=255)throw std::runtime_error("TT depth exceeds packed range");
        size_t i=0;
        if(ways_==2){auto [a,b]=slots(key);if(keys_[a]==key)i=a;else if(keys_[b]==key)i=b;else i=quality(a)<=quality(b)?a:b;}
        else{size_t base=(size_t(mix64(key))&bucket_mask_)*4;i=base;for(size_t j=base;j<base+4;j++){if(keys_[j]==key){i=j;break;}if(quality(j)<quality(i))i=j;}}
        uint8_t wd=WIN_NONE,fd=0;uint16_t bm=MOVE_NONE;
        if(keys_[i]==key){uint32_t old=meta_[i];wd=win_depth(old);fd=fail_depth(old);bm=best_move(old);}else keys_[i]=key;
        if(value)wd=uint8_t(std::min<int>(wd,depth));else fd=uint8_t(std::max<int>(fd,depth));
        if(wd!=WIN_NONE&&fd>=wd)throw std::runtime_error("inconsistent transposition bounds");
        if(move!=0xffff){if(move>0x1fe)throw std::runtime_error("move id exceeds packed TT range");bm=move;}
        meta_[i]=pack_meta(wd,fd,bm);
    }

};

class DominanceTable {
    static constexpr uint8_t WIN_NONE=0xff;
    struct Entry {
        uint64_t key=0;
        std::array<uint8_t,11> win{};
        std::array<uint8_t,11> fail{};
    };
    std::vector<Entry> entries_;
    size_t mask_=0;
public:
    explicit DominanceTable(unsigned bits=0){
        if(bits==0)return;
        if(bits<10||bits>27)throw std::runtime_error("dominance TT bits must be 10..27");
        entries_.resize(size_t(1)<<bits);mask_=entries_.size()-1;
        for(auto&e:entries_)e.win.fill(WIN_NONE);
    }
    bool enabled()const{return !entries_.empty();}
    size_t bytes()const{return entries_.size()*sizeof(Entry);}
    bool probe(uint64_t key,int own,int depth,bool&value)const{
        if(entries_.empty()) return false;
        const Entry&e=entries_[size_t(mix64(key))&mask_];
        if(e.key!=key) return false;
        if(e.win[own]!=WIN_NONE&&depth>=int(e.win[own])){value=true;return true;}
        if(depth<=int(e.fail[own])){value=false;return true;}
        return false;
    }
    void record(uint64_t key,int own,int depth,bool value){
        if(entries_.empty()) return;
        Entry&e=entries_[size_t(mix64(key))&mask_];
        if(e.key!=key){e.key=key;e.win.fill(WIN_NONE);e.fail.fill(0);}
        if(value){for(int a=own;a<=10;a++)e.win[a]=uint8_t(std::min<int>(e.win[a],depth));}
        else{for(int a=0;a<=own;a++)e.fail[a]=uint8_t(std::max<int>(e.fail[a],depth));}
    }
};

class LazyEngine {
public:
    int W,H,C,R,S,N;
    int walls_each,max_total_walls;
    int order_mode=1;
    int path_choice_weight=0;
    int symmetry_mode=2;
    uint64_t structural_mask=0;
    std::vector<std::array<uint8_t,4>> neigh;
    std::vector<uint8_t> mirror_sq,rotate_sq;
    std::vector<uint64_t> wall_conflict;
    std::array<std::array<uint32_t,4>,40> wall_block_{};

    struct ConfigData {
        std::array<uint8_t,32> dist0{};
        std::array<uint8_t,32> dist1{};
        std::array<uint32_t,4> dir{}; // source-square masks for U,D,L,R
        uint64_t legal_add=0;
        uint64_t canonical_wall=0;
        uint8_t canonical_xforms=1;
    };

private:
    FlatMaskIndex cache_index_;
    std::vector<ConfigData> cache_data_;
    std::vector<uint32_t> transition_offsets_;
    std::vector<uint16_t> transition_counts_;
    std::vector<uint16_t> transition_expansions_;
    std::vector<uint32_t> transition_entries_;
    int transition_threshold_=0;
    uint64_t transition_hits_=0,transition_builds_=0;
    std::array<std::array<uint64_t,1024>,4> mirror_lut_{};
    std::array<std::array<uint64_t,1024>,4> rotate_lut_{};
    std::array<std::array<uint64_t,1024>,4> mirror_rotate_lut_{};
    std::array<std::array<std::array<uint32_t,4>,1024>,4> block_lut_{};
    std::array<std::array<uint64_t,1024>,4> conflict_lut_{};
    std::array<uint32_t,4> base_dir_{};
    uint32_t board_mask_=0,top_goal_mask_=0,bottom_goal_mask_=0;
    bool profile_visits_=false;
    std::vector<uint64_t> node_visits_;
    uint64_t cache_hits_=0,cache_misses_=0;

public:
    LazyEngine(int width,int height,int walls,int ordering=1,int symmetry=2,size_t reserve_configs=65536,bool profile_visits=false,int transition_threshold=0,int choice_weight=0)
        :W(width),H(height),C(width-1),R(height-1),S(C*R),N(width*height),walls_each(walls),
         max_total_walls(std::min(2*walls,2*C*R)), cache_index_(reserve_configs) {
        order_mode=ordering;path_choice_weight=choice_weight;symmetry_mode=symmetry;profile_visits_=profile_visits;transition_threshold_=transition_threshold;
        if(W<2||H<2||N>32||2*S>39)throw std::runtime_error("lazy engine currently supports N <= 32 and 2*S <= 39");
        if(symmetry_mode<0||symmetry_mode>2)throw std::runtime_error("symmetry mode must be 0..2");
        structural_mask=(uint64_t(1)<<(2*S))-1;
        init_geometry();
        cache_data_.reserve(reserve_configs);transition_offsets_.reserve(reserve_configs);transition_counts_.reserve(reserve_configs);transition_expansions_.reserve(reserve_configs);if(profile_visits_)node_visits_.reserve(reserve_configs);
        if(ensure_config(0)!=0) throw std::runtime_error("empty config must receive id zero");
    }

    static std::string human_bytes(size_t x){const char*u[]={"B","KiB","MiB","GiB"};int k=0;double v=x;while(v>=1024&&k<3){v/=1024;k++;}std::ostringstream o;o<<std::fixed<<std::setprecision(k?1:0)<<v<<u[k];return o.str();}
    inline int row(uint8_t p)const{return p/W;}
    inline int col(uint8_t p)const{return p%W;}
    inline uint8_t sq(int r,int c)const{return uint8_t(r*W+c);}
    inline int slot(int r,int c)const{return r*C+c;}

    State initial()const{State s;s.cfg_id=0;s.p[0]=uint8_t((H-1)*W+W/2);s.p[1]=uint8_t(W/2);s.walls[0]=s.walls[1]=uint8_t(walls_each);return s;}
    inline bool terminal(const State&s,Player&w)const{if(row(s.p[0])==0){w=P1;return true;}if(row(s.p[1])==H-1){w=P2;return true;}return false;}

    size_t cache_size()const{return cache_data_.size();}
    uint64_t cache_hits()const{return cache_hits_;}
    uint64_t cache_misses()const{return cache_misses_;}
    size_t cache_payload_bytes()const{return cache_data_.capacity()*sizeof(ConfigData);}
    size_t cache_estimated_bytes()const{return cache_payload_bytes()+cache_index_.bytes()+node_visits_.capacity()*sizeof(uint64_t)+transition_offsets_.capacity()*sizeof(uint32_t)+transition_counts_.capacity()*sizeof(uint16_t)+transition_expansions_.capacity()*sizeof(uint16_t)+transition_entries_.capacity()*sizeof(uint32_t);}
    uint64_t transition_hits()const{return transition_hits_;}
    uint64_t transition_builds()const{return transition_builds_;}
    size_t transition_entries()const{return transition_entries_.size();}
    inline void record_node_visit(uint32_t id){if(profile_visits_)++node_visits_[id];}
    std::string visit_profile()const{
        if(!profile_visits_) return "";
        std::vector<uint64_t> v=node_visits_;
        std::sort(v.begin(),v.end(),std::greater<uint64_t>());
        uint64_t total=0;
        for(auto x:v) total+=x;
        auto cover=[&](double f){uint64_t want=uint64_t(double(total)*f);uint64_t acc=0;size_t n=0;while(n<v.size()&&acc<want)acc+=v[n++];return n;};
        size_t ge2=0,ge10=0,ge100=0,ge1000=0,ge10000=0;for(auto x:v){ge2+=x>=2;ge10+=x>=10;ge100+=x>=100;ge1000+=x>=1000;ge10000+=x>=10000;}
        std::ostringstream o;o<<"visit_total="<<total<<" visit_nonzero="<<std::count_if(v.begin(),v.end(),[](uint64_t x){return x>0;})<<" cover50="<<cover(.5)<<" cover90="<<cover(.9)<<" cover99="<<cover(.99)<<" ge2="<<ge2<<" ge10="<<ge10<<" ge100="<<ge100<<" ge1000="<<ge1000<<" ge10000="<<ge10000<<" top=";for(size_t i=0;i<std::min<size_t>(10,v.size());i++){if(i)o<<",";o<<v[i];}return o.str();
    }

    uint32_t ensure_config(uint64_t mask) {
        uint32_t found=cache_index_.find(mask);
        if(found!=UINT32_MAX){++cache_hits_;return found;}
        ++cache_misses_;
        uint32_t idx=uint32_t(cache_data_.size());
        cache_data_.push_back(build_config(mask));
        transition_offsets_.push_back(UINT32_MAX);transition_counts_.push_back(0);transition_expansions_.push_back(0);
        if(profile_visits_)node_visits_.push_back(0);
        cache_index_.insert(mask,idx);
        return idx;
    }
    uint32_t ensure_child_config(uint64_t mask,uint32_t parent_id,int wall) {
        uint32_t found=cache_index_.find(mask);
        if(found!=UINT32_MAX){++cache_hits_;return found;}
        ++cache_misses_;
        const ConfigData parent=cache_data_[parent_id];
        ConfigData child;
        for(int d=0;d<4;d++) child.dir[d]=parent.dir[d]&~wall_block_[wall][d];
        bfs_goal(child.dir,top_goal_mask_,child.dist0);
        bfs_goal(child.dir,bottom_goal_mask_,child.dist1);
        if(std::popcount(mask)<max_total_walls) child.legal_add=parent.legal_add&~wall_conflict[wall];
        set_canonical_wall(child,mask);
        uint32_t idx=uint32_t(cache_data_.size());
        cache_data_.push_back(child);
        transition_offsets_.push_back(UINT32_MAX);transition_counts_.push_back(0);transition_expansions_.push_back(0);
        if(profile_visits_) node_visits_.push_back(0);
        cache_index_.insert(mask,idx);
        return idx;
    }
    void build_transition_cache(const State&s,uint64_t adds){
        std::vector<uint32_t> local;
        local.reserve(std::popcount(adds));
        uint64_t todo=adds;
        while(todo){int w=std::countr_zero(todo);todo&=todo-1;uint64_t nm=s.walls_mask|(1ULL<<w);uint32_t id=ensure_child_config(nm,s.cfg_id,w);if(id>=(1u<<26))throw std::runtime_error("transition child id exceeds packed range");local.push_back((id<<6)|uint32_t(w));}
        if(transition_entries_.size()+local.size()>UINT32_MAX)throw std::runtime_error("transition cache offset overflow");
        transition_offsets_[s.cfg_id]=uint32_t(transition_entries_.size());
        transition_counts_[s.cfg_id]=uint16_t(local.size());
        transition_entries_.insert(transition_entries_.end(),local.begin(),local.end());
        ++transition_builds_;
    }
    const ConfigData& config_by_id(uint32_t id) const { return cache_data_[id]; }

    struct Child{State s;int score;uint16_t move;};

    int shortest_options(const State&s,int player,const ConfigData&cd)const{
        uint8_t p=s.p[player];int d=player==0?cd.dist0[p]:cd.dist1[p];if(d<=0||d>=255)return 0;int n=0;
        for(int dir=0;dir<4;dir++)if((cd.dir[dir]>>p)&1u){uint8_t q=neigh[p][dir];if(q==255)continue;int dq=player==0?cd.dist0[q]:cd.dist1[q];n+=dq+1==d;}
        return n;
    }

    int static_eval_data(const State&s,Player target,const ConfigData&cd) const {
        Player win;if(terminal(s,win))return win==target?1000000:-1000000;
        int t=int(target),o=1-t;
        int dt=(t==0?cd.dist0[s.p[t]]:cd.dist1[s.p[t]]);
        int do_=(o==0?cd.dist0[s.p[o]]:cd.dist1[s.p[o]]);
        if(order_mode==0)return(do_-dt)+int(s.walls[t])-int(s.walls[o]);
        int score=(do_-dt)*120+(int(s.walls[t])-int(s.walls[o]))*7;
        if(path_choice_weight)score+=(shortest_options(s,t,cd)-shortest_options(s,o,cd))*path_choice_weight;
        int prog_t=t==0?(H-1-row(s.p[t])):row(s.p[t]);
        int prog_o=o==0?(H-1-row(s.p[o])):row(s.p[o]);
        score+=(prog_t-prog_o)*3;
        if(dt==1)score+=s.turn==target?700:300;
        if(do_==1)score-=s.turn==Player(o)?700:300;
        return score;
    }
    int static_eval(const State&s,Player target)const{return static_eval_data(s,target,config_by_id(s.cfg_id));}

    int generate(const State&s,Player target,Child*out,bool ordered=true){
        Player win;if(terminal(s,win))return 0;
        int nout=0,me=int(s.turn),op=1-me;
        uint8_t mp=s.p[me],opp=s.p[op];
        const ConfigData& current=config_by_id(s.cfg_id);
        auto clear_at=[&](uint8_t p){return uint8_t(((current.dir[0]>>p)&1u)|(((current.dir[1]>>p)&1u)<<1)|(((current.dir[2]>>p)&1u)<<2)|(((current.dir[3]>>p)&1u)<<3));};
        uint8_t cd=clear_at(mp);
        bool seen[64]{};static constexpr int perpA[4]={2,2,0,0};static constexpr int perpB[4]={3,3,1,1};
        for(int d=0;d<4;d++)if(cd&(1u<<d)){
            uint8_t q=neigh[mp][d];if(q==255)continue;
            if(q!=opp){if(!seen[q]){seen[q]=true;State t=s;t.p[me]=q;t.turn=other(s.turn);out[nout++]={t,static_eval_data(t,target,current),uint16_t(q)};}}
            else{
                uint8_t od=clear_at(opp);
                if(od&(1u<<d)){uint8_t z=neigh[opp][d];if(z!=255&&!seen[z]){seen[z]=true;State t=s;t.p[me]=z;t.turn=other(s.turn);out[nout++]={t,static_eval_data(t,target,current)+40,uint16_t(z)};}}
                else for(int pd:{perpA[d],perpB[d]})if(od&(1u<<pd)){uint8_t z=neigh[opp][pd];if(z!=255&&!seen[z]){seen[z]=true;State t=s;t.p[me]=z;t.turn=other(s.turn);out[nout++]={t,static_eval_data(t,target,current)+20,uint16_t(z)};}}
            }
        }
        if(s.walls[me]>0){
            uint64_t adds=current.legal_add;
            int before_op=(op==0?current.dist0[s.p[op]]:current.dist1[s.p[op]]);
            int before_me=(me==0?current.dist0[s.p[me]]:current.dist1[s.p[me]]);
            auto emit_wall=[&](int w,uint32_t nid){
                const auto&nx=config_by_id(nid);
                if(nx.dist0[s.p[0]]==255||nx.dist1[s.p[1]]==255)return;
                State t=s;t.walls_mask=s.walls_mask|(1ULL<<w);t.cfg_id=nid;--t.walls[me];t.turn=other(s.turn);
                int sc=static_eval_data(t,target,nx);
                int after_op=(op==0?nx.dist0[s.p[op]]:nx.dist1[s.p[op]]);
                int after_me=(me==0?nx.dist0[s.p[me]]:nx.dist1[s.p[me]]);
                int tactical=(after_op-before_op)*80-(after_me-before_me)*55;
                if(me!=int(target))tactical=-tactical;
                out[nout++]={t,sc+(order_mode==0?0:tactical),uint16_t(0x100u+w)};
            };
            bool cached=transition_offsets_[s.cfg_id]!=UINT32_MAX;
            if(!cached&&transition_threshold_>0){uint16_t&exp=transition_expansions_[s.cfg_id];if(exp!=UINT16_MAX)++exp;if(exp>=transition_threshold_){build_transition_cache(s,adds);cached=true;}}
            if(cached){++transition_hits_;uint32_t off=transition_offsets_[s.cfg_id];uint16_t cnt=transition_counts_[s.cfg_id];for(uint16_t i=0;i<cnt;i++){uint32_t packed=transition_entries_[off+i];emit_wall(int(packed&63u),packed>>6);}}
            else while(adds){int w=std::countr_zero(adds);adds&=adds-1;uint64_t nm=s.walls_mask|(1ULL<<w);uint32_t nid=ensure_child_config(nm,s.cfg_id,w);emit_wall(w,nid);}
        }
        if(ordered&&nout>1){bool desc=s.turn==target;for(int i=1;i<nout;i++){Child x=out[i];int j=i;while(j>0&&(desc?out[j-1].score<x.score:out[j-1].score>x.score)){out[j]=out[j-1];--j;}out[j]=x;}}
        return nout;
    }

    bool structurally_saturated(uint64_t mask){return config_by_id(ensure_config(mask)).legal_add==0;}

    uint64_t transform_lut(uint64_t m,const std::array<std::array<uint64_t,1024>,4>&lut)const{
        return lut[0][m&1023ULL]|lut[1][(m>>10)&1023ULL]|lut[2][(m>>20)&1023ULL]|lut[3][(m>>30)&1023ULL];
    }

    uint64_t canonical_base_key(const State&s,Player target)const{
        auto pack=[&](uint64_t mask,uint8_t p0,uint8_t p1,Player turn,Player tar){uint64_t x=mask;x=(x<<6)|p0;x=(x<<6)|p1;x=(x<<1)|uint64_t(turn);x=(x<<1)|uint64_t(tar);return x+1;};
        if(symmetry_mode==0)return pack(s.walls_mask,s.p[0],s.p[1],s.turn,target);
        if(symmetry_mode==1){uint64_t a=pack(s.walls_mask,s.p[0],s.p[1],s.turn,target);uint64_t mm=transform_lut(s.walls_mask,mirror_lut_);uint64_t b=pack(mm,mirror_sq[s.p[0]],mirror_sq[s.p[1]],s.turn,target);return std::min(a,b);}
        const ConfigData&cd=config_by_id(s.cfg_id);uint64_t best=std::numeric_limits<uint64_t>::max();uint8_t xs=cd.canonical_xforms;
        if(xs&1u)best=std::min(best,pack(cd.canonical_wall,s.p[0],s.p[1],s.turn,target));
        if(xs&2u)best=std::min(best,pack(cd.canonical_wall,mirror_sq[s.p[0]],mirror_sq[s.p[1]],s.turn,target));
        if(xs&4u)best=std::min(best,pack(cd.canonical_wall,rotate_sq[s.p[1]],rotate_sq[s.p[0]],other(s.turn),other(target)));
        if(xs&8u)best=std::min(best,pack(cd.canonical_wall,mirror_sq[rotate_sq[s.p[1]]],mirror_sq[rotate_sq[s.p[0]]],other(s.turn),other(target)));
        return best;
    }

    uint64_t canonical_key(const State&s,Player target,int depth,bool cap_stocks)const{
        auto pack=[&](uint64_t mask,uint8_t p0,uint8_t p1,uint8_t w0,uint8_t w1,Player turn,Player tar){uint64_t x=mask;x=(x<<6)|p0;x=(x<<6)|p1;x=(x<<5)|w0;x=(x<<5)|w1;x=(x<<1)|uint64_t(turn);x=(x<<1)|uint64_t(tar);return x+1;};
        uint8_t w0=s.walls[0],w1=s.walls[1];
        if(cap_stocks){int first=(depth+1)/2,second=depth/2;int turns0=s.turn==P1?first:second;int turns1=s.turn==P2?first:second;w0=uint8_t(std::min<int>(w0,turns0));w1=uint8_t(std::min<int>(w1,turns1));}
        if(symmetry_mode==0)return pack(s.walls_mask,s.p[0],s.p[1],w0,w1,s.turn,target);
        if(symmetry_mode==1){uint64_t a=pack(s.walls_mask,s.p[0],s.p[1],w0,w1,s.turn,target);uint64_t mm=transform_lut(s.walls_mask,mirror_lut_);uint64_t b=pack(mm,mirror_sq[s.p[0]],mirror_sq[s.p[1]],w0,w1,s.turn,target);return std::min(a,b);}
        const ConfigData&cd=config_by_id(s.cfg_id);
        uint64_t best=std::numeric_limits<uint64_t>::max();
        uint8_t xs=cd.canonical_xforms;
        if(xs&1u) best=std::min(best,pack(cd.canonical_wall,s.p[0],s.p[1],w0,w1,s.turn,target));
        if(xs&2u) best=std::min(best,pack(cd.canonical_wall,mirror_sq[s.p[0]],mirror_sq[s.p[1]],w0,w1,s.turn,target));
        if(xs&4u) best=std::min(best,pack(cd.canonical_wall,rotate_sq[s.p[1]],rotate_sq[s.p[0]],w1,w0,other(s.turn),other(target)));
        if(xs&8u) best=std::min(best,pack(cd.canonical_wall,mirror_sq[rotate_sq[s.p[1]]],mirror_sq[rotate_sq[s.p[0]]],w1,w0,other(s.turn),other(target)));
        return best;
    }

private:
    void init_geometry(){
        neigh.resize(N);mirror_sq.resize(N);rotate_sq.resize(N);
        board_mask_=N==32?~0u:((1u<<N)-1u);
        for(int r=0;r<H;r++)for(int c=0;c<W;c++){int p=r*W+c;neigh[p]={uint8_t(r>0?p-W:255),uint8_t(r+1<H?p+W:255),uint8_t(c>0?p-1:255),uint8_t(c+1<W?p+1:255)};mirror_sq[p]=sq(r,W-1-c);rotate_sq[p]=sq(H-1-r,W-1-c);for(int d=0;d<4;d++)if(neigh[p][d]!=255)base_dir_[d]|=1u<<p;}
        for(int c=0;c<W;c++){top_goal_mask_|=1u<<sq(0,c);bottom_goal_mask_|=1u<<sq(H-1,c);}
        wall_conflict.assign(2*S,0);auto wi=[&](int ori,int r,int c){return ori*S+slot(r,c);};
        for(int r=0;r<R;r++)for(int c=0;c<C;c++){int h=wi(0,r,c),v=wi(1,r,c);wall_conflict[h]|=1ULL<<h;wall_conflict[v]|=1ULL<<v;wall_conflict[h]|=1ULL<<v;wall_conflict[v]|=1ULL<<h;
            if(c>0){int j=wi(0,r,c-1);wall_conflict[h]|=1ULL<<j;wall_conflict[j]|=1ULL<<h;}if(c+1<C){int j=wi(0,r,c+1);wall_conflict[h]|=1ULL<<j;wall_conflict[j]|=1ULL<<h;}
            if(r>0){int j=wi(1,r-1,c);wall_conflict[v]|=1ULL<<j;wall_conflict[j]|=1ULL<<v;}if(r+1<R){int j=wi(1,r+1,c);wall_conflict[v]|=1ULL<<j;wall_conflict[j]|=1ULL<<v;}}
        std::array<uint8_t,40> mb{},rb{},mrb{};
        for(int w=0;w<2*S;w++){int ori=w/S,z=w%S,r=z/C,c=z%C;mb[w]=uint8_t(ori*S+slot(r,C-1-c));rb[w]=uint8_t(ori*S+slot(R-1-r,C-1-c));mrb[w]=uint8_t(ori*S+slot(R-1-r,c));}
        for(int ch=0;ch<4;ch++)for(int v=0;v<1024;v++){uint64_t a=0,b=0,c=0;for(int bit=0;bit<10;bit++){int w=ch*10+bit;if(w>=2*S)break;if(v&(1<<bit)){a|=1ULL<<mb[w];b|=1ULL<<rb[w];c|=1ULL<<mrb[w];}}mirror_lut_[ch][v]=a;rotate_lut_[ch][v]=b;mirror_rotate_lut_[ch][v]=c;}
        for(int r=0;r<R;r++)for(int c=0;c<C;c++){
            int h=slot(r,c),v=S+slot(r,c);
            wall_block_[h][1]|=(1u<<sq(r,c))|(1u<<sq(r,c+1));
            wall_block_[h][0]|=(1u<<sq(r+1,c))|(1u<<sq(r+1,c+1));
            wall_block_[v][3]|=(1u<<sq(r,c))|(1u<<sq(r+1,c));
            wall_block_[v][2]|=(1u<<sq(r,c+1))|(1u<<sq(r+1,c+1));
        }
        for(int ch=0;ch<4;ch++)for(int v=0;v<1024;v++)for(int bit=0;bit<10;bit++){
            int w=ch*10+bit;
            if(w>=2*S) break;
            if(v&(1<<bit)){
                for(int d=0;d<4;d++) block_lut_[ch][v][d]|=wall_block_[w][d];
                conflict_lut_[ch][v]|=wall_conflict[w];
            }
        }
    }
    uint8_t compute_clear(uint64_t mask,int r,int c)const{
        uint64_t hm=mask&((1ULL<<S)-1),vm=mask>>S;uint8_t z=0;
        if(r>0){int br=r-1;bool b=(c<C&&((hm>>slot(br,c))&1))||(c>0&&((hm>>slot(br,c-1))&1));if(!b)z|=1u<<0;}
        if(r+1<H){int br=r;bool b=(c<C&&((hm>>slot(br,c))&1))||(c>0&&((hm>>slot(br,c-1))&1));if(!b)z|=1u<<1;}
        if(c>0){int bc=c-1;bool b=(r<R&&((vm>>slot(r,bc))&1))||(r>0&&((vm>>slot(r-1,bc))&1));if(!b)z|=1u<<2;}
        if(c+1<W){int bc=c;bool b=(r<R&&((vm>>slot(r,bc))&1))||(r>0&&((vm>>slot(r-1,bc))&1));if(!b)z|=1u<<3;}
        return z;
    }
    void bfs_goal(const std::array<uint32_t,4>&dir,uint32_t goals,std::array<uint8_t,32>&dist)const{
        dist.fill(255);uint32_t seen=goals,front=goals;for(uint32_t x=goals;x;x&=x-1)dist[std::countr_zero(x)]=0;uint8_t depth=0;
        while(front){++depth;uint32_t next=(((front&dir[0])>>W)|((front&dir[1])<<W)|((front&dir[2])>>1)|((front&dir[3])<<1))&board_mask_&~seen;if(!next)break;for(uint32_t x=next;x;x&=x-1)dist[std::countr_zero(x)]=depth;seen|=next;front=next;}
    }
    void set_canonical_wall(ConfigData&d,uint64_t mask)const{
        std::array<uint64_t,4> v{mask,transform_lut(mask,mirror_lut_),transform_lut(mask,rotate_lut_),transform_lut(mask,mirror_rotate_lut_)};
        d.canonical_wall=*std::min_element(v.begin(),v.end());
        d.canonical_xforms=0;
        for(int i=0;i<4;i++) if(v[i]==d.canonical_wall) d.canonical_xforms|=uint8_t(1u<<i);
    }
    ConfigData build_config(uint64_t mask)const{
        if(mask&~structural_mask)throw std::runtime_error("wall mask outside board");
        ConfigData d;std::array<uint32_t,4> blocked{};for(int ch=0;ch<4;ch++){int v=int((mask>>(10*ch))&1023ULL);for(int k=0;k<4;k++)blocked[k]|=block_lut_[ch][v][k];}for(int k=0;k<4;k++)d.dir[k]=base_dir_[k]&~blocked[k];
        bfs_goal(d.dir,top_goal_mask_,d.dist0);bfs_goal(d.dir,bottom_goal_mask_,d.dist1);
        if(std::popcount(mask)<max_total_walls){
            uint64_t conflicts=0;
            for(int ch=0;ch<4;ch++) conflicts|=conflict_lut_[ch][(mask>>(10*ch))&1023ULL];
            d.legal_add=structural_mask&~conflicts;
        }
        set_canonical_wall(d,mask);
        return d;
    }

};

class ProofSolver {
    struct LocalTable {
        static constexpr uint8_t WIN_NONE=0xff;
        static constexpr uint16_t MOVE_NONE=0x1ff;
        std::vector<uint32_t> meta;
        explicit LocalTable(size_t n):meta(n,uint32_t(WIN_NONE)|(uint32_t(MOVE_NONE)<<16)){}
        static uint8_t wd(uint32_t m){return uint8_t(m);}static uint8_t fd(uint32_t m){return uint8_t(m>>8);}static uint16_t bm(uint32_t m){return uint16_t((m>>16)&0x1ff);}
        bool probe(size_t i,int depth,bool&value,uint16_t&hint)const{uint32_t m=meta[i];uint16_t b=bm(m);hint=b==MOVE_NONE?0xffff:b;uint8_t w=wd(m),f=fd(m);if(w!=WIN_NONE&&depth>=int(w)){value=true;return true;}if(depth<=int(f)){value=false;return true;}return false;}
        void record(size_t i,int depth,bool value,uint16_t move){uint32_t m=meta[i];uint8_t w=wd(m),f=fd(m);uint16_t b=bm(m);if(value)w=uint8_t(std::min<int>(w,depth));else f=uint8_t(std::max<int>(f,depth));if(w!=WIN_NONE&&f>=w)throw std::runtime_error("inconsistent local TT bounds");if(move!=0xffff)b=move;meta[i]=uint32_t(w)|(uint32_t(f)<<8)|(uint32_t(b&0x1ff)<<16);}
    };
    struct LocalSlot { std::array<uint32_t,2> visits{}; std::array<std::unique_ptr<LocalTable>,2> table{}; };
    LazyEngine&e;TransTable tt;DominanceTable dom;bool use_tt=true;bool cap_stocks=false;int local_threshold=0,local_max=0,local_count=0;size_t local_entries=0;std::vector<LocalSlot> local_slots;uint64_t local_hits=0,local_probes=0,dominance_hits=0,dominance_probes=0;Clock::time_point deadline;uint64_t nodes=0,tt_hits=0,cutoffs=0;
    void ensure_local_slot(uint32_t id){if(id<local_slots.size())return;size_t n=local_slots.empty()?1024:local_slots.size();while(n<=id)n*=2;local_slots.resize(n);}
    size_t local_index(const State&s)const{return ((((size_t(s.walls[0])*(e.walls_each+1)+s.walls[1])*2+size_t(s.turn))*e.N+s.p[0])*e.N+s.p[1]);}
    LocalTable* local_for(const State&s,Player target){if(local_threshold<=0)return nullptr;ensure_local_slot(s.cfg_id);auto&slot=local_slots[s.cfg_id];uint32_t&v=slot.visits[int(target)];if(v!=UINT32_MAX)++v;if(!slot.table[int(target)]&&int(v)>=local_threshold&&local_count<local_max){slot.table[int(target)]=std::make_unique<LocalTable>(local_entries);++local_count;}return slot.table[int(target)].get();}
public:
    struct Result{bool solved=false;Player winner=P1;int depth=-1;uint64_t nodes=0,tt_hits=0,cutoffs=0,local_hits=0,local_probes=0,dominance_hits=0,dominance_probes=0;int local_tables=0;double seconds=0;bool timeout=false;};
    ProofSolver(LazyEngine&eng,unsigned tt_bits,bool transpositions=true,bool horizon_stock_cap=false,int tt_ways=2,int local_tt_threshold=0,int local_tt_max=0,unsigned dominance_tt_bits=0):e(eng),tt(transpositions?tt_bits:10,tt_ways),dom(dominance_tt_bits),use_tt(transpositions),cap_stocks(horizon_stock_cap),local_threshold(local_tt_threshold),local_max(local_tt_max){local_entries=size_t(e.walls_each+1)*(e.walls_each+1)*2*e.N*e.N;std::cerr<<"TT="<<(use_tt?LazyEngine::human_bytes(tt.bytes()):std::string("disabled"))<<" ways="<<tt_ways<<" lazy_cache stock_cap="<<cap_stocks<<" local_threshold="<<local_threshold<<" local_max="<<local_max<<" local_table="<<LazyEngine::human_bytes(local_entries*4)<<"\n";}
    static inline int target_relevant_depth(Player turn,Player target,int depth){if(depth<=0||((turn==target)==((depth&1)!=0)))return depth;return depth-1;}
    bool prove(const State&s,Player target,int depth,std::vector<std::array<LazyEngine::Child,192>>&lists,int ply){
        ++nodes;e.record_node_visit(s.cfg_id);if((nodes&16383ULL)==0&&Clock::now()>=deadline)throw 1;Player win;if(e.terminal(s,win))return win==target;depth=target_relevant_depth(s.turn,target,depth);if(depth<=0)return false;
        uint64_t key=e.canonical_key(s,target,depth,cap_stocks);bool cached;uint16_t hint=0xffff;LocalTable*lt=local_for(s,target);size_t li=0;if(lt){++local_probes;li=local_index(s);if(lt->probe(li,depth,cached,hint)){++local_hits;return cached;}}
        if(use_tt&&tt.probe(key,depth,cached,hint)){++tt_hits;if(lt)lt->record(li,depth,cached,hint);return cached;}
        uint64_t base_key=0;int own_walls=int(s.walls[int(target)]);
        if(dom.enabled()){++dominance_probes;base_key=e.canonical_base_key(s,target);if(dom.probe(base_key,own_walls,depth,cached)){++dominance_hits;return cached;}}
        auto&ch=lists[ply];int n=e.generate(s,target,ch.data(),true);if(n==0){if(use_tt)tt.record(key,depth,false,0xffff);if(lt)lt->record(li,depth,false,0xffff);if(dom.enabled())dom.record(base_key,own_walls,depth,false);return false;}if(hint!=0xffff)for(int i=0;i<n;i++)if(ch[i].move==hint){if(i)std::swap(ch[0],ch[i]);break;}
        bool result;uint16_t best=0xffff;uint64_t hardest=0;
        if(s.turn==target){result=false;for(int i=0;i<n;i++){uint64_t before=nodes;if(prove(ch[i].s,target,depth-1,lists,ply+1)){result=true;best=ch[i].move;++cutoffs;break;}uint64_t cost=nodes-before;if(cost>hardest){hardest=cost;best=ch[i].move;}}}
        else{result=true;for(int i=0;i<n;i++){uint64_t before=nodes;if(!prove(ch[i].s,target,depth-1,lists,ply+1)){result=false;best=ch[i].move;++cutoffs;break;}uint64_t cost=nodes-before;if(cost>hardest){hardest=cost;best=ch[i].move;}}}
        if(use_tt) tt.record(key,depth,result,best);
        if(lt) lt->record(li,depth,result,best);
        if(dom.enabled())dom.record(base_key,own_walls,depth,result);
        return result;
    }
    Result solve_from(State root,double seconds,int max_depth,int start_depth=1,int target_filter=-1){Result out;auto t0=Clock::now();deadline=t0+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));std::vector<std::array<LazyEngine::Child,192>>lists(size_t(max_depth)+2);int checked[2]={0,0};
        for(int d=start_depth;d<=max_depth;d++)for(Player target:{P1,P2}){if(target_filter>=0&&int(target)!=target_filter)continue;int rd=target_relevant_depth(root.turn,target,d);if(rd<=0||rd<=checked[int(target)])continue;checked[int(target)]=rd;uint64_t before=nodes;bool ok=false;try{ok=prove(root,target,rd,lists,0);}catch(int){out.timeout=true;goto done;}std::cerr<<"depth="<<rd<<" target="<<(target==P1?1:2)<<" proven="<<ok<<" nodes="<<(nodes-before)<<" total="<<nodes<<" elapsed="<<std::chrono::duration<double>(Clock::now()-t0).count()<<"s tt_hits="<<tt_hits<<" cache="<<e.cache_size()<<"\n";if(ok){out.solved=true;out.winner=target;out.depth=rd;goto done;}if(Clock::now()>=deadline){out.timeout=true;goto done;}}
    done:out.nodes=nodes;out.tt_hits=tt_hits;out.cutoffs=cutoffs;out.local_hits=local_hits;out.local_probes=local_probes;out.local_tables=local_count;out.dominance_hits=dominance_hits;out.dominance_probes=dominance_probes;out.seconds=std::chrono::duration<double>(Clock::now()-t0).count();return out;}
};

} // namespace qdomain

int main(int argc,char**argv){using namespace qdomain;int W=3,H=9,walls=8,max_depth=80,start_depth=1,tt_bits=24,tt_ways=2,dominance_tt_bits=0,transition_cache_threshold=0,path_choice_weight=0,local_tt_threshold=0,local_tt_max=0,order=1,target_filter=-1,root_index=-1,root_index2=-1,root_index3=-1,child_depth=-1,scan_root_start=0,scan_root_end=-1;double seconds=60;bool scan_current=false,list_root=false,list_second=false,list_third=false,use_tt=true,horizon_stock_cap=false,profile_visits=false;int symmetry=2;size_t cache_reserve=65536;
    for(int i=1;i<argc;i++){std::string a=argv[i];auto val=[&](auto&x){if(i+1>=argc)throw std::runtime_error("missing arg");std::stringstream ss(argv[++i]);ss>>x;};
        if(a=="--width")val(W);else if(a=="--height")val(H);else if(a=="--walls")val(walls);else if(a=="--max-depth")val(max_depth);else if(a=="--start-depth")val(start_depth);else if(a=="--target")val(target_filter);else if(a=="--tt-bits")val(tt_bits);else if(a=="--tt-ways")val(tt_ways);else if(a=="--dominance-tt-bits")val(dominance_tt_bits);else if(a=="--transition-cache-threshold")val(transition_cache_threshold);else if(a=="--path-choice-weight")val(path_choice_weight);else if(a=="--local-tt-threshold")val(local_tt_threshold);else if(a=="--local-tt-max")val(local_tt_max);else if(a=="--order")val(order);else if(a=="--seconds")val(seconds);else if(a=="--root-index")val(root_index);else if(a=="--root-index2")val(root_index2);else if(a=="--root-index3")val(root_index3);else if(a=="--child-depth")val(child_depth);else if(a=="--scan-root-start")val(scan_root_start);else if(a=="--scan-root-end")val(scan_root_end);else if(a=="--scan-current")scan_current=true;else if(a=="--list-root")list_root=true;else if(a=="--list-second")list_second=true;else if(a=="--list-third")list_third=true;else if(a=="--no-tt")use_tt=false;else if(a=="--no-symmetry")symmetry=0;else if(a=="--mirror-only")symmetry=1;else if(a=="--cache-reserve")val(cache_reserve);else if(a=="--horizon-stock-cap")horizon_stock_cap=true;else if(a=="--profile-config-visits")profile_visits=true;else if(a=="--no-bounds"||a=="--no-pawn-table"){}else if(a=="--help"){std::cout<<"lazy_frontier_solver --width 4 --height 7 --walls 7 --root-index 0 --root-index2 0 --root-index3 8 --target 1 --start-depth 24 --max-depth 24 --tt-bits 27\n";return 0;}else throw std::runtime_error("unknown argument: "+a);}
    if(target_filter==1)target_filter=0; else if(target_filter==2)target_filter=1; else target_filter=-1;
    try{LazyEngine e(W,H,walls,order,symmetry,cache_reserve,profile_visits,transition_cache_threshold,path_choice_weight);State root=e.initial();auto label=[&](uint16_t mv){std::ostringstream o;if(mv<0x100){o<<"P("<<e.row(uint8_t(mv))<<","<<e.col(uint8_t(mv))<<")";}else{int w=mv-0x100,ori=w/e.S,z=w%e.S;o<<(ori?"V":"H")<<"("<<z/e.C<<","<<z%e.C<<")";}return o.str();};
        auto choose=[&](State s,int idx,bool list,const char*name)->State{std::array<LazyEngine::Child,192>ch{};Player target=target_filter==1?P2:P1;int n=e.generate(s,target,ch.data(),true);for(int i=0;i<n;i++)if(list)std::cout<<name<<"["<<i<<"] move="<<label(ch[i].move)<<" score="<<ch[i].score<<"\n";if(idx<0)return s;if(idx>=n)throw std::runtime_error("child index out of range");std::cerr<<"forcing "<<name<<"["<<idx<<"] move="<<label(ch[idx].move)<<"\n";return ch[idx].s;};
        if(list_root){choose(root,-1,true,"root");return 0;}if(root_index>=0)root=choose(root,root_index,false,"root");if(list_second){choose(root,-1,true,"second");return 0;}if(root_index2>=0)root=choose(root,root_index2,false,"second");if(list_third){choose(root,-1,true,"third");return 0;}if(root_index3>=0)root=choose(root,root_index3,false,"third");
        if(scan_current){
            if(target_filter<0)throw std::runtime_error("scan-current requires --target 1 or 2");
            if(child_depth<0)child_depth=max_depth-1;
            std::array<LazyEngine::Child,192> raw{};Player target=target_filter==0?P1:P2;
            int nr=e.generate(root,target,raw.data(),true);int first=std::max(0,scan_root_start),last=scan_root_end<0?nr-1:std::min(nr-1,scan_root_end);
            if(first>last||first>=nr)throw std::runtime_error("empty current scan range");
            int proved=0,refuted=0,unresolved=0;uint64_t aggregate_nodes=0;double aggregate_seconds=0;
            for(int i=first;i<=last;i++){
                ProofSolver branch(e,tt_bits,use_tt,horizon_stock_cap,tt_ways,local_tt_threshold,local_tt_max,dominance_tt_bits);
                auto br=branch.solve_from(raw[i].s,seconds,child_depth,child_depth,int(target));aggregate_nodes+=br.nodes;aggregate_seconds+=br.seconds;bool win=br.solved&&br.winner==target;
                if(br.timeout)++unresolved;else if(win)++proved;else ++refuted;
                std::cout<<"current_scan task="<<i<<" rep="<<i<<" aliases="<<i<<" move="<<label(raw[i].move)<<" proven="<<win<<" timeout="<<br.timeout<<" nodes="<<br.nodes<<" tt_hits="<<br.tt_hits<<" seconds="<<br.seconds<<" child_depth="<<child_depth<<" total_suffix="<<(child_depth+1)<<" cache_configs="<<e.cache_size()<<" transition_entries="<<e.transition_entries()<<"\n"<<std::flush;
                if(root.turn==target&&win) break;
                if(root.turn!=target&&!br.timeout&&!win) break;
            }
            bool complete=first==0&&last==nr-1;bool bounded_proof=root.turn==target?proved>0:(refuted==0&&unresolved==0&&complete);bool bounded_refutation=root.turn==target?(proved==0&&unresolved==0&&complete):refuted>0;
            std::cout<<"current_scan_result proven="<<bounded_proof<<" refuted="<<bounded_refutation<<" child_proved="<<proved<<" child_refuted="<<refuted<<" child_unresolved="<<unresolved<<" aggregate_nodes="<<aggregate_nodes<<" aggregate_seconds="<<aggregate_seconds<<" total_suffix="<<(child_depth+1)<<" range="<<first<<"-"<<last<<" tasks="<<nr<<" raw="<<nr<<" unique=0 cache_configs="<<e.cache_size()<<" transition_entries="<<e.transition_entries()<<"\n";
            return bounded_proof?0:(bounded_refutation?1:(unresolved?3:1));
        }
        ProofSolver ps(e,tt_bits,use_tt,horizon_stock_cap,tt_ways,local_tt_threshold,local_tt_max,dominance_tt_bits);auto r=ps.solve_from(root,seconds,max_depth,start_depth,target_filter);std::cout<<"width="<<W<<" height="<<H<<" walls="<<walls<<" solved="<<r.solved;if(r.solved)std::cout<<" winner="<<(r.winner==P1?1:2)<<" depth="<<r.depth;std::cout<<" nodes="<<r.nodes<<" tt_hits="<<r.tt_hits<<" cutoffs="<<r.cutoffs<<" local_hits="<<r.local_hits<<" local_probes="<<r.local_probes<<" local_tables="<<r.local_tables<<" dominance_hits="<<r.dominance_hits<<" dominance_probes="<<r.dominance_probes<<" seconds="<<r.seconds<<" timeout="<<r.timeout<<" cache_configs="<<e.cache_size()<<" cache_hits="<<e.cache_hits()<<" cache_misses="<<e.cache_misses()<<" cache_payload="<<e.cache_payload_bytes()<<" cache_estimated="<<e.cache_estimated_bytes()<<" transition_hits="<<e.transition_hits()<<" transition_builds="<<e.transition_builds()<<" transition_entries="<<e.transition_entries();if(profile_visits)std::cout<<" "<<e.visit_profile();std::cout<<"\n";
    }catch(const std::exception&ex){std::cerr<<"error: "<<ex.what()<<"\n";return 2;}return 0;}
