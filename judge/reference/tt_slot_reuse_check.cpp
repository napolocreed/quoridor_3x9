#define QSPEC_TT_SLOT_REUSE_EXPERIMENT 1
#define QSPEC_TT_SLOT_REUSE_PROFILE 1
#define main lazy_specialized_solver_embedded_cli_main
#include "../src/lazy_specialized_solver.cpp"
#undef main

static void exercise(int ways) {
    using namespace qspec;
    TransTable direct(10,ways), reused(10,ways);
    uint64_t operations=0;
    for(uint64_t round=0;round<4000;++round){
        uint64_t key=mix64(round*17+3)|1ULL;
        int depth=int(round%40)+1;
        bool direct_value=false,reused_value=false;
        uint16_t direct_hint=0xffff,reused_hint=0xffff;
        bool direct_hit=direct.probe(key,depth,direct_value,direct_hint);
        TransTable::ProbeToken token;
        bool reused_hit=reused.probe_with_token(key,depth,reused_value,reused_hint,token);
        if(direct_hit!=reused_hit||direct_value!=reused_value||direct_hint!=reused_hint)
            throw std::runtime_error("TT probe mismatch before interleaved writes");

        // Recursive search may replace either candidate slot before the parent
        // returns. The token stores only immutable slot indices; recording must
        // still inspect their current keys and qualities.
        for(uint64_t j=0;j<5;++j){
            uint64_t other=mix64(round*97+j+100000)|1ULL;
            int other_depth=int((round+j)%31)+1;
            uint16_t move=uint16_t((round+j)%0x1ff);
            direct.record(other,other_depth,false,move);
            reused.record(other,other_depth,false,move);
        }
        uint16_t move=uint16_t(round%0x1ff);
        direct.record(key,depth,false,move);
        reused.record_from_probe(key,depth,false,move,token);
        ++operations;

        for(uint64_t sample=round>8?round-8:0;sample<=round;++sample){
            uint64_t probe_key=mix64(sample*17+3)|1ULL;
            bool a=false,b=false;uint16_t ah=0xffff,bh=0xffff;
            bool ar=direct.probe(probe_key,17,a,ah);
            bool br=reused.probe(probe_key,17,b,bh);
            if(ar!=br||a!=b||ah!=bh)throw std::runtime_error("TT state diverged after slot reuse");
        }
    }
    if(reused.slot_reuses()!=operations)throw std::runtime_error("TT slot reuse counter mismatch");

    uint64_t bounded_key=mix64(0x123456789abcdef0ULL)|1ULL;
    bool value=false;uint16_t hint=0xffff;
    TransTable::ProbeToken winning_token;
    if(reused.probe_with_token(bounded_key,12,value,hint,winning_token))
        throw std::runtime_error("fresh bounded key unexpectedly resolved");
    direct.record(bounded_key,12,true,37);
    reused.record_from_probe(bounded_key,12,true,37,winning_token);
    TransTable::ProbeToken failing_token;
    if(reused.probe_with_token(bounded_key,5,value,hint,failing_token))
        throw std::runtime_error("shallower query unexpectedly used an upper bound");
    direct.record(bounded_key,5,false,19);
    reused.record_from_probe(bounded_key,5,false,19,failing_token);
    for(int depth:{5,6,11,12,20}){
        bool a=false,b=false;uint16_t ah=0xffff,bh=0xffff;
        bool ar=direct.probe(bounded_key,depth,a,ah);
        bool br=reused.probe(bounded_key,depth,b,bh);
        if(ar!=br||a!=b||ah!=bh)throw std::runtime_error("TT upper/lower bounds diverged after slot reuse");
    }

#ifndef NDEBUG
    TransTable wrong_owner(10,ways);
    bool rejected=false;
    try{wrong_owner.record_from_probe(bounded_key,3,false,0xffff,failing_token);}
    catch(const std::runtime_error&){rejected=true;}
    if(!rejected)throw std::runtime_error("TT token from another table instance was accepted");
#endif
}

int main(){
    exercise(2);
    exercise(4);
    std::cout<<"tt_slot_reuse_check status=ok interleaved_operations=8000 bounds=ok owner_guard=ok\n";
    return 0;
}
