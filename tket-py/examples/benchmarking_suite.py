import sys
import time
import numpy as np
from pathlib import Path
from tqdm import tqdm
from typing import Callable, Dict, List

# pytket imports
from pytket import Circuit, OpType
from pytket.passes import DecomposeBoxes, AutoRebase

# add path to your local tket2_rewriting repo
sys.path.append("../../../tket2-rewriting/tket2_rewriting")

# import your custom optimisers
from cx_gadget.cx_gadget import CXGadget
from zzphase_flip.zzphase_flip import ZZPhaseFlip
from three_qubit_squash.three_qubit_squash_gadget import Squash3Gadget
from label.label_gadget import LabelGadget
from KAK.kak_gadget import KAKGadget
from tket.circuit import Tk2Circuit
from tket.optimiser import BadgerOptimiser

# ---------------------------------------------------------------------
# Import all your circuit generators
# ---------------------------------------------------------------------
from circuit_generation.cx_gadget_random import CXGadgetBenchmarkCircuit
from circuit_generation.cx_gadget_vanilla import CXGadgetVanillaBenchmarkCircuit
from circuit_generation.cx_many_rz import CXManyRzBenchmarkCircuit
from circuit_generation.gadget import (
    SquashGadgetTestCircuit,
    LabelFriendlyCircuit,
    SimpleLabelFriendlyCircuit,
    KAKFriendlyCircuit,
)

# ---------------------------------------------------------------------
# Benchmark configuration
# ---------------------------------------------------------------------
N_SAMPLES = 1000
WIDTH = 4
DEPTH = 10
RNG = np.random.default_rng(1234)

# List of circuit generators to benchmark
GENERATORS: Dict[str, Callable[[], Circuit]] = {
    "CXGadgetBenchmarkCircuit": lambda: CXGadgetBenchmarkCircuit(WIDTH, DEPTH, RNG),
    "CXGadgetVanillaBenchmarkCircuit": lambda: CXGadgetVanillaBenchmarkCircuit(WIDTH, DEPTH, RNG),
    "CXManyRzBenchmarkCircuit": lambda: CXManyRzBenchmarkCircuit(WIDTH, DEPTH, RNG),
    "SquashGadgetTestCircuit": SquashGadgetTestCircuit,
    "LabelFriendlyCircuit": lambda: LabelFriendlyCircuit(WIDTH, DEPTH, RNG),
    "SimpleLabelFriendlyCircuit": lambda: SimpleLabelFriendlyCircuit(WIDTH, DEPTH, RNG),
    "KAKFriendlyCircuit": lambda: KAKFriendlyCircuit(WIDTH, DEPTH, RNG),
}

# ---------------------------------------------------------------------
# Define optimiser pipeline (you can toggle gadgets here)
# ---------------------------------------------------------------------
OPTIMISER = BadgerOptimiser([
    ZZPhaseFlip(),
    # CXGadget(),
    # Squash3Gadget(),
    # # LabelGadget(),
    # KAKGadget(),
])

# ---------------------------------------------------------------------
# Helper function to benchmark a single generator
# ---------------------------------------------------------------------
def benchmark_generator(name: str, generator: Callable[[], Circuit], n_samples: int = N_SAMPLES):
    """Benchmark one circuit generator type over multiple random samples."""
    total_time = 0.0
    orig_2q, opt_2q = 0, 0

    for _ in tqdm(range(n_samples), desc=f"Benchmarking {name}"):
        # Generate circuit
        circ = generator()

        # Preprocess (flatten boxes + rebase)
        DecomposeBoxes().apply(circ)
        AutoRebase({OpType.CX, OpType.Rz, OpType.Rx}).apply(circ)

        # Convert to Tk2Circuit for BadgerOptimiser
        tk2_circ = Tk2Circuit(circ)

        # Optimise
        start = time.time()
        opt_circ_tk2 = OPTIMISER.optimise(tk2_circ)
        total_time += time.time() - start

        # Convert back to pytket Circuit
        opt_circ = opt_circ_tk2.to_tket1()

        # Count two-qubit gates
        orig_2q += circ.n_2qb_gates()
        opt_2q += opt_circ.n_2qb_gates()

    # Summarise
    reduction = orig_2q - opt_2q
    pct_reduction = 100.0 * reduction / orig_2q if orig_2q > 0 else 0.0
    avg_time = total_time / n_samples

    return {
        "name": name,
        "orig_2q": orig_2q,
        "opt_2q": opt_2q,
        "reduction": reduction,
        "pct_reduction": pct_reduction,
        "total_time": total_time,
        "avg_time": avg_time,
    }

# ---------------------------------------------------------------------
# Main benchmarking loop
# ---------------------------------------------------------------------
if __name__ == "__main__":
    results: List[Dict] = []

    print(f"\nRunning benchmarking suite on {len(GENERATORS)} circuit types...")
    for name, gen in GENERATORS.items():
        res = benchmark_generator(name, gen, N_SAMPLES)
        results.append(res)

    # Print summary
    print("\n=== BENCHMARK SUMMARY ===")
    for r in results:
        print(
            f"{r['name']:<35s} "
            f"2Q Gates: {r['orig_2q']:>6d} → {r['opt_2q']:>6d} "
            f"({r['pct_reduction']:.2f}% reduction) | "
            f"Avg Time: {r['avg_time']*1000:.2f} ms"
        )

    total_time = sum(r["total_time"] for r in results)
    print(f"\nTotal runtime for all benchmarks: {total_time:.2f} s")
