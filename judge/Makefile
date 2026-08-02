CXX ?= g++
CXXFLAGS ?= -O3 -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic

# GNU ld otherwise inserts the current timestamp in PE/COFF images, making two
# identical MinGW builds hash differently. Linux and other toolchains are left
# unchanged.
REPRO_LDFLAGS :=
ifeq ($(OS),Windows_NT)
REPRO_LDFLAGS := -Wl,--no-insert-timestamp
override CXXFLAGS += $(REPRO_LDFLAGS)
endif

.PHONY: all test smoke audit-small lazy lazy-smoke lazy-differential lazy-flow-smoke external-review-smoke external-stalemate-smoke qcert-smoke qcert-aggregate-smoke local-gate-check experimental-qcert experimental-qcert-smoke experimental-dfpn dfpn-smoke experimental-local-touch local-touch-smoke local-touch-differential local-touch-audit-small experimental-zero-wall zero-wall-smoke zero-wall-differential zero-wall-audit-small experimental-tt-hint-first tt-hint-first-smoke tt-hint-first-differential tt-hint-first-audit-small experimental-mask-index-probe mask-index-probe-check mask-index-probe-smoke mask-index-probe-differential mask-index-probe-audit-small experimental-tt-slot-reuse tt-slot-reuse-check tt-slot-reuse-smoke tt-slot-reuse-differential tt-slot-reuse-audit-small clean
all: bin/frontier_solver bin/frontier_dump bin/frontier_state_solve

lazy: bin/lazy_specialized_solver bin/lazy_frontier_dump bin/lazy_frontier_state_solve

bin/lazy_specialized_solver: src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native $< -o $@

bin/lazy_frontier_dump: reference/lazy_frontier_dump.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native reference/lazy_frontier_dump.cpp -o $@

bin/lazy_frontier_state_solve: reference/lazy_frontier_state_solve.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native reference/lazy_frontier_state_solve.cpp -o $@

lazy-differential: bin/lazy_frontier_dump bin/lazy_frontier_state_solve
	python3 reference/differential_check.py --dump ./bin/lazy_frontier_dump --width 4 --height 3 --walls 3 --samples 1000 --seed 12345
	python3 reference/differential_check.py --dump ./bin/lazy_frontier_dump --width 3 --height 5 --walls 4 --samples 1000 --seed 22345
	python3 reference/differential_check.py --dump ./bin/lazy_frontier_dump --width 3 --height 9 --walls 8 --samples 500 --seed 32345
	python3 reference/proof_differential_check.py --solver ./bin/lazy_frontier_state_solve --width 3 --height 3 --walls 1 --samples 500 --max-depth 9 --seed 72026 --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/lazy_frontier_state_solve --width 3 --height 3 --walls 1 --samples 500 --max-depth 9 --seed 82026 --no-bounds --no-pawn-table --path-flow-weight 1

lazy-flow-smoke: bin/lazy_specialized_solver
	@out="$$(./bin/lazy_specialized_solver --width 4 --height 7 --walls 7 --root-move 'P(5,2)' --second-move 'P(1,2)' --third-move 'H(5,2)' --target 1 --start-depth 16 --max-depth 16 --seconds 30 --tt-bits 25 --transition-cache-threshold 1 --path-flow-weight 1 --path-flow-cache-bits 18 --no-bounds --no-pawn-table 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=0 nodes=2326659 .*stalemates_seen=0 .*timeout=0'

lazy-smoke: bin/lazy_specialized_solver
	@out="$$(./bin/lazy_specialized_solver --width 3 --height 3 --walls 1 --target 2 --start-depth 8 --max-depth 8 --seconds 30 --tt-bits 20 --transition-cache-threshold 1 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=1 winner=2 depth=8 .*stalemates_seen=0'

bin/frontier_solver: src/frontier_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) $< -o $@

bin/frontier_dump: reference/frontier_dump.cpp src/frontier_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) reference/frontier_dump.cpp -o $@

bin/frontier_state_solve: reference/frontier_state_solve.cpp src/frontier_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) reference/frontier_state_solve.cpp -o $@

smoke: bin/frontier_solver
	@out="$$(./bin/frontier_solver --width 3 --height 3 --walls 0 --target 2 --seconds 30 --max-depth 12 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=1 winner=2 depth=4 .*stalemates_seen=0'

test: all smoke
	python3 reference/known_outcomes.py --solver ./bin/frontier_solver
	python3 reference/differential_check.py --dump ./bin/frontier_dump --width 4 --height 3 --walls 3 --samples 1000 --seed 12345
	python3 reference/differential_check.py --dump ./bin/frontier_dump --width 3 --height 5 --walls 4 --samples 1000 --seed 22345
	python3 reference/differential_check.py --dump ./bin/frontier_dump --width 3 --height 9 --walls 8 --samples 500 --seed 32345
	python3 reference/proof_differential_check.py --solver ./bin/frontier_state_solve --width 3 --height 3 --walls 1 --samples 500 --max-depth 9 --seed 72026 --no-bounds --no-pawn-table
	python3 reference/symmetry_semantics_check.py --width 3 --height 3 --walls 1
	python3 reference/stalemate_invariant_check.py --width 3 --height 3 --walls 1
	python3 reference/solver_output_check.py
	python3 reference/audit_record_check.py
	python3 reference/reflection_partition_check.py
	python3 reference/manifest_counter_check.py
	python3 reference/stalemate_semantics_check.py

# Slower but still laptop-scale: exhaustive bounded-proof semantics on every 3x3x1 state.
audit-small: all lazy
	python3 reference/proof_differential_check.py --solver ./bin/frontier_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/frontier_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table --no-symmetry
	python3 reference/symmetry_semantics_check.py --width 4 --height 3 --walls 2 --samples 5000
	python3 reference/stalemate_invariant_check.py --width 4 --height 3 --walls 3
	python3 reference/cycle_gate_check.py --width 4 --height 3 --walls 3
	python3 reference/cycle_gate_check.py --width 3 --height 5 --walls 4
	python3 reference/proof_differential_check.py --solver ./bin/lazy_frontier_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table --defer-cycle-safe
	python3 reference/proof_differential_check.py --solver ./bin/lazy_frontier_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table --path-flow-weight 1

external-review-smoke: all external-stalemate-smoke
	./bin/frontier_dump --width 3 --height 9 --walls 10 --samples 200 --seed 777 | node external_reviews/claude_fable_2026-08-01/qref.mjs check-dump 3 9 10
	@out="$$(node external_reviews/claude_fable_2026-08-01/qref.mjs solve 3 3 1 10)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq '"winner":2,"depth":8,.*"stalematesSeen":0'
	node reference/qcert_verify_check.mjs
	python3 reference/qcert_verify_sqlite_check.py
	python3 reference/qcert_aggregate_verify_check.py

external-stalemate-smoke:
	python3 reference/external_stalemate_check.py

qcert-smoke:
	node reference/qcert_verify_check.mjs
	python3 reference/qcert_verify_sqlite_check.py
	python3 reference/qcert_aggregate_verify_check.py

qcert-aggregate-smoke:
	python3 reference/qcert_aggregate_verify_check.py

local-gate-check:
	python3 reference/local_cycle_gate_check.py --width 4 --height 3 --walls 3
	python3 reference/local_cycle_gate_check.py --width 4 --height 4 --walls 3
	python3 reference/local_cycle_gate_check.py --width 3 --height 5 --walls 4
	python3 reference/local_cycle_gate_check.py --width 2 --height 4 --walls 2

experimental-qcert: bin/lazy_qcert_emit

experimental-qcert-smoke: bin/lazy_qcert_emit
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	 rank_out=$$(./bin/lazy_qcert_emit --width 3 --height 3 --walls 0 --target 2 --bound 4 --seconds 60 --tt-bits 18 --budget-mode rank --output "$$tmp/rank.jsonl"); \
	 printf '%s\n' "$$rank_out"; printf '%s\n' "$$rank_out" | grep -Eq 'stalemates_seen=0'; \
	 node reference/qcert_verify.mjs "$$tmp/rank.jsonl"; \
	 exact_out=$$(./bin/lazy_qcert_emit --width 3 --height 3 --walls 0 --target 2 --bound 4 --seconds 60 --tt-bits 18 --budget-mode exact-dmin --output "$$tmp/exact.jsonl"); \
	 printf '%s\n' "$$exact_out"; printf '%s\n' "$$exact_out" | grep -Eq 'stalemates_seen=0'; \
	 node reference/qcert_verify.mjs "$$tmp/exact.jsonl"

bin/lazy_qcert_emit: experiments/tools/lazy_qcert_emit.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/tools/lazy_qcert_emit.cpp -o $@

experimental-dfpn: bin/lazy_dfpn_solver

dfpn-smoke: bin/lazy_dfpn_solver
	python3 reference/dfpn_known_outcomes.py --solver ./bin/lazy_dfpn_solver
	python3 reference/dfpn_known_outcomes.py --solver ./bin/lazy_dfpn_solver --rank-priors
	python3 reference/dfpn_known_outcomes.py --solver ./bin/lazy_dfpn_solver --rank-priors --incremental-cycle-safe

bin/lazy_dfpn_solver: experiments/solvers/lazy_dfpn_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_dfpn_solver.cpp -o $@

experimental-local-touch: bin/lazy_local_touch_gate_solver bin/lazy_local_touch_gate_dump bin/lazy_local_touch_gate_state_solve

bin/lazy_local_touch_gate_solver: experiments/solvers/lazy_local_touch_gate_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_local_touch_gate_solver.cpp -o $@

bin/lazy_local_touch_gate_dump: reference/lazy_frontier_dump.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -DQSPEC_LOCAL_TOUCH_GATE_EXPERIMENT=1 -march=native reference/lazy_frontier_dump.cpp -o $@

bin/lazy_local_touch_gate_state_solve: reference/lazy_frontier_state_solve.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -DQSPEC_LOCAL_TOUCH_GATE_EXPERIMENT=1 -march=native reference/lazy_frontier_state_solve.cpp -o $@

local-touch-smoke: bin/lazy_local_touch_gate_solver
	python3 reference/local_touch_gate_engine_check.py --solver ./bin/lazy_local_touch_gate_solver

local-touch-differential: experimental-local-touch
	@for k in 0 2 4 all; do \
	 python3 reference/differential_check.py --dump ./bin/lazy_local_touch_gate_dump --width 4 --height 3 --walls 3 --samples 1000 --seed 12345 --local-touch-refine $$k || exit 1; \
	 python3 reference/differential_check.py --dump ./bin/lazy_local_touch_gate_dump --width 3 --height 5 --walls 4 --samples 1000 --seed 22345 --local-touch-refine $$k || exit 1; \
	 python3 reference/differential_check.py --dump ./bin/lazy_local_touch_gate_dump --width 3 --height 9 --walls 8 --samples 500 --seed 32345 --local-touch-refine $$k || exit 1; \
	done
	@for k in 0 2 4 all; do \
	 python3 reference/proof_differential_check.py --solver ./bin/lazy_local_touch_gate_state_solve --width 3 --height 3 --walls 1 --samples 500 --max-depth 9 --seed 92026 --no-bounds --no-pawn-table --local-touch-refine $$k || exit 1; \
	done
	python3 reference/proof_differential_check.py --solver ./bin/lazy_local_touch_gate_state_solve --width 3 --height 3 --walls 1 --samples 1000 --max-depth 9 --seed 102026 --no-bounds --no-pawn-table --transition-cache-threshold 0 --local-touch-refine 0
	python3 reference/proof_differential_check.py --solver ./bin/lazy_local_touch_gate_state_solve --width 3 --height 3 --walls 1 --samples 1000 --max-depth 9 --seed 102026 --no-bounds --no-pawn-table --transition-cache-threshold 0 --local-touch-refine all
	python3 reference/proof_differential_check.py --solver ./bin/lazy_local_touch_gate_state_solve --width 3 --height 3 --walls 1 --samples 1000 --max-depth 9 --seed 122026 --no-bounds --no-pawn-table --transition-cache-threshold 2 --local-touch-refine 2
	python3 reference/proof_differential_check.py --solver ./bin/lazy_local_touch_gate_state_solve --width 3 --height 3 --walls 1 --samples 1000 --max-depth 9 --seed 162026 --no-bounds --no-pawn-table --path-flow-weight 1 --path-flow-cache-bits 18 --transition-cache-threshold 1 --local-touch-refine 2

local-touch-audit-small: bin/lazy_local_touch_gate_state_solve
	@for k in 0 2 4 all; do \
	 python3 reference/proof_differential_check.py --solver ./bin/lazy_local_touch_gate_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table --local-touch-refine $$k || exit 1; \
	done

experimental-zero-wall: bin/lazy_zero_wall_tablebase_solver bin/lazy_zero_wall_tablebase_state_solve

bin/lazy_zero_wall_tablebase_solver: experiments/solvers/lazy_zero_wall_tablebase_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_zero_wall_tablebase_solver.cpp -o $@

bin/lazy_zero_wall_tablebase_state_solve: reference/lazy_frontier_state_solve.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -DQSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT=1 -march=native reference/lazy_frontier_state_solve.cpp -o $@

zero-wall-smoke: bin/lazy_zero_wall_tablebase_solver
	@out="$$(./bin/lazy_zero_wall_tablebase_solver --width 3 --height 3 --walls 0 --target 2 --start-depth 4 --max-depth 4 --seconds 30 --tt-bits 20 --zero-wall-tablebase-threshold 1 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=1 winner=2 depth=4 .*stalemates_seen=0 .*zero_wall_builds=1'

zero-wall-differential: bin/lazy_zero_wall_tablebase_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_zero_wall_tablebase_state_solve --width 3 --height 3 --walls 1 --samples 2000 --max-depth 9 --seed 172026 --no-bounds --no-pawn-table --zero-wall-tablebase-threshold 1
	python3 reference/proof_differential_check.py --solver ./bin/lazy_zero_wall_tablebase_state_solve --width 4 --height 3 --walls 2 --samples 2000 --max-depth 10 --seed 182026 --no-bounds --no-pawn-table --zero-wall-tablebase-threshold 2

zero-wall-audit-small: bin/lazy_zero_wall_tablebase_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_zero_wall_tablebase_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table --zero-wall-tablebase-threshold 1

experimental-tt-hint-first: bin/lazy_tt_hint_first_solver bin/lazy_tt_hint_first_state_solve

bin/lazy_tt_hint_first_solver: experiments/solvers/lazy_tt_hint_first_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_tt_hint_first_solver.cpp -o $@

bin/lazy_tt_hint_first_state_solve: reference/lazy_frontier_state_solve.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -DQSPEC_TT_HINT_FIRST_EXPERIMENT=1 -march=native reference/lazy_frontier_state_solve.cpp -o $@

tt-hint-first-smoke: bin/lazy_tt_hint_first_solver
	@out="$$(./bin/lazy_tt_hint_first_solver --width 4 --height 7 --walls 7 --root-move 'P(5,2)' --second-move 'P(1,2)' --third-move 'H(5,2)' --target 1 --start-depth 16 --max-depth 16 --seconds 30 --tt-bits 25 --transition-cache-threshold 1 --path-flow-weight 1 --path-flow-cache-bits 18 --tt-hint-first-mode opponent --no-tt-hint-transform --no-bounds --no-pawn-table 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=0 .*stalemates_seen=0 .*timeout=0 .*tt_hint_first_mode=2 .*tt_hint_transform=0 .*hint_first_cutoffs=[1-9][0-9]*'

tt-hint-first-differential: bin/lazy_tt_hint_first_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_hint_first_state_solve --width 3 --height 3 --walls 1 --samples 2000 --max-depth 9 --seed 192026 --tt-hint-first-mode opponent --no-tt-hint-transform --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_hint_first_state_solve --width 4 --height 3 --walls 2 --samples 2000 --max-depth 10 --seed 202026 --tt-hint-first-mode opponent --no-bounds --no-pawn-table

tt-hint-first-audit-small: bin/lazy_tt_hint_first_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_hint_first_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --tt-hint-first-mode opponent --no-tt-hint-transform --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_hint_first_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --tt-hint-first-mode opponent --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_hint_first_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --tt-hint-first-mode off --no-bounds --no-pawn-table

experimental-mask-index-probe: bin/lazy_mask_index_probe_solver bin/lazy_mask_index_probe_profile_solver bin/lazy_mask_index_probe_state_solve

bin/mask_index_probe_check: reference/mask_index_probe_check.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) -O2 -std=c++20 -Wall -Wextra -Wpedantic $(REPRO_LDFLAGS) reference/mask_index_probe_check.cpp -o $@

mask-index-probe-check: bin/mask_index_probe_check
	./bin/mask_index_probe_check

bin/lazy_mask_index_probe_solver: experiments/solvers/lazy_mask_index_probe_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_mask_index_probe_solver.cpp -o $@

bin/lazy_mask_index_probe_profile_solver: experiments/solvers/lazy_mask_index_probe_profile_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_mask_index_probe_profile_solver.cpp -o $@

bin/lazy_mask_index_probe_state_solve: reference/lazy_frontier_state_solve.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -DQSPEC_MASK_INDEX_PROBE_EXPERIMENT=1 -march=native reference/lazy_frontier_state_solve.cpp -o $@

mask-index-probe-smoke: bin/lazy_mask_index_probe_profile_solver
	@out="$$(./bin/lazy_mask_index_probe_profile_solver --width 4 --height 7 --walls 7 --root-move 'P(5,2)' --second-move 'P(1,2)' --third-move 'H(5,2)' --target 1 --start-depth 16 --max-depth 16 --seconds 30 --tt-bits 25 --transition-cache-threshold 1 --path-flow-weight 1 --path-flow-cache-bits 18 --no-bounds --no-pawn-table 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=0 nodes=2326659 .*stalemates_seen=0 .*timeout=0 .*mask_probe_reused=[1-9][0-9]*'

mask-index-probe-differential: bin/lazy_mask_index_probe_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_mask_index_probe_state_solve --width 3 --height 3 --walls 1 --samples 2000 --max-depth 9 --seed 212026 --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/lazy_mask_index_probe_state_solve --width 4 --height 3 --walls 2 --samples 2000 --max-depth 10 --seed 222026 --cache-reserve 16 --no-bounds --no-pawn-table

mask-index-probe-audit-small: bin/lazy_mask_index_probe_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_mask_index_probe_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --cache-reserve 16 --no-bounds --no-pawn-table

experimental-tt-slot-reuse: bin/lazy_tt_slot_reuse_solver bin/lazy_tt_slot_reuse_profile_solver bin/lazy_tt_slot_reuse_state_solve

bin/tt_slot_reuse_check: reference/tt_slot_reuse_check.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) -O2 -std=c++20 -Wall -Wextra -Wpedantic $(REPRO_LDFLAGS) reference/tt_slot_reuse_check.cpp -o $@

tt-slot-reuse-check: bin/tt_slot_reuse_check
	./bin/tt_slot_reuse_check

bin/lazy_tt_slot_reuse_solver: experiments/solvers/lazy_tt_slot_reuse_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_tt_slot_reuse_solver.cpp -o $@

bin/lazy_tt_slot_reuse_profile_solver: experiments/solvers/lazy_tt_slot_reuse_profile_solver.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -march=native experiments/solvers/lazy_tt_slot_reuse_profile_solver.cpp -o $@

bin/lazy_tt_slot_reuse_state_solve: reference/lazy_frontier_state_solve.cpp src/lazy_specialized_solver.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -DQSPEC_TT_SLOT_REUSE_EXPERIMENT=1 -march=native reference/lazy_frontier_state_solve.cpp -o $@

tt-slot-reuse-smoke: bin/lazy_tt_slot_reuse_profile_solver
	@out="$$(./bin/lazy_tt_slot_reuse_profile_solver --width 4 --height 7 --walls 7 --root-move 'P(5,2)' --second-move 'P(1,2)' --third-move 'H(5,2)' --target 1 --start-depth 16 --max-depth 16 --seconds 30 --tt-bits 25 --transition-cache-threshold 1 --path-flow-weight 1 --path-flow-cache-bits 18 --no-bounds --no-pawn-table 2>/dev/null)"; \
	 echo "$$out"; \
	 echo "$$out" | grep -Eq 'solved=0 nodes=2326659 .*stalemates_seen=0 .*timeout=0 .*tt_slot_reuses=[1-9][0-9]*'

tt-slot-reuse-differential: bin/lazy_tt_slot_reuse_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_slot_reuse_state_solve --width 3 --height 3 --walls 1 --samples 2000 --max-depth 9 --seed 232026 --no-bounds --no-pawn-table
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_slot_reuse_state_solve --width 4 --height 3 --walls 2 --samples 2000 --max-depth 10 --seed 242026 --no-bounds --no-pawn-table

tt-slot-reuse-audit-small: bin/lazy_tt_slot_reuse_state_solve
	python3 reference/proof_differential_check.py --solver ./bin/lazy_tt_slot_reuse_state_solve --width 3 --height 3 --walls 1 --max-depth 9 --exhaustive-grid --no-bounds --no-pawn-table

clean:
	rm -rf bin build
