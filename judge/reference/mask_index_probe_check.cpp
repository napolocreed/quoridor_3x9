#define QSPEC_MASK_INDEX_PROBE_EXPERIMENT 1
#define QSPEC_MASK_INDEX_PROBE_PROFILE 1
#define main lazy_specialized_solver_embedded_cli_main
#include "../src/lazy_specialized_solver.cpp"
#undef main

int main() {
    using namespace qspec;

    FlatMaskIndex index(1);
    auto first=index.probe(7);
    if(first.value!=UINT32_MAX)throw std::runtime_error("fresh mask index unexpectedly contains key");
    index.insert_at_miss(7,70,first);
    if(index.find(7)!=70)throw std::runtime_error("miss-slot insertion is not findable");

    auto stale=index.probe(9);
    index.insert(10,100);
    bool rejected=false;
    try { index.insert_at_miss(9,90,stale); }
    catch(const std::runtime_error&) { rejected=true; }
    if(!rejected)throw std::runtime_error("stale miss token was accepted");

    FlatMaskIndex threshold(1);
    for(uint64_t key=0;key<12;++key) {
        auto miss=threshold.probe(key);
        if(miss.value!=UINT32_MAX)throw std::runtime_error("duplicate key in threshold test");
        threshold.insert_at_miss(key,uint32_t(key),miss);
    }
    if(threshold.reused_miss_slots()!=11||threshold.rehash_fallbacks()!=1)
        throw std::runtime_error("unexpected miss-slot/rehash accounting");
    for(uint64_t key=0;key<12;++key)if(threshold.find(key)!=key)
        throw std::runtime_error("rehash fallback lost a key");

    std::cout<<"mask_index_probe_check status=ok reused="<<threshold.reused_miss_slots()
             <<" rehash_fallbacks="<<threshold.rehash_fallbacks()<<"\n";
    return 0;
}
