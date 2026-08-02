#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
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

namespace qspec {

#if defined(QSPEC_MASK_INDEX_PROBE_PROFILE) && !defined(QSPEC_MASK_INDEX_PROBE_EXPERIMENT)
#error "QSPEC_MASK_INDEX_PROBE_PROFILE requires QSPEC_MASK_INDEX_PROBE_EXPERIMENT"
#endif
#if defined(QSPEC_TT_SLOT_REUSE_PROFILE) && !defined(QSPEC_TT_SLOT_REUSE_EXPERIMENT)
#error "QSPEC_TT_SLOT_REUSE_PROFILE requires QSPEC_TT_SLOT_REUSE_EXPERIMENT"
#endif

struct SearchTimeout final {};

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
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
    uint64_t reused_miss_slots_ = 0;
    uint64_t reused_miss_probes_ = 0;
    uint64_t rehash_fallbacks_ = 0;
#endif
#if defined(QSPEC_MASK_INDEX_PROBE_EXPERIMENT) && !defined(NDEBUG)
    size_t generation_ = 0;
#endif

    void rehash(size_t cap) {
        size_t n=1; while(n<cap)n<<=1;
        std::vector<uint64_t> oldk=std::move(keys_);
        std::vector<uint32_t> oldv=std::move(vals_);
        keys_.assign(n,0); vals_.resize(n); mask_=n-1; size_=0;
        for(size_t i=0;i<oldk.size();++i) if(oldk[i]) insert_raw(oldk[i]-1,oldv[i]);
#if defined(QSPEC_MASK_INDEX_PROBE_EXPERIMENT) && !defined(NDEBUG)
        ++generation_;
#endif
    }
    void insert_raw(uint64_t key,uint32_t value) {
        size_t i=size_t(mix64(key))&mask_; while(keys_[i])i=(i+1)&mask_;
        keys_[i]=key+1; vals_[i]=value; ++size_;
    }
public:
    explicit FlatMaskIndex(size_t reserve=1024){rehash(std::max<size_t>(16,reserve*2));}
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
    struct Probe {
        uint32_t value;
        size_t slot;
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
        uint32_t probes;
#endif
#ifndef NDEBUG
        uint64_t key;
        size_t generation;
#endif
    };
    Probe probe(uint64_t key) const {
        size_t i=size_t(mix64(key))&mask_; uint64_t stored=key+1;
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
        uint32_t probes=1;
#endif
        while(true){uint64_t k=keys_[i];if(!k)return {UINT32_MAX,i
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
            ,probes
#endif
#ifndef NDEBUG
            ,key,generation_
#endif
        };if(k==stored)return {vals_[i],i
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
            ,probes
#endif
#ifndef NDEBUG
            ,key,generation_
#endif
        };i=(i+1)&mask_;
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
        ++probes;
#endif
        }
    }
#endif
    uint32_t find(uint64_t key) const {
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
        return probe(key).value;
#else
        size_t i=size_t(mix64(key))&mask_; uint64_t stored=key+1;
        while(true){uint64_t k=keys_[i];if(!k)return UINT32_MAX;if(k==stored)return vals_[i];i=(i+1)&mask_;}
#endif
    }
    void insert(uint64_t key,uint32_t value){if((size_+1)*10>keys_.size()*7)rehash(keys_.size()*2);insert_raw(key,value);
#if defined(QSPEC_MASK_INDEX_PROBE_EXPERIMENT) && !defined(NDEBUG)
        ++generation_;
#endif
    }
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
    void insert_at_miss(uint64_t key,uint32_t value,const Probe& miss) {
#ifndef NDEBUG
        if(miss.value!=UINT32_MAX||miss.key!=key||miss.generation!=generation_||find(key)!=UINT32_MAX)
            throw std::runtime_error("stale or invalid mask-index miss token");
#endif
        if((size_+1)*10>keys_.size()*7){rehash(keys_.size()*2);insert_raw(key,value);
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
            ++rehash_fallbacks_;
#endif
#ifndef NDEBUG
            ++generation_;
#endif
            return;}
        if(keys_[miss.slot])throw std::runtime_error("mask-index miss slot invalidated before insertion");
        keys_[miss.slot]=key+1;vals_[miss.slot]=value;++size_;
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
        ++reused_miss_slots_;reused_miss_probes_+=miss.probes;
#endif
#ifndef NDEBUG
        ++generation_;
#endif
    }
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
    uint64_t reused_miss_slots()const{return reused_miss_slots_;}
    uint64_t reused_miss_probes()const{return reused_miss_probes_;}
    uint64_t rehash_fallbacks()const{return rehash_fallbacks_;}
#endif
#endif
    size_t bytes()const{return keys_.capacity()*sizeof(uint64_t)+vals_.capacity()*sizeof(uint32_t);}
};

enum Player : uint8_t { P1 = 0, P2 = 1 };
static inline Player other(Player p) { return p == P1 ? P2 : P1; }

struct State {
    uint64_t walls_mask = 0;
    uint32_t cfg_id = 0;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    // cfg_id == UINT32_MAX means that this state carries a cache-first local
    // touch handle.  The low six bits name the added wall and the remaining
    // bits name its already-materialised parent configuration.
    uint32_t deferred_ref = UINT32_MAX;
#endif
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
#ifdef QSPEC_TT_SLOT_REUSE_PROFILE
    uint64_t slot_reuses_ = 0;
#endif
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
#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
    struct ProbeToken {
        // TT bits are capped at 30, so both immutable candidate slots fit in
        // 32 bits. Keeping the release token at eight bytes limits parent
        // recursion-frame pressure.
        uint32_t first = 0;
        uint32_t second = 0;
#ifndef NDEBUG
        const TransTable* owner = nullptr;
        uint64_t key = 0;
        int ways = 0;
#endif
    };
#endif
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

#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
    bool probe_with_token(uint64_t key,int depth,bool&value,uint16_t&hint,ProbeToken&token)const{
        hint=0xffff;
        if(ways_==2){
            auto [a,b]=slots(key);token.first=uint32_t(a);token.second=uint32_t(b);
#ifndef NDEBUG
            token.owner=this;token.key=key;token.ways=ways_;
#endif
            for(size_t i:{a,b}){if(keys_[i]!=key)continue;uint32_t m=meta_[i];uint16_t bm=best_move(m);hint=(bm==MOVE_NONE?0xffff:bm);uint8_t wd=win_depth(m),fd=fail_depth(m);if(wd!=WIN_NONE&&depth>=int(wd)){value=true;return true;}if(depth<=int(fd)){value=false;return true;}return false;}
            return false;
        }
        size_t base=(size_t(mix64(key))&bucket_mask_)*4;token.first=uint32_t(base);token.second=uint32_t(base+4);
#ifndef NDEBUG
        token.owner=this;token.key=key;token.ways=ways_;
#endif
        for(size_t i=base;i<base+4;i++){if(keys_[i]!=key)continue;uint32_t m=meta_[i];uint16_t bm=best_move(m);hint=(bm==MOVE_NONE?0xffff:bm);uint8_t wd=win_depth(m),fd=fail_depth(m);if(wd!=WIN_NONE&&depth>=int(wd)){value=true;return true;}if(depth<=int(fd)){value=false;return true;}return false;}
        return false;
    }
#endif

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

#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
    void record_from_probe(uint64_t key,int depth,bool value,uint16_t move,const ProbeToken&token){
        if(depth<0||depth>=255)throw std::runtime_error("TT depth exceeds packed range");
#ifndef NDEBUG
        if(token.owner!=this||token.key!=key||token.ways!=ways_)throw std::runtime_error("TT probe token does not match record request");
        if(ways_==2){auto [a,b]=slots(key);if(token.first!=a||token.second!=b)throw std::runtime_error("TT probe token has invalid two-way slots");}
        else{size_t base=(size_t(mix64(key))&bucket_mask_)*4;if(token.first!=base||token.second!=base+4)throw std::runtime_error("TT probe token has invalid four-way bucket");}
#endif
        size_t i=0;
        if(ways_==2){size_t a=token.first,b=token.second;if(keys_[a]==key)i=a;else if(keys_[b]==key)i=b;else i=quality(a)<=quality(b)?a:b;}
        else{size_t base=token.first;i=base;for(size_t j=base;j<token.second;j++){if(keys_[j]==key){i=j;break;}if(quality(j)<quality(i))i=j;}}
        uint8_t wd=WIN_NONE,fd=0;uint16_t bm=MOVE_NONE;
        if(keys_[i]==key){uint32_t old=meta_[i];wd=win_depth(old);fd=fail_depth(old);bm=best_move(old);}else keys_[i]=key;
        if(value)wd=uint8_t(std::min<int>(wd,depth));else fd=uint8_t(std::max<int>(fd,depth));
        if(wd!=WIN_NONE&&fd>=wd)throw std::runtime_error("inconsistent transposition bounds");
        if(move!=0xffff){if(move>0x1fe)throw std::runtime_error("move id exceeds packed TT range");bm=move;}
        meta_[i]=pack_meta(wd,fd,bm);
#ifdef QSPEC_TT_SLOT_REUSE_PROFILE
        ++slot_reuses_;
#endif
    }
#ifdef QSPEC_TT_SLOT_REUSE_PROFILE
    uint64_t slot_reuses()const{return slot_reuses_;}
#endif
#endif

};

class LazyEngine {
public:
    int W,H,C,R,S,N;
    int walls_each,max_total_walls;
    int order_mode=1;
    int path_choice_weight=0;
    int path_flow_weight=0;
    int symmetry_mode=2;
    uint64_t structural_mask=0;
    std::vector<std::array<uint8_t,4>> neigh;
    std::vector<uint8_t> mirror_sq,rotate_sq;
    std::vector<uint64_t> wall_conflict;
    std::array<std::array<uint32_t,4>,40> wall_block_{};
    std::array<std::array<uint64_t,4>,32> edge_walls_{};
    std::array<std::array<uint8_t,3>,40> wall_junctions_{};

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
    bool profile_cycle_gate_=false;
    bool defer_cycle_safe_=false;
    std::vector<uint64_t> node_visits_;
    std::vector<std::array<uint8_t,64>> junction_components_;
    uint64_t cache_hits_=0,cache_misses_=0,deferred_emitted_=0,deferred_resolved_=0;
    uint64_t cycle_gate_safe_=0,cycle_gate_fallback_=0;
    int junction_width_=0,junction_count_=0;

    struct FlowCacheEntry {
        uint64_t key=0;
        std::array<uint16_t,40> impact{};
    };
    std::vector<FlowCacheEntry> flow_cache_;
    size_t flow_cache_mask_=0;
    uint64_t flow_cache_hits_=0,flow_cache_misses_=0;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    static constexpr uint32_t PENDING_TRANSITION_ID=(1u<<26)-1;
    std::array<uint64_t,64> junction_incident_walls_{};
    uint64_t boundary_junctions_=0;
    int local_touch_refine_=0; // -1 means all proxy-ranked handles.
    uint64_t local_touch_exact_hits_=0,local_touch_safe_misses_=0,local_touch_fallback_misses_=0;
    uint64_t local_touch_pending_replayed_=0,local_touch_pending_patched_=0;
    uint64_t local_touch_resolve_hits_=0,local_touch_resolve_builds_=0;
    uint64_t local_touch_pruned_=0,local_touch_pruned_uncached_=0;
    uint64_t local_touch_refined_=0,local_touch_refine_order_changes_=0;
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    static constexpr uint16_t ZERO_WALL_UNKNOWN=std::numeric_limits<uint16_t>::max();
    struct ZeroWallTablebase {
        std::array<std::vector<uint16_t>,2> rank;
        uint64_t edges=0;
        uint64_t ranked=0;
    };
    std::vector<uint32_t> zero_wall_visits_;
    std::vector<std::unique_ptr<ZeroWallTablebase>> zero_wall_tables_;
    int zero_wall_threshold_=0;
    int zero_wall_max_=4096;
    uint64_t zero_wall_queries_=0,zero_wall_hits_=0,zero_wall_tt_misses_=0,zero_wall_bypassed_=0;
    uint64_t zero_wall_builds_=0,zero_wall_edges_=0,zero_wall_ranked_=0;
    double zero_wall_build_seconds_=0;
#endif

public:
    LazyEngine(int width,int height,int walls,int ordering=1,int symmetry=2,size_t reserve_configs=65536,bool profile_visits=false,int transition_threshold=0,int choice_weight=0,bool profile_cycle_gate=false,bool defer_cycle_safe=false,int flow_weight=0,int flow_cache_bits=18
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        ,int local_touch_refine=0
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        ,int zero_wall_threshold=0,int zero_wall_max=4096
#endif
    )
        :W(width),H(height),C(width-1),R(height-1),S(C*R),N(width*height),walls_each(walls),
         max_total_walls(std::min(2*walls,2*C*R)), cache_index_(reserve_configs) {
        order_mode=ordering;path_choice_weight=choice_weight;path_flow_weight=flow_weight;symmetry_mode=symmetry;profile_visits_=profile_visits;profile_cycle_gate_=profile_cycle_gate;defer_cycle_safe_=defer_cycle_safe;transition_threshold_=defer_cycle_safe?0:transition_threshold;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        if(defer_cycle_safe_)throw std::runtime_error("--defer-cycle-safe is incompatible with the cache-first local-touch experiment");
        if(local_touch_refine!=-1&&local_touch_refine!=0&&local_touch_refine!=2&&local_touch_refine!=4)throw std::runtime_error("local touch refinement must be 0, 2, 4, or all");
        local_touch_refine_=local_touch_refine;
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        if(zero_wall_threshold<0||zero_wall_max<0)throw std::runtime_error("zero-wall tablebase threshold/max must be non-negative");
        zero_wall_threshold_=zero_wall_threshold;zero_wall_max_=zero_wall_max;
#endif
        if(path_flow_weight){if(flow_cache_bits<10||flow_cache_bits>24)throw std::runtime_error("path flow cache bits must be 10..24");flow_cache_.resize(size_t(1)<<flow_cache_bits);flow_cache_mask_=flow_cache_.size()-1;}
        if(W<2||H<2||N>32||2*S>39)throw std::runtime_error("lazy engine currently supports N <= 32 and 2*S <= 39");
        if(symmetry_mode<0||symmetry_mode>2)throw std::runtime_error("symmetry mode must be 0..2");
        structural_mask=(uint64_t(1)<<(2*S))-1;
        init_geometry();
        cache_data_.reserve(reserve_configs);transition_offsets_.reserve(reserve_configs);transition_counts_.reserve(reserve_configs);transition_expansions_.reserve(reserve_configs);if(profile_visits_)node_visits_.reserve(reserve_configs);if(profile_cycle_gate_||defer_cycle_safe_)junction_components_.reserve(reserve_configs);
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        zero_wall_visits_.reserve(reserve_configs);zero_wall_tables_.reserve(reserve_configs);
#endif
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
    size_t cache_estimated_bytes()const{return cache_payload_bytes()+cache_index_.bytes()+node_visits_.capacity()*sizeof(uint64_t)+transition_offsets_.capacity()*sizeof(uint32_t)+transition_counts_.capacity()*sizeof(uint16_t)+transition_expansions_.capacity()*sizeof(uint16_t)+transition_entries_.capacity()*sizeof(uint32_t)+flow_cache_.capacity()*sizeof(FlowCacheEntry)
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        +sizeof(junction_incident_walls_)+sizeof(boundary_junctions_)
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        +zero_wall_visits_.capacity()*sizeof(uint32_t)+zero_wall_tables_.capacity()*sizeof(std::unique_ptr<ZeroWallTablebase>)+zero_wall_table_bytes()
#endif
        ;}
    uint64_t transition_hits()const{return transition_hits_;}
    uint64_t transition_builds()const{return transition_builds_;}
    size_t transition_entries()const{return transition_entries_.size();}
    uint64_t cycle_gate_safe()const{return cycle_gate_safe_;}
    uint64_t cycle_gate_fallback()const{return cycle_gate_fallback_;}
    uint64_t deferred_emitted()const{return deferred_emitted_;}
    uint64_t deferred_resolved()const{return deferred_resolved_;}
    uint64_t flow_cache_hits()const{return flow_cache_hits_;}
    uint64_t flow_cache_misses()const{return flow_cache_misses_;}
    size_t flow_cache_bytes()const{return flow_cache_.capacity()*sizeof(FlowCacheEntry);}
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
    uint64_t mask_probe_reused()const{return cache_index_.reused_miss_slots();}
    uint64_t mask_probe_slot_reads_saved()const{return cache_index_.reused_miss_probes();}
    uint64_t mask_probe_rehash_fallbacks()const{return cache_index_.rehash_fallbacks();}
#endif
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    uint64_t local_touch_exact_hits()const{return local_touch_exact_hits_;}
    uint64_t local_touch_safe_misses()const{return local_touch_safe_misses_;}
    uint64_t local_touch_fallback_misses()const{return local_touch_fallback_misses_;}
    uint64_t local_touch_pending_replayed()const{return local_touch_pending_replayed_;}
    uint64_t local_touch_pending_patched()const{return local_touch_pending_patched_;}
    uint64_t local_touch_resolve_hits()const{return local_touch_resolve_hits_;}
    uint64_t local_touch_resolve_builds()const{return local_touch_resolve_builds_;}
    uint64_t local_touch_pruned()const{return local_touch_pruned_;}
    uint64_t local_touch_pruned_uncached()const{return local_touch_pruned_uncached_;}
    uint64_t local_touch_bfs_passes_avoided()const{return local_touch_pruned_uncached_*2;}
    uint64_t local_touch_refined()const{return local_touch_refined_;}
    uint64_t local_touch_refine_order_changes()const{return local_touch_refine_order_changes_;}
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    int zero_wall_threshold()const{return zero_wall_threshold_;}
    int zero_wall_max()const{return zero_wall_max_;}
    uint64_t zero_wall_queries()const{return zero_wall_queries_;}
    uint64_t zero_wall_hits()const{return zero_wall_hits_;}
    uint64_t zero_wall_tt_misses()const{return zero_wall_tt_misses_;}
    uint64_t zero_wall_bypassed()const{return zero_wall_bypassed_;}
    uint64_t zero_wall_builds()const{return zero_wall_builds_;}
    uint64_t zero_wall_edges()const{return zero_wall_edges_;}
    uint64_t zero_wall_ranked()const{return zero_wall_ranked_;}
    double zero_wall_build_seconds()const{return zero_wall_build_seconds_;}
    size_t zero_wall_table_bytes()const{
        size_t bytes=0;
        for(const auto&table:zero_wall_tables_)if(table){bytes+=sizeof(ZeroWallTablebase);for(const auto&r:table->rank)bytes+=r.capacity()*sizeof(uint16_t);}
        return bytes;
    }
#endif
    void resolve_state(State&s){if(s.cfg_id==UINT32_MAX){
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        if(s.deferred_ref==UINT32_MAX)throw std::runtime_error("unresolved local-touch state has no parent handle");
        uint32_t parent=s.deferred_ref>>6;int wall=int(s.deferred_ref&63u);
        if(parent>=PENDING_TRANSITION_ID||wall<0||wall>=2*S)throw std::runtime_error("invalid local-touch parent handle");
#ifndef NDEBUG
        uint64_t parent_mask=s.walls_mask&~(1ULL<<wall);
        if(cache_index_.find(parent_mask)!=parent)throw std::runtime_error("local-touch handle does not match its parent wall mask");
#endif
        size_t before=cache_data_.size();
        s.cfg_id=ensure_child_config(s.walls_mask,parent,wall);
        if(cache_data_.size()==before)++local_touch_resolve_hits_;else ++local_touch_resolve_builds_;
        s.deferred_ref=UINT32_MAX;
#else
        s.cfg_id=ensure_config(s.walls_mask);
#endif
        ++deferred_resolved_;}}
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
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
        auto probe=cache_index_.probe(mask);uint32_t found=probe.value;
#else
        uint32_t found=cache_index_.find(mask);
#endif
        if(found!=UINT32_MAX){++cache_hits_;return found;}
        ++cache_misses_;
        uint32_t idx=uint32_t(cache_data_.size());
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        if(idx>=PENDING_TRANSITION_ID)throw std::runtime_error("configuration id reaches reserved local-touch transition sentinel");
#endif
        cache_data_.push_back(build_config(mask));
        if(profile_cycle_gate_||defer_cycle_safe_)junction_components_.push_back(build_junction_components(mask));
        transition_offsets_.push_back(UINT32_MAX);transition_counts_.push_back(0);transition_expansions_.push_back(0);
        if(profile_visits_)node_visits_.push_back(0);
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        zero_wall_visits_.push_back(0);zero_wall_tables_.push_back(nullptr);
#endif
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
        cache_index_.insert_at_miss(mask,idx,probe);
#else
        cache_index_.insert(mask,idx);
#endif
        return idx;
    }
    uint32_t ensure_child_config(uint64_t mask,uint32_t parent_id,int wall) {
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
        auto probe=cache_index_.probe(mask);uint32_t found=probe.value;
#else
        uint32_t found=cache_index_.find(mask);
#endif
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
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        if(idx>=PENDING_TRANSITION_ID)throw std::runtime_error("configuration id reaches reserved local-touch transition sentinel");
#endif
        cache_data_.push_back(child);
        if(profile_cycle_gate_||defer_cycle_safe_){auto jc=junction_components_[parent_id];merge_wall_components(jc,wall);junction_components_.push_back(jc);}
        transition_offsets_.push_back(UINT32_MAX);transition_counts_.push_back(0);transition_expansions_.push_back(0);
        if(profile_visits_) node_visits_.push_back(0);
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        zero_wall_visits_.push_back(0);zero_wall_tables_.push_back(nullptr);
#endif
#ifdef QSPEC_MASK_INDEX_PROBE_EXPERIMENT
        cache_index_.insert_at_miss(mask,idx,probe);
#else
        cache_index_.insert(mask,idx);
#endif
        return idx;
    }
    void build_transition_cache(const State&s,uint64_t adds){
        std::vector<uint32_t> local;
        local.reserve(std::popcount(adds));
        uint64_t todo=adds;
        while(todo){int w=std::countr_zero(todo);todo&=todo-1;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
            uint64_t nm=s.walls_mask|(1ULL<<w);
            uint32_t id=cache_index_.find(nm);
            if(id!=UINT32_MAX){++cache_hits_;++local_touch_exact_hits_;}
            else{classify_cycle_gate(s.cfg_id,w);if(local_touch_safe(s.walls_mask,w)){++local_touch_safe_misses_;id=PENDING_TRANSITION_ID;}
            else{++local_touch_fallback_misses_;id=ensure_child_config(nm,s.cfg_id,w);}}
            if(id>PENDING_TRANSITION_ID)throw std::runtime_error("transition child id exceeds packed local-touch range");
#else
            classify_cycle_gate(s.cfg_id,w);uint64_t nm=s.walls_mask|(1ULL<<w);
            uint32_t id=ensure_child_config(nm,s.cfg_id,w);if(id>=(1u<<26))throw std::runtime_error("transition child id exceeds packed range");
#endif
            local.push_back((id<<6)|uint32_t(w));}
        if(transition_entries_.size()+local.size()>UINT32_MAX)throw std::runtime_error("transition cache offset overflow");
        transition_offsets_[s.cfg_id]=uint32_t(transition_entries_.size());
        transition_counts_[s.cfg_id]=uint16_t(local.size());
        transition_entries_.insert(transition_entries_.end(),local.begin(),local.end());
        ++transition_builds_;
    }
    const ConfigData& config_by_id(uint32_t id) const {
#if defined(QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT) && !defined(NDEBUG)
        if(id==UINT32_MAX||id>=cache_data_.size())throw std::runtime_error("configuration access on unresolved or invalid local-touch state");
#endif
        return cache_data_[id];
    }

    struct Child{State s;int score;uint16_t move;};

#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    void record_pruned_handles(const Child*children,int count){
        for(int i=0;i<count;i++)if(children[i].s.cfg_id==UINT32_MAX){
            ++local_touch_pruned_;
            if(cache_index_.find(children[i].s.walls_mask)==UINT32_MAX)++local_touch_pruned_uncached_;
        }
    }
#endif

    int shortest_options(const State&s,int player,const ConfigData&cd)const{
        uint8_t p=s.p[player];int d=player==0?cd.dist0[p]:cd.dist1[p];if(d<=0||d>=255)return 0;int n=0;
        for(int dir=0;dir<4;dir++)if((cd.dir[dir]>>p)&1u){uint8_t q=neigh[p][dir];if(q==255)continue;int dq=player==0?cd.dist0[q]:cd.dist1[q];n+=dq+1==d;}
        return n;
    }


    static uint64_t flow_sat_add(uint64_t a,uint64_t b){
        static constexpr uint64_t CAP=uint64_t(1)<<50;
        return a>=CAP-b?CAP:a+b;
    }
    static uint64_t flow_sat_mul(uint64_t a,uint64_t b){
        static constexpr uint64_t CAP=uint64_t(1)<<50;
        if(!a||!b)return 0;
        if(a>=CAP/b)return CAP;
        return a*b;
    }

    std::array<uint16_t,40> compute_path_flow_impacts(int player,uint8_t start,const ConfigData&cd)const{
        std::array<uint16_t,40> result{};
        const auto&goal=player==0?cd.dist0:cd.dist1;
        int total=goal[start];
        if(total<=0||total>=255)return result;
        auto from=distances_from(start,cd);
        std::array<uint64_t,32> forward{},backward{};
        forward[start]=1;
        for(int level=0;level<total;level++)for(int p=0;p<N;p++){
            if(from[p]!=level||int(from[p])+int(goal[p])!=total||!forward[p])continue;
            for(int dir=0;dir<4;dir++)if((cd.dir[dir]>>p)&1u){uint8_t q=neigh[p][dir];if(q!=255&&from[q]==level+1&&int(from[q])+int(goal[q])==total)forward[q]=flow_sat_add(forward[q],forward[p]);}
        }
        for(int level=total;level>=0;level--)for(int p=0;p<N;p++){
            if(from[p]!=level||int(from[p])+int(goal[p])!=total)continue;
            if(goal[p]==0){backward[p]=1;continue;}
            uint64_t sum=0;
            for(int dir=0;dir<4;dir++)if((cd.dir[dir]>>p)&1u){uint8_t q=neigh[p][dir];if(q!=255&&from[q]==level+1&&int(from[q])+int(goal[q])==total)sum=flow_sat_add(sum,backward[q]);}
            backward[p]=sum;
        }
        uint64_t paths=backward[start];if(!paths)return result;
        std::array<uint64_t,40> blocked{};
        for(int p=0;p<N;p++){
            if(from[p]==255||int(from[p])+int(goal[p])!=total||!forward[p])continue;
            for(int dir=0;dir<4;dir++)if((cd.dir[dir]>>p)&1u){
                uint8_t q=neigh[p][dir];if(q==255||from[q]!=from[p]+1||int(from[q])+int(goal[q])!=total||!backward[q])continue;
                uint64_t contribution=flow_sat_mul(forward[p],backward[q]);
                uint64_t walls=edge_walls_[p][dir];while(walls){int w=std::countr_zero(walls);walls&=walls-1;blocked[w]=flow_sat_add(blocked[w],contribution);}
            }
        }
        for(int w=0;w<2*S;w++){
            uint64_t numerator=std::min(paths,blocked[w]);
            result[w]=uint16_t((numerator*1000)/paths);
        }
        return result;
    }

    const std::array<uint16_t,40>& path_flow_impacts(uint32_t cfg,int player,uint8_t start,const ConfigData&cd){
        uint64_t raw=(uint64_t(cfg)<<7)|(uint64_t(player)<<6)|uint64_t(start);uint64_t key=raw+1;
        FlowCacheEntry&entry=flow_cache_[size_t(mix64(raw))&flow_cache_mask_];
        if(entry.key==key){++flow_cache_hits_;return entry.impact;}
        ++flow_cache_misses_;entry.key=key;entry.impact=compute_path_flow_impacts(player,start,cd);return entry.impact;
    }

    std::array<uint8_t,32> distances_from(uint8_t start,const ConfigData&cd)const{
        std::array<uint8_t,32>d{};d.fill(255);std::array<uint8_t,32>q{};int head=0,tail=0;d[start]=0;q[tail++]=start;
        while(head<tail){uint8_t p=q[head++];for(int dir=0;dir<4;dir++)if((cd.dir[dir]>>p)&1u){uint8_t z=neigh[p][dir];if(z!=255&&d[z]==255){d[z]=uint8_t(d[p]+1);q[tail++]=z;}}}
        return d;
    }

    int shortest_edges_blocked(int player,uint8_t start,int wall,const std::array<uint8_t,32>&from,const ConfigData&cd)const{
        const auto&goal=player==0?cd.dist0:cd.dist1;int total=goal[start];if(total<=0||total>=255)return 0;int count=0;
        for(int dir=0;dir<4;dir++){
            uint32_t bits=wall_block_[wall][dir];
            while(bits){int p=std::countr_zero(bits);bits&=bits-1;uint8_t z=neigh[p][dir];if(z==255||from[p]==255||goal[z]==255)continue;
                if(int(from[p])+1+int(goal[z])==total)++count;
            }
        }
        return count;
    }

    int immediate_shortest_edges_blocked(int player,uint8_t start,int wall,const ConfigData&cd)const{
        const auto&goal=player==0?cd.dist0:cd.dist1;int total=goal[start];if(total<=0||total>=255)return 0;int count=0;
        for(int dir=0;dir<4;dir++)if((wall_block_[wall][dir]>>start)&1u){uint8_t z=neigh[start][dir];if(z!=255&&goal[z]+1==total)++count;}
        return count;
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
#if defined(QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT) && !defined(NDEBUG)
        if(s.cfg_id==UINT32_MAX)throw std::runtime_error("move generation on unresolved local-touch state");
#endif
        Player win;if(terminal(s,win))return 0;
        int nout=0,me=int(s.turn),op=1-me;
        uint8_t mp=s.p[me],opp=s.p[op];
        // Child materialisation may grow cache_data_. Keep a local parent copy so
        // later scoring never depends on a vector reference surviving reallocation.
        const ConfigData current=config_by_id(s.cfg_id);
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
            std::array<uint8_t,32> from_me{},from_op{};
            int options_me=0,options_op=0;
            std::array<uint16_t,40> flow_me{},flow_op{};
            if(path_flow_weight){flow_me=path_flow_impacts(s.cfg_id,me,s.p[me],current);flow_op=path_flow_impacts(s.cfg_id,op,s.p[op],current);}
            int deferred_base_score=0;
#ifndef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
            if(defer_cycle_safe_){
                from_me=distances_from(s.p[me],current);from_op=distances_from(s.p[op],current);options_me=shortest_options(s,me,current);options_op=shortest_options(s,op,current);
                State base=s;--base.walls[me];base.turn=other(s.turn);deferred_base_score=static_eval_data(base,target,current);
            }
            auto emit_wall=[&](int w,uint32_t nid){
                const auto&nx=config_by_id(nid);
                if(nx.dist0[s.p[0]]==255||nx.dist1[s.p[1]]==255)return;
                State t=s;t.walls_mask=s.walls_mask|(1ULL<<w);t.cfg_id=nid;--t.walls[me];t.turn=other(s.turn);
                int sc=static_eval_data(t,target,nx);
                int after_op=(op==0?nx.dist0[s.p[op]]:nx.dist1[s.p[op]]);
                int after_me=(me==0?nx.dist0[s.p[me]]:nx.dist1[s.p[me]]);
                int tactical=(after_op-before_op)*80-(after_me-before_me)*55;
                if(path_flow_weight)tactical+=(int(flow_op[w])-int(flow_me[w]))*path_flow_weight;
                if(me!=int(target))tactical=-tactical;
                out[nout++]={t,sc+(order_mode==0?0:tactical),uint16_t(0x100u+w)};
            };
            auto emit_deferred_wall=[&](int w){
                State t=s;t.walls_mask=s.walls_mask|(1ULL<<w);t.cfg_id=UINT32_MAX;--t.walls[me];t.turn=other(s.turn);
                int sc=deferred_base_score;
                int impact_op=shortest_edges_blocked(op,s.p[op],w,from_op,current);
                int impact_me=shortest_edges_blocked(me,s.p[me],w,from_me,current);
                int immediate_op=immediate_shortest_edges_blocked(op,s.p[op],w,current);
                int immediate_me=immediate_shortest_edges_blocked(me,s.p[me],w,current);
                int tactical=impact_op*16-impact_me*12;
                if(options_op>0&&immediate_op>=options_op)tactical+=180;
                if(options_me>0&&immediate_me>=options_me)tactical-=150;
                if(me!=int(target))tactical=-tactical;
                if(order_mode!=0)sc+=tactical;
                out[nout++]={t,sc,uint16_t(0x100u+w)};++deferred_emitted_;
            };
            bool cached=transition_offsets_[s.cfg_id]!=UINT32_MAX;
            if(!cached&&transition_threshold_>0){uint16_t&exp=transition_expansions_[s.cfg_id];if(exp!=UINT16_MAX)++exp;if(exp>=transition_threshold_){build_transition_cache(s,adds);cached=true;}}
            if(cached){++transition_hits_;uint32_t off=transition_offsets_[s.cfg_id];uint16_t cnt=transition_counts_[s.cfg_id];for(uint16_t i=0;i<cnt;i++){uint32_t packed=transition_entries_[off+i];emit_wall(int(packed&63u),packed>>6);}}
            else while(adds){
                int w=std::countr_zero(adds);adds&=adds-1;
                bool gate_safe=classify_cycle_gate(s.cfg_id,w);
                if(defer_cycle_safe_&&gate_safe)emit_deferred_wall(w);
                else{uint64_t nm=s.walls_mask|(1ULL<<w);uint32_t nid=ensure_child_config(nm,s.cfg_id,w);emit_wall(w,nid);}
            }
#else
            bool deferred_proxy_ready=false;
            auto ensure_deferred_proxy=[&](){if(!deferred_proxy_ready){
                from_me=distances_from(s.p[me],current);from_op=distances_from(s.p[op],current);options_me=shortest_options(s,me,current);options_op=shortest_options(s,op,current);
                State base=s;--base.walls[me];base.turn=other(s.turn);deferred_base_score=static_eval_data(base,target,current);deferred_proxy_ready=true;
            }};
            auto make_wall=[&](int w,uint32_t nid,Child&child)->bool{
                const auto&nx=config_by_id(nid);
                if(nx.dist0[s.p[0]]==255||nx.dist1[s.p[1]]==255)return false;
                State t=s;t.walls_mask=s.walls_mask|(1ULL<<w);t.cfg_id=nid;--t.walls[me];t.turn=other(s.turn);
                int sc=static_eval_data(t,target,nx);
                int after_op=(op==0?nx.dist0[s.p[op]]:nx.dist1[s.p[op]]);
                int after_me=(me==0?nx.dist0[s.p[me]]:nx.dist1[s.p[me]]);
                int tactical=(after_op-before_op)*80-(after_me-before_me)*55;
                if(path_flow_weight)tactical+=(int(flow_op[w])-int(flow_me[w]))*path_flow_weight;
                if(me!=int(target))tactical=-tactical;
                child={t,sc+(order_mode==0?0:tactical),uint16_t(0x100u+w)};
                return true;
            };
            auto emit_wall=[&](int w,uint32_t nid){Child child{};if(make_wall(w,nid,child))out[nout++]=child;};
            auto emit_deferred_wall=[&](int w){
                ensure_deferred_proxy();
                State t=s;t.walls_mask=s.walls_mask|(1ULL<<w);t.cfg_id=UINT32_MAX;--t.walls[me];t.turn=other(s.turn);
                if(s.cfg_id>=PENDING_TRANSITION_ID)throw std::runtime_error("local-touch parent id exceeds packed handle range");
                t.deferred_ref=(s.cfg_id<<6)|uint32_t(w);
                int sc=deferred_base_score;
                int impact_op=shortest_edges_blocked(op,s.p[op],w,from_op,current);
                int impact_me=shortest_edges_blocked(me,s.p[me],w,from_me,current);
                int immediate_op=immediate_shortest_edges_blocked(op,s.p[op],w,current);
                int immediate_me=immediate_shortest_edges_blocked(me,s.p[me],w,current);
                int tactical=impact_op*16-impact_me*12;
                if(options_op>0&&immediate_op>=options_op)tactical+=180;
                if(options_me>0&&immediate_me>=options_me)tactical-=150;
                if(path_flow_weight)tactical+=(int(flow_op[w])-int(flow_me[w]))*path_flow_weight;
                if(me!=int(target))tactical=-tactical;
                if(order_mode!=0)sc+=tactical;
                out[nout++]={t,sc,uint16_t(0x100u+w)};++deferred_emitted_;
            };
            bool cached=transition_offsets_[s.cfg_id]!=UINT32_MAX;
            if(!cached&&transition_threshold_>0){uint16_t&exp=transition_expansions_[s.cfg_id];if(exp!=UINT16_MAX)++exp;if(exp>=transition_threshold_){build_transition_cache(s,adds);cached=true;}}
            if(cached){++transition_hits_;uint32_t off=transition_offsets_[s.cfg_id];uint16_t cnt=transition_counts_[s.cfg_id];for(uint16_t i=0;i<cnt;i++){
                uint32_t&packed=transition_entries_[off+i];int w=int(packed&63u);uint32_t id=packed>>6;
                if(id==PENDING_TRANSITION_ID){
                    ++local_touch_pending_replayed_;uint64_t nm=s.walls_mask|(1ULL<<w);uint32_t found=cache_index_.find(nm);
                    if(found!=UINT32_MAX){++cache_hits_;++local_touch_pending_patched_;packed=(found<<6)|uint32_t(w);emit_wall(w,found);}
                    else emit_deferred_wall(w);
                }else emit_wall(w,id);
            }}
            else while(adds){
                int w=std::countr_zero(adds);adds&=adds-1;uint64_t nm=s.walls_mask|(1ULL<<w);uint32_t found=cache_index_.find(nm);
                if(found!=UINT32_MAX){++cache_hits_;++local_touch_exact_hits_;emit_wall(w,found);}
                else{classify_cycle_gate(s.cfg_id,w);if(local_touch_safe(s.walls_mask,w)){++local_touch_safe_misses_;emit_deferred_wall(w);}
                else{++local_touch_fallback_misses_;uint32_t nid=ensure_child_config(nm,s.cfg_id,w);emit_wall(w,nid);}}
            }
            if(ordered&&local_touch_refine_!=0&&nout>1){
                bool desc=s.turn==target;
                // Rank proxy scores through indices.  Do not permute the child
                // array before exact rescoring: doing so would change the stable
                // tie order of the final sort, even for K=all.
                std::array<uint16_t,192> proxy_rank{};for(int i=0;i<nout;i++)proxy_rank[i]=uint16_t(i);
                for(int i=1;i<nout;i++){uint16_t x=proxy_rank[i];int j=i;while(j>0&&(desc?out[proxy_rank[j-1]].score<out[x].score:out[proxy_rank[j-1]].score>out[x].score)){proxy_rank[j]=proxy_rank[j-1];--j;}proxy_rank[j]=x;}
                std::array<uint16_t,192> proxy_order{};for(int i=0;i<nout;i++)proxy_order[i]=out[proxy_rank[i]].move;
                int left=local_touch_refine_<0?std::numeric_limits<int>::max():local_touch_refine_;
                for(int rank=0;rank<nout&&left>0;rank++){int i=proxy_rank[rank];if(out[i].s.cfg_id==UINT32_MAX){
                    int w=int(out[i].move-0x100u);State resolved=out[i].s;resolve_state(resolved);Child exact{};
                    if(!make_wall(w,resolved.cfg_id,exact))throw std::runtime_error("local-touch safe handle failed exact path legality");
                    out[i]=exact;++local_touch_refined_;--left;
                }}
                for(int i=1;i<nout;i++){Child x=out[i];int j=i;while(j>0&&(desc?out[j-1].score<x.score:out[j-1].score>x.score)){out[j]=out[j-1];--j;}out[j]=x;}
                bool changed=false;for(int i=0;i<nout;i++)changed|=proxy_order[i]!=out[i].move;if(changed)++local_touch_refine_order_changes_;
            }
#endif
        }
        if(ordered&&nout>1){bool desc=s.turn==target;for(int i=1;i<nout;i++){Child x=out[i];int j=i;while(j>0&&(desc?out[j-1].score<x.score:out[j-1].score>x.score)){out[j]=out[j-1];--j;}out[j]=x;}}
        return nout;
    }

#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
    bool try_legal_move(const State&s,uint16_t move,Child&child){
        Player winner;if(terminal(s,winner))return false;
        int me=int(s.turn),op=1-me;uint8_t mp=s.p[me],opp=s.p[op];
        const ConfigData&current=config_by_id(s.cfg_id);
        auto clear_at=[&](uint8_t p){return uint8_t(((current.dir[0]>>p)&1u)|(((current.dir[1]>>p)&1u)<<1)|(((current.dir[2]>>p)&1u)<<2)|(((current.dir[3]>>p)&1u)<<3));};
        if(move<0x100u){
            if(move>=uint16_t(N)||move==opp)return false;
            uint8_t cd=clear_at(mp);static constexpr int perpA[4]={2,2,0,0};static constexpr int perpB[4]={3,3,1,1};
            for(int d=0;d<4;d++)if(cd&(1u<<d)){
                uint8_t q=neigh[mp][d];if(q==255)continue;
                if(q!=opp){if(q==move){State t=s;t.p[me]=q;t.turn=other(s.turn);child={t,0,move};return true;}}
                else{
                    uint8_t od=clear_at(opp);
                    if(od&(1u<<d)){uint8_t z=neigh[opp][d];if(z==move){State t=s;t.p[me]=z;t.turn=other(s.turn);child={t,0,move};return true;}}
                    else for(int pd:{perpA[d],perpB[d]})if(od&(1u<<pd)){uint8_t z=neigh[opp][pd];if(z==move){State t=s;t.p[me]=z;t.turn=other(s.turn);child={t,0,move};return true;}}
                }
            }
            return false;
        }
        int wall=int(move)-0x100;if(wall<0||wall>=2*S||s.walls[me]==0||((current.legal_add>>wall)&1ULL)==0)return false;
        uint64_t mask=s.walls_mask|(1ULL<<wall);uint32_t id=ensure_child_config(mask,s.cfg_id,wall);const ConfigData&next=config_by_id(id);
        if(next.dist0[s.p[0]]==255||next.dist1[s.p[1]]==255)return false;
        State t=s;t.walls_mask=mask;t.cfg_id=id;--t.walls[me];t.turn=other(s.turn);child={t,0,move};return true;
    }
#endif

#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    bool zero_wall_tablebase_probe(const State&s,Player target,int depth,bool build_on_miss,bool&result){
        if(s.walls[0]!=0||s.walls[1]!=0)return false;
        if(s.cfg_id>=zero_wall_tables_.size())throw std::runtime_error("zero-wall tablebase configuration index out of range");
        auto&table=zero_wall_tables_[s.cfg_id];
        if(!build_on_miss)++zero_wall_queries_;
        if(table){
            size_t i=zero_wall_index(s.turn,s.p[0],s.p[1]);
            uint16_t rank=table->rank[int(target)][i];
            result=rank!=ZERO_WALL_UNKNOWN&&int(rank)<=depth;
            ++zero_wall_hits_;return true;
        }
        if(!build_on_miss)return false;
        ++zero_wall_tt_misses_;
        if(zero_wall_threshold_<=0){++zero_wall_bypassed_;return false;}
        uint32_t&visits=zero_wall_visits_[s.cfg_id];
        if(visits!=UINT32_MAX)++visits;
        if(int(visits)<zero_wall_threshold_||int(zero_wall_builds_)>=zero_wall_max_){
            ++zero_wall_bypassed_;return false;
        }
        auto t0=Clock::now();
        table=build_zero_wall_tablebase(s.cfg_id,s.walls_mask);
        zero_wall_build_seconds_+=std::chrono::duration<double>(Clock::now()-t0).count();
        ++zero_wall_builds_;zero_wall_edges_+=table->edges;zero_wall_ranked_+=table->ranked;
        size_t i=zero_wall_index(s.turn,s.p[0],s.p[1]);
        uint16_t rank=table->rank[int(target)][i];
        result=rank!=ZERO_WALL_UNKNOWN&&int(rank)<=depth;
        ++zero_wall_hits_;
        return true;
    }
#endif

    bool structurally_saturated(uint64_t mask){return config_by_id(ensure_config(mask)).legal_add==0;}

    uint64_t transform_lut(uint64_t m,const std::array<std::array<uint64_t,1024>,4>&lut)const{
        return lut[0][m&1023ULL]|lut[1][(m>>10)&1023ULL]|lut[2][(m>>20)&1023ULL]|lut[3][(m>>30)&1023ULL];
    }

    uint64_t canonical_key(const State&s,Player target,int depth,bool cap_stocks)const{
#if defined(QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT) && !defined(NDEBUG)
        if(s.cfg_id==UINT32_MAX)throw std::runtime_error("canonical key requested for unresolved local-touch state");
#endif
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

#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
    std::pair<uint64_t,uint8_t> canonical_key_with_transform(const State&s,Player target,int depth,bool cap_stocks)const{
        auto pack=[&](uint64_t mask,uint8_t p0,uint8_t p1,uint8_t w0,uint8_t w1,Player turn,Player tar){uint64_t x=mask;x=(x<<6)|p0;x=(x<<6)|p1;x=(x<<5)|w0;x=(x<<5)|w1;x=(x<<1)|uint64_t(turn);x=(x<<1)|uint64_t(tar);return x+1;};
        uint8_t w0=s.walls[0],w1=s.walls[1];
        if(cap_stocks){int first=(depth+1)/2,second=depth/2;int turns0=s.turn==P1?first:second;int turns1=s.turn==P2?first:second;w0=uint8_t(std::min<int>(w0,turns0));w1=uint8_t(std::min<int>(w1,turns1));}
        if(symmetry_mode==0)return {pack(s.walls_mask,s.p[0],s.p[1],w0,w1,s.turn,target),0};
        if(symmetry_mode==1){
            uint64_t a=pack(s.walls_mask,s.p[0],s.p[1],w0,w1,s.turn,target);
            uint64_t mm=transform_lut(s.walls_mask,mirror_lut_);
            uint64_t b=pack(mm,mirror_sq[s.p[0]],mirror_sq[s.p[1]],w0,w1,s.turn,target);
            return b<a?std::pair<uint64_t,uint8_t>{b,1}:std::pair<uint64_t,uint8_t>{a,0};
        }
        const ConfigData&cd=config_by_id(s.cfg_id);uint64_t best=std::numeric_limits<uint64_t>::max();uint8_t transform=0;
        auto consider=[&](uint64_t value,uint8_t candidate){if(value<best){best=value;transform=candidate;}};
        uint8_t xs=cd.canonical_xforms;
        if(xs&1u)consider(pack(cd.canonical_wall,s.p[0],s.p[1],w0,w1,s.turn,target),0);
        if(xs&2u)consider(pack(cd.canonical_wall,mirror_sq[s.p[0]],mirror_sq[s.p[1]],w0,w1,s.turn,target),1);
        if(xs&4u)consider(pack(cd.canonical_wall,rotate_sq[s.p[1]],rotate_sq[s.p[0]],w1,w0,other(s.turn),other(target)),2);
        if(xs&8u)consider(pack(cd.canonical_wall,mirror_sq[rotate_sq[s.p[1]]],mirror_sq[rotate_sq[s.p[0]]],w1,w0,other(s.turn),other(target)),3);
        return {best,transform};
    }
    uint16_t transform_move(uint16_t move,uint8_t transform)const{
        if(move==0xffff||transform==0)return move;
        if(move<0x100u){if(move>=uint16_t(N))throw std::runtime_error("TT hint pawn move outside board");if(transform==1)return mirror_sq[move];if(transform==2)return rotate_sq[move];if(transform==3)return mirror_sq[rotate_sq[move]];throw std::runtime_error("invalid TT hint transform");}
        int wall=int(move)-0x100;if(wall<0||wall>=2*S)throw std::runtime_error("TT hint wall move outside board");int ori=wall/S,z=wall%S,r=z/C,c=z%C;
        if(transform==1)c=C-1-c;else if(transform==2){r=R-1-r;c=C-1-c;}else if(transform==3)r=R-1-r;else throw std::runtime_error("invalid TT hint transform");
        return uint16_t(0x100+ori*S+slot(r,c));
    }
#endif

private:
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    size_t zero_wall_index(Player turn,uint8_t p0,uint8_t p1)const{return (size_t(turn)*size_t(N)+p0)*size_t(N)+p1;}
    std::unique_ptr<ZeroWallTablebase> build_zero_wall_tablebase(uint32_t cfg,uint64_t mask){
        const size_t states=size_t(2)*size_t(N)*size_t(N);
        if(states>=size_t(ZERO_WALL_UNKNOWN))throw std::runtime_error("zero-wall tablebase state index exceeds uint16 range");
        auto table=std::make_unique<ZeroWallTablebase>();
        std::vector<std::vector<uint16_t>> predecessors(states);
#ifndef NDEBUG
        std::vector<std::vector<uint16_t>> successors(states);
#endif
        std::vector<uint8_t> outdegree(states,0);
        std::array<Child,192> children{};
        for(Player turn:{P1,P2})for(int p0=0;p0<N;p0++)for(int p1=0;p1<N;p1++){
            if(p0==p1)continue;
            State s;s.walls_mask=mask;s.cfg_id=cfg;s.p[0]=uint8_t(p0);s.p[1]=uint8_t(p1);s.turn=turn;
            Player winner;if(terminal(s,winner))continue;
            int n=generate(s,P1,children.data(),false);
            if(n<0||n>255)throw std::runtime_error("zero-wall tablebase outdegree exceeds uint8 range");
            size_t from=zero_wall_index(turn,uint8_t(p0),uint8_t(p1));outdegree[from]=uint8_t(n);
            for(int k=0;k<n;k++){
                const State&t=children[k].s;
                if(t.cfg_id!=cfg||t.walls_mask!=mask||t.walls[0]!=0||t.walls[1]!=0||t.p[0]==t.p[1])throw std::runtime_error("zero-wall tablebase generated an invalid successor");
                size_t to=zero_wall_index(t.turn,t.p[0],t.p[1]);
                predecessors[to].push_back(uint16_t(from));++table->edges;
#ifndef NDEBUG
                successors[from].push_back(uint16_t(to));
#endif
            }
        }
        for(Player target:{P1,P2}){
            auto&rank=table->rank[int(target)];rank.assign(states,ZERO_WALL_UNKNOWN);
            std::vector<uint8_t> remaining=outdegree;
            std::vector<uint16_t> max_child_rank(states,0);
            std::deque<uint16_t> queue;
            for(Player turn:{P1,P2})for(int p0=0;p0<N;p0++)for(int p1=0;p1<N;p1++){
                if(p0==p1)continue;
                State s;s.walls_mask=mask;s.cfg_id=cfg;s.p[0]=uint8_t(p0);s.p[1]=uint8_t(p1);s.turn=turn;
                Player winner;if(terminal(s,winner)&&winner==target){size_t i=zero_wall_index(turn,uint8_t(p0),uint8_t(p1));rank[i]=0;queue.push_back(uint16_t(i));++table->ranked;}
            }
            while(!queue.empty()){
                uint16_t child=queue.front();queue.pop_front();uint16_t child_rank=rank[child];
                for(uint16_t parent:predecessors[child]){
                    if(rank[parent]!=ZERO_WALL_UNKNOWN)continue;
                    Player parent_turn=Player(parent/(N*N));
                    if(parent_turn==target){
                        rank[parent]=uint16_t(child_rank+1);queue.push_back(parent);++table->ranked;
                    }else{
                        if(remaining[parent]==0)continue;
                        --remaining[parent];max_child_rank[parent]=std::max(max_child_rank[parent],child_rank);
                        if(remaining[parent]==0&&outdegree[parent]>0){rank[parent]=uint16_t(max_child_rank[parent]+1);queue.push_back(parent);++table->ranked;}
                    }
                }
            }
#ifndef NDEBUG
            for(Player turn:{P1,P2})for(int p0=0;p0<N;p0++)for(int p1=0;p1<N;p1++){
                if(p0==p1)continue;
                State s;s.walls_mask=mask;s.cfg_id=cfg;s.p[0]=uint8_t(p0);s.p[1]=uint8_t(p1);s.turn=turn;
                size_t i=zero_wall_index(turn,uint8_t(p0),uint8_t(p1));Player winner;
                uint16_t expected=ZERO_WALL_UNKNOWN;
                if(terminal(s,winner)){if(winner==target)expected=0;}
                else if(turn==target){
                    uint16_t best=ZERO_WALL_UNKNOWN;
                    for(uint16_t child:successors[i])if(rank[child]!=ZERO_WALL_UNKNOWN)best=std::min(best,uint16_t(rank[child]+1));
                    expected=best;
                }else if(!successors[i].empty()){
                    uint16_t worst=0;bool all=true;
                    for(uint16_t child:successors[i]){if(rank[child]==ZERO_WALL_UNKNOWN){all=false;break;}worst=std::max(worst,uint16_t(rank[child]+1));}
                    if(all)expected=worst;
                }
                if(rank[i]!=expected)throw std::runtime_error("zero-wall tablebase Bellman validation failed");
                if(rank[i]!=ZERO_WALL_UNKNOWN&&rank[i]>=states)throw std::runtime_error("zero-wall tablebase rank exceeds finite-state bound");
            }
#endif
        }
        return table;
    }
#endif
    static uint8_t component_find(std::array<uint8_t,64>&p,uint8_t x){while(p[x]!=x){p[x]=p[p[x]];x=p[x];}return x;}
    static void component_union(std::array<uint8_t,64>&p,uint8_t a,uint8_t b){a=component_find(p,a);b=component_find(p,b);if(a!=b)p[b]=a;}
    std::array<uint8_t,64> build_junction_components(uint64_t mask)const{
        std::array<uint8_t,64> p{};for(int i=0;i<junction_count_;i++)p[i]=uint8_t(i);
        int boundary=-1;
        for(int r=0;r<=H;r++)for(int c=0;c<=W;c++)if(r==0||r==H||c==0||c==W){int j=r*junction_width_+c;if(boundary<0)boundary=j;else component_union(p,uint8_t(boundary),uint8_t(j));}
        uint64_t todo=mask;while(todo){int w=std::countr_zero(todo);todo&=todo-1;auto j=wall_junctions_[w];component_union(p,j[0],j[1]);component_union(p,j[1],j[2]);}
        for(int i=0;i<junction_count_;i++)p[i]=component_find(p,uint8_t(i));
        return p;
    }
    void merge_wall_components(std::array<uint8_t,64>&labels,int wall)const{
        auto j=wall_junctions_[wall];uint8_t a=labels[j[0]],b=labels[j[1]],c=labels[j[2]];uint8_t keep=std::min({a,b,c});
        for(int i=0;i<junction_count_;i++)if(labels[i]==a||labels[i]==b||labels[i]==c)labels[i]=keep;
    }
    bool cycle_gate_safe_for(uint32_t cfg,int wall)const{
        const auto&labels=junction_components_[cfg];auto j=wall_junctions_[wall];uint8_t a=labels[j[0]],b=labels[j[1]],c=labels[j[2]];return a!=b&&a!=c&&b!=c;
    }
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    bool local_touch_safe(uint64_t mask,int wall)const{
        auto js=wall_junctions_[wall];int touched=0;
        for(uint8_t j:js){
            bool boundary=((boundary_junctions_>>j)&1ULL)!=0;
            bool incident=(junction_incident_walls_[j]&mask)!=0;
            touched+=boundary||incident;
        }
        return touched<=1;
    }
#endif
    bool classify_cycle_gate(uint32_t cfg,int wall){
        if(!profile_cycle_gate_&&!defer_cycle_safe_)return false;
        bool safe=cycle_gate_safe_for(cfg,wall);if(safe)++cycle_gate_safe_;else ++cycle_gate_fallback_;return safe;
    }
    void init_geometry(){
        junction_width_=W+1;junction_count_=(W+1)*(H+1);if(junction_count_>64)throw std::runtime_error("junction graph exceeds 64 vertices");
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
            wall_junctions_[h]={uint8_t((r+1)*junction_width_+c),uint8_t((r+1)*junction_width_+c+1),uint8_t((r+1)*junction_width_+c+2)};
            wall_junctions_[v]={uint8_t(r*junction_width_+c+1),uint8_t((r+1)*junction_width_+c+1),uint8_t((r+2)*junction_width_+c+1)};
            wall_block_[h][1]|=(1u<<sq(r,c))|(1u<<sq(r,c+1));
            wall_block_[h][0]|=(1u<<sq(r+1,c))|(1u<<sq(r+1,c+1));
            wall_block_[v][3]|=(1u<<sq(r,c))|(1u<<sq(r+1,c));
            wall_block_[v][2]|=(1u<<sq(r,c+1))|(1u<<sq(r+1,c+1));
        }
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        for(int r=0;r<=H;r++)for(int c=0;c<=W;c++)if(r==0||r==H||c==0||c==W)boundary_junctions_|=1ULL<<(r*junction_width_+c);
        for(int w=0;w<2*S;w++)for(uint8_t j:wall_junctions_[w])junction_incident_walls_[j]|=1ULL<<w;
#endif
        for(int w=0;w<2*S;w++)for(int d=0;d<4;d++){uint32_t bits=wall_block_[w][d];while(bits){int p=std::countr_zero(bits);bits&=bits-1;edge_walls_[p][d]|=uint64_t(1)<<w;}}
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
    LazyEngine&e;TransTable tt;bool use_tt=true;bool cap_stocks=false;int local_threshold=0,local_max=0,local_count=0;size_t local_entries=0;std::vector<LocalSlot> local_slots;uint64_t local_hits=0,local_probes=0;Clock::time_point deadline;uint64_t nodes=0,tt_hits=0,cutoffs=0,stalemates_seen=0;
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    std::array<uint64_t,3> remwall_nodes{},remwall_tt_misses{},remwall_distinct_configs{};
    std::array<std::vector<uint8_t>,3> remwall_seen_configs;
    std::vector<uint32_t> remwall_one_config_tt_misses;
    void record_remaining_wall_layer(const State&s,int layer){
        if(layer<0||layer>2)return;
        ++remwall_nodes[size_t(layer)];auto&seen=remwall_seen_configs[size_t(layer)];
        if(seen.size()<=s.cfg_id)seen.resize(size_t(s.cfg_id)+1,0);
        if(!seen[s.cfg_id]){seen[s.cfg_id]=1;++remwall_distinct_configs[size_t(layer)];}
    }
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
    int tt_hint_first_mode=0; // 0 off, 1 all, 2 opponent, 3 target, 4 opponent pawn, 5 opponent wall, 6 canonical order only.
    bool tt_hint_transform=true;
    uint64_t hint_first_attempts=0,hint_first_legal=0,hint_first_illegal=0;
    uint64_t hint_first_pawn=0,hint_first_wall=0,hint_first_cutoffs=0,hint_first_continues=0;
    uint64_t hint_first_target_attempts=0,hint_first_opponent_attempts=0;
    uint64_t hint_first_target_cutoffs=0,hint_first_opponent_cutoffs=0;
    uint64_t hint_first_pawn_cutoffs=0,hint_first_wall_cutoffs=0;
#endif
    void ensure_local_slot(uint32_t id){if(id<local_slots.size())return;size_t n=local_slots.empty()?1024:local_slots.size();while(n<=id)n*=2;local_slots.resize(n);}
    size_t local_index(const State&s)const{return ((((size_t(s.walls[0])*(e.walls_each+1)+s.walls[1])*2+size_t(s.turn))*e.N+s.p[0])*e.N+s.p[1]);}
    LocalTable* local_for(const State&s,Player target){if(local_threshold<=0)return nullptr;ensure_local_slot(s.cfg_id);auto&slot=local_slots[s.cfg_id];uint32_t&v=slot.visits[int(target)];if(v!=UINT32_MAX)++v;if(!slot.table[int(target)]&&int(v)>=local_threshold&&local_count<local_max){slot.table[int(target)]=std::make_unique<LocalTable>(local_entries);++local_count;}return slot.table[int(target)].get();}
public:
    struct Result{bool solved=false;Player winner=P1;int depth=-1;uint64_t nodes=0,tt_hits=0,cutoffs=0,local_hits=0,local_probes=0,stalemates_seen=0;int local_tables=0;double seconds=0;bool timeout=false;
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        std::array<uint64_t,3> remwall_nodes{},remwall_tt_misses{},remwall_distinct_configs{};
        uint64_t remwall_one_max_tt_misses=0,remwall_one_configs_ge16=0,remwall_one_configs_ge64=0,remwall_one_configs_ge256=0,remwall_one_configs_ge1024=0;
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        uint64_t hint_first_attempts=0,hint_first_legal=0,hint_first_illegal=0,hint_first_pawn=0,hint_first_wall=0,hint_first_cutoffs=0,hint_first_continues=0;
        uint64_t hint_first_target_attempts=0,hint_first_opponent_attempts=0,hint_first_target_cutoffs=0,hint_first_opponent_cutoffs=0,hint_first_pawn_cutoffs=0,hint_first_wall_cutoffs=0;
#endif
    };
    ProofSolver(LazyEngine&eng,unsigned tt_bits,bool transpositions=true,bool horizon_stock_cap=false,int tt_ways=2,int local_tt_threshold=0,int local_tt_max=0
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        ,int hint_first_mode=0,bool transform_tt_hints=true
#endif
    ):e(eng),tt(transpositions?tt_bits:10,tt_ways),use_tt(transpositions),cap_stocks(horizon_stock_cap),local_threshold(local_tt_threshold),local_max(local_tt_max)
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        ,tt_hint_first_mode(hint_first_mode),tt_hint_transform(transform_tt_hints)
#endif
    {
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        if(tt_hint_first_mode<0||tt_hint_first_mode>6)throw std::runtime_error("TT hint-first mode must be 0..6");
#endif
        local_entries=size_t(e.walls_each+1)*(e.walls_each+1)*2*e.N*e.N;std::cerr<<"TT="<<(use_tt?LazyEngine::human_bytes(tt.bytes()):std::string("disabled"))<<" ways="<<tt_ways<<" lazy_cache stock_cap="<<cap_stocks<<" local_threshold="<<local_threshold<<" local_max="<<local_max<<" local_table="<<LazyEngine::human_bytes(local_entries*4)
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        <<" tt_hint_first_mode="<<tt_hint_first_mode<<" tt_hint_transform="<<tt_hint_transform
#endif
        <<"\n";}
    static inline int target_relevant_depth(Player turn,Player target,int depth){if(depth<=0||((turn==target)==((depth&1)!=0)))return depth;return depth-1;}
    bool prove(State s,Player target,int depth,std::vector<std::array<LazyEngine::Child,192>>&lists,int ply){
        e.resolve_state(s);++nodes;e.record_node_visit(s.cfg_id);if((nodes&16383ULL)==0&&Clock::now()>=deadline)throw SearchTimeout{};Player win;if(e.terminal(s,win))return win==target;depth=target_relevant_depth(s.turn,target,depth);if(depth<=0)return false;
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        int remwall_layer=int(s.walls[0])+int(s.walls[1]);record_remaining_wall_layer(s,remwall_layer);
        bool tablebase_result=false;if(e.zero_wall_tablebase_probe(s,target,depth,false,tablebase_result))return tablebase_result;
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        const bool canonical_hints=tt_hint_transform&&tt_hint_first_mode!=0;
        uint8_t key_transform=0;uint64_t key=0;if(canonical_hints){auto kt=e.canonical_key_with_transform(s,target,depth,cap_stocks);key=kt.first;key_transform=kt.second;}else key=e.canonical_key(s,target,depth,cap_stocks);
#ifndef NDEBUG
        if(key!=e.canonical_key(s,target,depth,cap_stocks))throw std::runtime_error("canonical TT hint key disagrees with canonical key");
#endif
#else
        uint64_t key=e.canonical_key(s,target,depth,cap_stocks);
#endif
        auto tt_store_move=[&](uint16_t move){
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
            return canonical_hints?e.transform_move(move,key_transform):move;
#else
            return move;
#endif
        };
        bool cached;uint16_t hint=0xffff;LocalTable*lt=local_for(s,target);size_t li=0;if(lt){++local_probes;li=local_index(s);if(lt->probe(li,depth,cached,hint)){++local_hits;return cached;}}
#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
        TransTable::ProbeToken tt_probe;
#endif
        if(use_tt){uint16_t tt_hint=0xffff;bool tt_cached=
#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
            tt.probe_with_token(key,depth,cached,tt_hint,tt_probe);
#else
            tt.probe(key,depth,cached,tt_hint);
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
            if(!tt_cached&&remwall_layer<=2){
                ++remwall_tt_misses[size_t(remwall_layer)];
                if(remwall_layer==1){if(remwall_one_config_tt_misses.size()<=s.cfg_id)remwall_one_config_tt_misses.resize(size_t(s.cfg_id)+1,0);++remwall_one_config_tt_misses[s.cfg_id];}
            }
#endif
            if(tt_hint!=0xffff)hint=
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
            canonical_hints?e.transform_move(tt_hint,key_transform):tt_hint;
#else
            tt_hint;
#endif
            if(tt_cached){++tt_hits;if(lt)lt->record(li,depth,cached,hint);return cached;}}
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        if(e.zero_wall_tablebase_probe(s,target,depth,true,tablebase_result))return tablebase_result;
#endif
        bool result=s.turn!=target;uint16_t best=0xffff;uint64_t hardest=0;bool hinted=false;
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        bool hint_mode_matches=tt_hint_first_mode==1||(tt_hint_first_mode==2&&s.turn!=target)||(tt_hint_first_mode==3&&s.turn==target)||(tt_hint_first_mode==4&&s.turn!=target&&hint<0x100u)||(tt_hint_first_mode==5&&s.turn!=target&&hint>=0x100u);
        if(hint_mode_matches&&hint!=0xffff){
            ++hint_first_attempts;if(s.turn==target)++hint_first_target_attempts;else ++hint_first_opponent_attempts;LazyEngine::Child hc{};
            if(e.try_legal_move(s,hint,hc)){
                ++hint_first_legal;if(hint<0x100u)++hint_first_pawn;else ++hint_first_wall;
                uint64_t before=nodes;bool child_result=prove(hc.s,target,depth-1,lists,ply+1);uint64_t cost=nodes-before;
                bool cutoff=s.turn==target?child_result:!child_result;
                if(cutoff){result=s.turn==target;best=hint;++cutoffs;++hint_first_cutoffs;if(s.turn==target)++hint_first_target_cutoffs;else ++hint_first_opponent_cutoffs;if(hint<0x100u)++hint_first_pawn_cutoffs;else ++hint_first_wall_cutoffs;if(use_tt)
#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
                    tt.record_from_probe(key,depth,result,tt_store_move(best),tt_probe);
#else
                    tt.record(key,depth,result,tt_store_move(best));
#endif
                    if(lt)lt->record(li,depth,result,best);return result;}
                hinted=true;hardest=cost;best=hint;++hint_first_continues;
            }else ++hint_first_illegal;
        }
#endif
        auto&ch=lists[ply];int n=e.generate(s,target,ch.data(),true);if(n==0){
            ++stalemates_seen;
            if(use_tt)
#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
                tt.record_from_probe(key,depth,false,tt_store_move(0xffff),tt_probe);
#else
                tt.record(key,depth,false,tt_store_move(0xffff));
#endif
            if(lt)lt->record(li,depth,false,0xffff);
            return false;
        }
        if(hint!=0xffff)for(int i=0;i<n;i++)if(ch[i].move==hint){if(i)std::swap(ch[0],ch[i]);break;}
        if(hinted){bool found=false;for(int i=0;i<n;i++)found|=ch[i].move==hint;if(!found)throw std::runtime_error("legal TT hint absent from full move generation");}
        if(s.turn==target){for(int i=0;i<n;i++){if(hinted&&ch[i].move==hint)continue;uint64_t before=nodes;if(prove(ch[i].s,target,depth-1,lists,ply+1)){result=true;best=ch[i].move;++cutoffs;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
                    e.record_pruned_handles(ch.data()+i+1,n-i-1);
#endif
                    break;}uint64_t cost=nodes-before;if(cost>hardest){hardest=cost;best=ch[i].move;}}}
        else{for(int i=0;i<n;i++){if(hinted&&ch[i].move==hint)continue;uint64_t before=nodes;if(!prove(ch[i].s,target,depth-1,lists,ply+1)){result=false;best=ch[i].move;++cutoffs;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
                    e.record_pruned_handles(ch.data()+i+1,n-i-1);
#endif
                    break;}uint64_t cost=nodes-before;if(cost>hardest){hardest=cost;best=ch[i].move;}}}
        if(use_tt)
#ifdef QSPEC_TT_SLOT_REUSE_EXPERIMENT
            tt.record_from_probe(key,depth,result,tt_store_move(best),tt_probe);
#else
            tt.record(key,depth,result,tt_store_move(best));
#endif
        if(lt) lt->record(li,depth,result,best);
        return result;
    }
    Result solve_from(State root,double seconds,int max_depth,int start_depth=1,int target_filter=-1){Result out;auto t0=Clock::now();deadline=t0+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));std::vector<std::array<LazyEngine::Child,192>>lists(size_t(max_depth)+2);int checked[2]={0,0};
        for(int d=start_depth;d<=max_depth;d++)for(Player target:{P1,P2}){if(target_filter>=0&&int(target)!=target_filter)continue;int rd=target_relevant_depth(root.turn,target,d);if(rd<=0||rd<=checked[int(target)])continue;checked[int(target)]=rd;uint64_t before=nodes;bool ok=false;try{ok=prove(root,target,rd,lists,0);}catch(const SearchTimeout&){out.timeout=true;goto done;}std::cerr<<"depth="<<rd<<" target="<<(target==P1?1:2)<<" proven="<<ok<<" nodes="<<(nodes-before)<<" total="<<nodes<<" elapsed="<<std::chrono::duration<double>(Clock::now()-t0).count()<<"s tt_hits="<<tt_hits<<" cache="<<e.cache_size()<<"\n";if(ok){out.solved=true;out.winner=target;out.depth=rd;goto done;}if(Clock::now()>=deadline){out.timeout=true;goto done;}}
    done:out.nodes=nodes;out.tt_hits=tt_hits;out.cutoffs=cutoffs;out.local_hits=local_hits;out.local_probes=local_probes;out.local_tables=local_count;out.stalemates_seen=stalemates_seen;out.seconds=std::chrono::duration<double>(Clock::now()-t0).count();
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        out.remwall_nodes=remwall_nodes;out.remwall_tt_misses=remwall_tt_misses;out.remwall_distinct_configs=remwall_distinct_configs;
        for(uint32_t count:remwall_one_config_tt_misses)if(count){out.remwall_one_max_tt_misses=std::max<uint64_t>(out.remwall_one_max_tt_misses,count);out.remwall_one_configs_ge16+=count>=16;out.remwall_one_configs_ge64+=count>=64;out.remwall_one_configs_ge256+=count>=256;out.remwall_one_configs_ge1024+=count>=1024;}
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        out.hint_first_attempts=hint_first_attempts;out.hint_first_legal=hint_first_legal;out.hint_first_illegal=hint_first_illegal;out.hint_first_pawn=hint_first_pawn;out.hint_first_wall=hint_first_wall;out.hint_first_cutoffs=hint_first_cutoffs;out.hint_first_continues=hint_first_continues;out.hint_first_target_attempts=hint_first_target_attempts;out.hint_first_opponent_attempts=hint_first_opponent_attempts;out.hint_first_target_cutoffs=hint_first_target_cutoffs;out.hint_first_opponent_cutoffs=hint_first_opponent_cutoffs;out.hint_first_pawn_cutoffs=hint_first_pawn_cutoffs;out.hint_first_wall_cutoffs=hint_first_wall_cutoffs;
#endif
        return out;}
    uint64_t node_count()const{return nodes;}
    uint64_t stalemate_count()const{return stalemates_seen;}
#ifdef QSPEC_TT_SLOT_REUSE_PROFILE
    uint64_t tt_slot_reuses()const{return tt.slot_reuses();}
#endif
};

} // namespace qspec

int main(int argc,char**argv){using namespace qspec;int W=3,H=9,walls=8,max_depth=80,start_depth=1,tt_bits=24,tt_ways=2,transition_cache_threshold=0,path_choice_weight=0,path_flow_weight=0,path_flow_cache_bits=18,local_tt_threshold=0,local_tt_max=0,order=1,target_filter=-1,root_index=-1,root_index2=-1,root_index3=-1,child_depth=-1,scan_root_start=0,scan_root_end=-1;double seconds=60;bool scan_current=false,list_root=false,list_second=false,list_third=false,use_tt=true,horizon_stock_cap=false,profile_visits=false,profile_cycle_gate=false,defer_cycle_safe=false;int symmetry=2;size_t cache_reserve=65536;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
    int local_touch_refine=0;
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
    int zero_wall_threshold=0,zero_wall_max=4096;
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
    int tt_hint_first_mode=0;bool tt_hint_transform=true;
#endif
    std::string root_move_name,second_move_name,third_move_name;
    for(int i=1;i<argc;i++){std::string a=argv[i];auto val=[&](auto&x){if(i+1>=argc)throw std::runtime_error("missing arg");std::stringstream ss(argv[++i]);ss>>x;};
        if(a=="--width")val(W);else if(a=="--height")val(H);else if(a=="--walls")val(walls);else if(a=="--max-depth")val(max_depth);else if(a=="--start-depth")val(start_depth);else if(a=="--target")val(target_filter);else if(a=="--tt-bits")val(tt_bits);else if(a=="--tt-ways")val(tt_ways);else if(a=="--transition-cache-threshold")val(transition_cache_threshold);else if(a=="--path-choice-weight")val(path_choice_weight);else if(a=="--path-flow-weight")val(path_flow_weight);else if(a=="--path-flow-cache-bits")val(path_flow_cache_bits);else if(a=="--root-move")val(root_move_name);else if(a=="--second-move")val(second_move_name);else if(a=="--third-move")val(third_move_name);else if(a=="--local-tt-threshold")val(local_tt_threshold);else if(a=="--local-tt-max")val(local_tt_max);else if(a=="--order")val(order);else if(a=="--seconds")val(seconds);else if(a=="--root-index")val(root_index);else if(a=="--root-index2")val(root_index2);else if(a=="--root-index3")val(root_index3);else if(a=="--child-depth")val(child_depth);else if(a=="--scan-root-start")val(scan_root_start);else if(a=="--scan-root-end")val(scan_root_end);else if(a=="--scan-current")scan_current=true;else if(a=="--list-root")list_root=true;else if(a=="--list-second")list_second=true;else if(a=="--list-third")list_third=true;else if(a=="--no-tt")use_tt=false;else if(a=="--no-symmetry")symmetry=0;else if(a=="--mirror-only")symmetry=1;else if(a=="--cache-reserve")val(cache_reserve);else if(a=="--horizon-stock-cap")horizon_stock_cap=true;else if(a=="--profile-config-visits")profile_visits=true;else if(a=="--profile-cycle-gate")profile_cycle_gate=true;else if(a=="--defer-cycle-safe")defer_cycle_safe=true;
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        else if(a=="--local-touch-refine"){std::string x;val(x);if(x=="all")local_touch_refine=-1;else{std::stringstream ss(x);char tail=0;if(!(ss>>local_touch_refine)||(ss>>tail))throw std::runtime_error("invalid local touch refinement: "+x);}}
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        else if(a=="--zero-wall-tablebase-threshold")val(zero_wall_threshold);
        else if(a=="--zero-wall-tablebase-max")val(zero_wall_max);
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        else if(a=="--tt-hint-first-mode"){std::string x;val(x);if(x=="off")tt_hint_first_mode=0;else if(x=="all")tt_hint_first_mode=1;else if(x=="opponent")tt_hint_first_mode=2;else if(x=="target")tt_hint_first_mode=3;else if(x=="opponent-pawn")tt_hint_first_mode=4;else if(x=="opponent-wall")tt_hint_first_mode=5;else if(x=="order-only")tt_hint_first_mode=6;else throw std::runtime_error("invalid TT hint-first mode: "+x);}
        else if(a=="--no-tt-hint-first")tt_hint_first_mode=0;
        else if(a=="--no-tt-hint-transform")tt_hint_transform=false;
#endif
        else if(a=="--no-bounds"||a=="--no-pawn-table"){}else if(a=="--help"){std::cout<<"lazy_frontier_solver --width 4 --height 7 --walls 7 --root-index 0 --root-index2 0 --root-index3 8 --target 1 --start-depth 24 --max-depth 24 --tt-bits 27 [--profile-cycle-gate] [--defer-cycle-safe] [--path-flow-weight 1] [--path-flow-cache-bits 18]"
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
            <<" [--local-touch-refine 0|2|4|all]"
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
            <<" [--zero-wall-tablebase-threshold N] [--zero-wall-tablebase-max N]"
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
            <<" [--tt-hint-first-mode off|all|opponent|target|opponent-pawn|opponent-wall|order-only] [--no-tt-hint-transform]"
#endif
            <<"\n";return 0;}else throw std::runtime_error("unknown argument: "+a);}
    if(target_filter==1)target_filter=0; else if(target_filter==2)target_filter=1; else target_filter=-1;
    try{LazyEngine e(W,H,walls,order,symmetry,cache_reserve,profile_visits,transition_cache_threshold,path_choice_weight,profile_cycle_gate,defer_cycle_safe,path_flow_weight,path_flow_cache_bits
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        ,local_touch_refine
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        ,zero_wall_threshold,zero_wall_max
#endif
        );State root=e.initial();auto label=[&](uint16_t mv){std::ostringstream o;if(mv<0x100){o<<"P("<<e.row(uint8_t(mv))<<","<<e.col(uint8_t(mv))<<")";}else{int w=mv-0x100,ori=w/e.S,z=w%e.S;o<<(ori?"V":"H")<<"("<<z/e.C<<","<<z%e.C<<")";}return o.str();};
        auto parse_move=[&](const std::string&text)->uint16_t{char kind=0,tail=0;int r=-1,c=-1;if(std::sscanf(text.c_str()," %c(%d,%d)%c",&kind,&r,&c,&tail)!=3)throw std::runtime_error("invalid move label: "+text);if(kind=='P'){if(r<0||r>=e.H||c<0||c>=e.W)throw std::runtime_error("pawn move out of range: "+text);return uint16_t(r*e.W+c);}if(kind=='H'||kind=='V'){if(r<0||r>=e.R||c<0||c>=e.C)throw std::runtime_error("wall move out of range: "+text);int ori=kind=='V';return uint16_t(0x100+ori*e.S+r*e.C+c);}throw std::runtime_error("invalid move kind: "+text);};
        auto choose=[&](State s,int idx,const std::string&wanted,bool list,const char*name)->State{e.resolve_state(s);std::array<LazyEngine::Child,192>ch{};Player target=target_filter==1?P2:P1;int n=e.generate(s,target,ch.data(),true);for(int i=0;i<n;i++)if(list)std::cout<<name<<"["<<i<<"] move="<<label(ch[i].move)<<" score="<<ch[i].score<<"\n";if(idx>=0&&!wanted.empty())throw std::runtime_error(std::string("use either ")+name+" index or named move, not both");if(!wanted.empty()){uint16_t code=parse_move(wanted);for(int i=0;i<n;i++)if(ch[i].move==code){std::cerr<<"forcing "<<name<<" move="<<label(ch[i].move)<<" index="<<i<<"\n";return ch[i].s;}throw std::runtime_error(std::string("named ")+name+" move is not legal: "+wanted);}if(idx<0)return s;if(idx>=n)throw std::runtime_error("child index out of range");std::cerr<<"forcing "<<name<<"["<<idx<<"] move="<<label(ch[idx].move)<<"\n";return ch[idx].s;};
        if(list_root){choose(root,-1,"",true,"root");return 0;}if(root_index>=0||!root_move_name.empty())root=choose(root,root_index,root_move_name,false,"root");if(list_second){choose(root,-1,"",true,"second");return 0;}if(root_index2>=0||!second_move_name.empty())root=choose(root,root_index2,second_move_name,false,"second");if(list_third){choose(root,-1,"",true,"third");return 0;}if(root_index3>=0||!third_move_name.empty())root=choose(root,root_index3,third_move_name,false,"third");
        if(scan_current){
            if(target_filter<0)throw std::runtime_error("scan-current requires --target 1 or 2");
            if(child_depth<0)child_depth=max_depth-1;
            // A named/indexed third move can itself be a deferred local-touch
            // child.  The scanner generates from that selected root directly,
            // so materialise it before indexing configuration-owned data.
            e.resolve_state(root);
            std::array<LazyEngine::Child,192> raw{};Player target=target_filter==0?P1:P2;
            int nr=e.generate(root,target,raw.data(),true);int first=std::max(0,scan_root_start),last=scan_root_end<0?nr-1:std::min(nr-1,scan_root_end);
            if(first>last||first>=nr)throw std::runtime_error("empty current scan range");
            int proved=0,refuted=0,unresolved=0;uint64_t aggregate_nodes=0,aggregate_stalemates=0;double aggregate_seconds=0;
            for(int i=first;i<=last;i++){
                ProofSolver branch(e,tt_bits,use_tt,horizon_stock_cap,tt_ways,local_tt_threshold,local_tt_max
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
                    ,tt_hint_first_mode,tt_hint_transform
#endif
                );
                auto br=branch.solve_from(raw[i].s,seconds,child_depth,child_depth,int(target));aggregate_nodes+=br.nodes;aggregate_stalemates+=br.stalemates_seen;aggregate_seconds+=br.seconds;bool win=br.solved&&br.winner==target;
                if(br.timeout)++unresolved;else if(win)++proved;else ++refuted;
                std::cout<<"current_scan task="<<i<<" rep="<<i<<" aliases="<<i<<" move="<<label(raw[i].move)<<" proven="<<win<<" timeout="<<br.timeout<<" nodes="<<br.nodes<<" tt_hits="<<br.tt_hits<<" stalemates_seen="<<br.stalemates_seen<<" seconds="<<br.seconds<<" child_depth="<<child_depth<<" total_suffix="<<(child_depth+1)<<" cache_configs="<<e.cache_size()<<" transition_entries="<<e.transition_entries()<<"\n"<<std::flush;
                if(root.turn==target&&win) break;
                if(root.turn!=target&&!br.timeout&&!win) break;
            }
            bool complete=first==0&&last==nr-1;bool bounded_proof=root.turn==target?proved>0:(refuted==0&&unresolved==0&&complete);bool bounded_refutation=root.turn==target?(proved==0&&unresolved==0&&complete):refuted>0;
            std::cout<<"current_scan_result proven="<<bounded_proof<<" refuted="<<bounded_refutation<<" child_proved="<<proved<<" child_refuted="<<refuted<<" child_unresolved="<<unresolved<<" aggregate_nodes="<<aggregate_nodes<<" stalemates_seen="<<aggregate_stalemates<<" aggregate_seconds="<<aggregate_seconds<<" total_suffix="<<(child_depth+1)<<" range="<<first<<"-"<<last<<" tasks="<<nr<<" raw="<<nr<<" unique=0 cache_configs="<<e.cache_size()<<" transition_entries="<<e.transition_entries()<<"\n";
            return bounded_proof?0:(bounded_refutation?1:(unresolved?3:1));
        }
        ProofSolver ps(e,tt_bits,use_tt,horizon_stock_cap,tt_ways,local_tt_threshold,local_tt_max
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
            ,tt_hint_first_mode,tt_hint_transform
#endif
        );auto r=ps.solve_from(root,seconds,max_depth,start_depth,target_filter);std::cout<<"width="<<W<<" height="<<H<<" walls="<<walls<<" solved="<<r.solved;if(r.solved)std::cout<<" winner="<<(r.winner==P1?1:2)<<" depth="<<r.depth;std::cout<<" nodes="<<r.nodes<<" tt_hits="<<r.tt_hits<<" cutoffs="<<r.cutoffs<<" local_hits="<<r.local_hits<<" local_probes="<<r.local_probes<<" local_tables="<<r.local_tables<<" stalemates_seen="<<r.stalemates_seen<<" seconds="<<r.seconds<<" timeout="<<r.timeout<<" cache_configs="<<e.cache_size()<<" cache_hits="<<e.cache_hits()<<" cache_misses="<<e.cache_misses()<<" cache_payload="<<e.cache_payload_bytes()<<" cache_estimated="<<e.cache_estimated_bytes()<<" transition_hits="<<e.transition_hits()<<" transition_builds="<<e.transition_builds()<<" transition_entries="<<e.transition_entries();if(path_flow_weight)std::cout<<" flow_cache_hits="<<e.flow_cache_hits()<<" flow_cache_misses="<<e.flow_cache_misses()<<" flow_cache_bytes="<<e.flow_cache_bytes();
#ifndef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        if(profile_cycle_gate||defer_cycle_safe)std::cout<<" cycle_gate_safe="<<e.cycle_gate_safe()<<" cycle_gate_fallback="<<e.cycle_gate_fallback()<<" deferred_emitted="<<e.deferred_emitted()<<" deferred_resolved="<<e.deferred_resolved();
#else
        if(profile_cycle_gate)std::cout<<" cycle_gate_safe="<<e.cycle_gate_safe()<<" cycle_gate_fallback="<<e.cycle_gate_fallback();
#endif
#ifdef QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT
        std::cout<<" local_touch_refine="<<(local_touch_refine<0?std::string("all"):std::to_string(local_touch_refine))<<" local_touch_exact_hits="<<e.local_touch_exact_hits()<<" local_touch_safe_misses="<<e.local_touch_safe_misses()<<" local_touch_fallback_misses="<<e.local_touch_fallback_misses()<<" deferred_emitted="<<e.deferred_emitted()<<" deferred_replayed="<<e.local_touch_pending_replayed()<<" deferred_patched="<<e.local_touch_pending_patched()<<" deferred_resolved="<<e.deferred_resolved()<<" deferred_resolve_hits="<<e.local_touch_resolve_hits()<<" deferred_resolve_builds="<<e.local_touch_resolve_builds()<<" deferred_pruned="<<e.local_touch_pruned()<<" deferred_pruned_uncached="<<e.local_touch_pruned_uncached()<<" bfs_passes_avoided="<<e.local_touch_bfs_passes_avoided()<<" deferred_refined="<<e.local_touch_refined()<<" refinement_order_changes="<<e.local_touch_refine_order_changes();
#endif
#ifdef QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT
        std::cout<<" zero_wall_threshold="<<e.zero_wall_threshold()<<" zero_wall_max="<<e.zero_wall_max()<<" zero_wall_queries="<<e.zero_wall_queries()<<" zero_wall_hits="<<e.zero_wall_hits()<<" zero_wall_tt_misses="<<e.zero_wall_tt_misses()<<" zero_wall_bypassed="<<e.zero_wall_bypassed()<<" zero_wall_builds="<<e.zero_wall_builds()<<" zero_wall_edges="<<e.zero_wall_edges()<<" zero_wall_ranked="<<e.zero_wall_ranked()<<" zero_wall_build_seconds="<<e.zero_wall_build_seconds()<<" zero_wall_bytes="<<e.zero_wall_table_bytes();
        for(int layer=0;layer<=2;layer++)std::cout<<" remwall_nodes_"<<layer<<"="<<r.remwall_nodes[size_t(layer)]<<" remwall_tt_misses_"<<layer<<"="<<r.remwall_tt_misses[size_t(layer)]<<" remwall_configs_"<<layer<<"="<<r.remwall_distinct_configs[size_t(layer)];
        std::cout<<" remwall_one_max_tt_misses="<<r.remwall_one_max_tt_misses<<" remwall_one_configs_ge16="<<r.remwall_one_configs_ge16<<" remwall_one_configs_ge64="<<r.remwall_one_configs_ge64<<" remwall_one_configs_ge256="<<r.remwall_one_configs_ge256<<" remwall_one_configs_ge1024="<<r.remwall_one_configs_ge1024;
#endif
#ifdef QSPEC_TT_HINT_FIRST_EXPERIMENT
        std::cout<<" tt_hint_first_mode="<<tt_hint_first_mode<<" tt_hint_transform="<<tt_hint_transform<<" tt_hint_transform_effective="<<(tt_hint_transform&&tt_hint_first_mode!=0)<<" hint_first_attempts="<<r.hint_first_attempts<<" hint_first_legal="<<r.hint_first_legal<<" hint_first_illegal="<<r.hint_first_illegal<<" hint_first_pawn="<<r.hint_first_pawn<<" hint_first_wall="<<r.hint_first_wall<<" hint_first_cutoffs="<<r.hint_first_cutoffs<<" hint_first_continues="<<r.hint_first_continues<<" hint_first_target_attempts="<<r.hint_first_target_attempts<<" hint_first_opponent_attempts="<<r.hint_first_opponent_attempts<<" hint_first_target_cutoffs="<<r.hint_first_target_cutoffs<<" hint_first_opponent_cutoffs="<<r.hint_first_opponent_cutoffs<<" hint_first_pawn_cutoffs="<<r.hint_first_pawn_cutoffs<<" hint_first_wall_cutoffs="<<r.hint_first_wall_cutoffs;
#endif
#ifdef QSPEC_MASK_INDEX_PROBE_PROFILE
        std::cout<<" mask_probe_reused="<<e.mask_probe_reused()<<" mask_probe_slot_reads_saved="<<e.mask_probe_slot_reads_saved()<<" mask_probe_rehash_fallbacks="<<e.mask_probe_rehash_fallbacks();
#endif
#ifdef QSPEC_TT_SLOT_REUSE_PROFILE
        std::cout<<" tt_slot_reuses="<<ps.tt_slot_reuses();
#endif
        if(profile_visits){std::cout<<" "<<e.visit_profile();}std::cout<<"\n";
    }catch(const std::exception&ex){std::cerr<<"error: "<<ex.what()<<"\n";return 2;}return 0;}
