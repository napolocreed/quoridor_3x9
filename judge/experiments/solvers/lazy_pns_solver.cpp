#define main lazy_specialized_solver_embedded_main
#include "../../src/lazy_specialized_solver.cpp"
#undef main

#include <deque>
#include <unordered_map>

namespace qpns {
using namespace qspec;
static constexpr uint32_t INF=0x3fffffffU;
static uint32_t sat_add(uint32_t a,uint32_t b){return a>=INF-b?INF:a+b;}

struct Key {
    uint64_t canonical=0;
    uint8_t depth=0;
    bool operator==(const Key&o)const{return canonical==o.canonical&&depth==o.depth;}
};
struct KeyHash {size_t operator()(const Key&k)const noexcept{return size_t(mix64(k.canonical^(uint64_t(k.depth)*0x9e3779b97f4a7c15ULL)));}};
struct ParentEdge {uint32_t parent=0,next=UINT32_MAX;};
struct Node {
    State state{};
    uint32_t pn=1,dn=1;
    uint32_t child_offset=0,parent_head=UINT32_MAX;
    uint16_t child_count=0;
    uint8_t depth=0;
    bool expanded=false;
};

class PnsSolver {
    LazyEngine&e;Player target;std::vector<Node>nodes;std::vector<uint32_t>children;std::vector<ParentEdge>parents;
    std::unordered_map<Key,uint32_t,KeyHash>index;Clock::time_point deadline;uint64_t expansions=0,selections=0,propagations=0;

    static int relevant(Player turn,Player target,int depth){if(depth<=0||((turn==target)==((depth&1)!=0)))return depth;return depth-1;}
    uint32_t add_node(const State&s,int depth){
        depth=relevant(s.turn,target,depth);Key k{e.canonical_key(s,target,depth,false),uint8_t(depth)};
        auto it=index.find(k);if(it!=index.end())return it->second;
        Node n;n.state=s;n.depth=uint8_t(depth);Player w;
        if(e.terminal(s,w)){n.expanded=true;if(w==target){n.pn=0;n.dn=INF;}else{n.pn=INF;n.dn=0;}}
        else if(depth<=0){n.expanded=true;n.pn=INF;n.dn=0;}
        uint32_t id=uint32_t(nodes.size());nodes.push_back(n);index.emplace(k,id);return id;
    }
    void link_parent(uint32_t child,uint32_t parent){parents.push_back({parent,nodes[child].parent_head});nodes[child].parent_head=uint32_t(parents.size()-1);}
    std::pair<uint32_t,uint32_t> aggregate(uint32_t id)const{
        const Node&n=nodes[id];if(!n.expanded||n.child_count==0)return {n.pn,n.dn};
        if(n.state.turn==target){uint32_t pn=INF,dn=0;for(uint16_t i=0;i<n.child_count;i++){const Node&c=nodes[children[n.child_offset+i]];pn=std::min(pn,c.pn);dn=sat_add(dn,c.dn);}return {pn,dn};}
        uint32_t pn=0,dn=INF;for(uint16_t i=0;i<n.child_count;i++){const Node&c=nodes[children[n.child_offset+i]];pn=sat_add(pn,c.pn);dn=std::min(dn,c.dn);}return {pn,dn};
    }
    void propagate_from(uint32_t start){
        std::deque<uint32_t>q;q.push_back(start);while(!q.empty()){uint32_t id=q.front();q.pop_front();for(uint32_t pe=nodes[id].parent_head;pe!=UINT32_MAX;pe=parents[pe].next){uint32_t p=parents[pe].parent;auto [pn,dn]=aggregate(p);if(pn==nodes[p].pn&&dn==nodes[p].dn)continue;nodes[p].pn=pn;nodes[p].dn=dn;++propagations;q.push_back(p);}}
    }
    void expand(uint32_t id){
        Node snapshot=nodes[id];if(snapshot.expanded)return;std::array<LazyEngine::Child,192>ch{};int n=e.generate(snapshot.state,target,ch.data(),true);
        uint32_t off=uint32_t(children.size());children.reserve(children.size()+n);std::vector<uint32_t>ids;ids.reserve(n);
        for(int i=0;i<n;i++)ids.push_back(add_node(ch[i].s,int(snapshot.depth)-1));
        // add_node may reallocate nodes, so write the parent only afterwards.
        nodes[id].child_offset=off;nodes[id].child_count=uint16_t(n);nodes[id].expanded=true;
        for(uint32_t cid:ids){children.push_back(cid);link_parent(cid,id);}
        if(n==0){nodes[id].pn=INF;nodes[id].dn=0;}else{auto [pn,dn]=aggregate(id);nodes[id].pn=pn;nodes[id].dn=dn;}
        ++expansions;propagate_from(id);
    }
    uint32_t select_leaf(uint32_t root){
        uint32_t id=root;while(nodes[id].expanded&&nodes[id].pn&&nodes[id].dn&&nodes[id].child_count){const Node&n=nodes[id];uint32_t best=children[n.child_offset];
            if(n.state.turn==target){for(uint16_t i=1;i<n.child_count;i++){uint32_t c=children[n.child_offset+i];if(nodes[c].pn<nodes[best].pn)best=c;}}
            else{for(uint16_t i=1;i<n.child_count;i++){uint32_t c=children[n.child_offset+i];if(nodes[c].dn<nodes[best].dn)best=c;}}
            id=best;++selections;
        }return id;
    }
public:
    struct Result{bool solved=false,value=false,timeout=false;uint64_t expansions=0,selections=0,propagations=0;size_t nodes=0,edges=0;double seconds=0;uint32_t pn=1,dn=1;};
    PnsSolver(LazyEngine&engine,Player tar,size_t reserve_nodes=1000000):e(engine),target(tar){nodes.reserve(reserve_nodes);children.reserve(reserve_nodes*2);parents.reserve(reserve_nodes*2);index.reserve(reserve_nodes*2);}
    Result solve(const State&root,int depth,double seconds,uint64_t max_expansions=UINT64_MAX){auto t0=Clock::now();deadline=t0+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));uint32_t rid=add_node(root,depth);
        while(nodes[rid].pn&&nodes[rid].dn&&expansions<max_expansions){if((expansions&1023ULL)==0&&Clock::now()>=deadline)break;uint32_t leaf=select_leaf(rid);if(nodes[leaf].expanded)break;expand(leaf);}
        Result r;r.solved=nodes[rid].pn==0||nodes[rid].dn==0;r.value=nodes[rid].pn==0;r.timeout=!r.solved&&Clock::now()>=deadline;r.expansions=expansions;r.selections=selections;r.propagations=propagations;r.nodes=nodes.size();r.edges=children.size();r.seconds=std::chrono::duration<double>(Clock::now()-t0).count();r.pn=nodes[rid].pn;r.dn=nodes[rid].dn;return r;}
};
}

int main(int argc,char**argv){using namespace qspec;using namespace qpns;int W=4,H=7,walls=7,depth=12,target_arg=1,root1=-1,root2=-1,root3=-1,transition_threshold=1;double seconds=60;size_t reserve=1000000;uint64_t max_expansions=UINT64_MAX;
    for(int i=1;i<argc;i++){std::string a=argv[i];auto val=[&](auto&x){if(++i>=argc)throw std::runtime_error("missing arg");std::stringstream ss(argv[i]);ss>>x;};if(a=="--width")val(W);else if(a=="--height")val(H);else if(a=="--walls")val(walls);else if(a=="--depth")val(depth);else if(a=="--target")val(target_arg);else if(a=="--root-index")val(root1);else if(a=="--root-index2")val(root2);else if(a=="--root-index3")val(root3);else if(a=="--seconds")val(seconds);else if(a=="--reserve-nodes")val(reserve);else if(a=="--max-expansions")val(max_expansions);else if(a=="--transition-cache-threshold")val(transition_threshold);}
    try{Player target=target_arg==2?P2:P1;LazyEngine e(W,H,walls,1,2,65536,false,transition_threshold);State root=e.initial();auto choose=[&](State s,int idx){if(idx<0)return s;std::array<LazyEngine::Child,192>ch{};int n=e.generate(s,target,ch.data(),true);if(idx>=n)throw std::runtime_error("child index");return ch[idx].s;};root=choose(root,root1);root=choose(root,root2);root=choose(root,root3);PnsSolver solver(e,target,reserve);auto r=solver.solve(root,depth,seconds,max_expansions);std::cout<<"solved="<<r.solved<<" value="<<r.value<<" timeout="<<r.timeout<<" pn="<<r.pn<<" dn="<<r.dn<<" expansions="<<r.expansions<<" graph_nodes="<<r.nodes<<" graph_edges="<<r.edges<<" selections="<<r.selections<<" propagations="<<r.propagations<<" seconds="<<r.seconds<<" cache_configs="<<e.cache_size()<<"\n";return r.solved?0:3;}catch(const std::exception&ex){std::cerr<<ex.what()<<"\n";return 2;}}
