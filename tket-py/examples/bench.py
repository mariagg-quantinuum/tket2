from typing import Literal
import numpy as np
from pytket import Circuit
from tket.optimiser import SeadogOptimiser, BadgerOptimiser

from ..circuit_generation.cx_many_rz import CXManyRzBenchmarkCircuit
from ..circuit_generation.cx_gadget_vanilla import CXGadgetVanillaBenchmarkCircuit
from ..cx_gadget.cx_gadget import CXGadget
from ..zzphase_flip.zzphase_flip import ZZPhaseFlip

import time
import json
from pathlib import Path

rng = np.random.default_rng(42)


def bench_circuits(
    n: int, type: Literal["cx_many_rz", "cx_gadget"] = "cx_gadget"
) -> list[Circuit]:
    match type:
        case "cx_many_rz":
            return [
                CXManyRzBenchmarkCircuit(width=2 * i + 1, depth=10, rng=rng)
                for i in range(n)
            ]
        case "cx_gadget":
            return [
                CXGadgetVanillaBenchmarkCircuit(width=5, depth=4 * (i + 1), rng=rng)
                for i in range(n)
            ]


def save_bench_circuits(
    n: int, folder: str | Path, type: Literal["cx_many_rz", "cx_gadget"] = "cx_gadget"
):
    folder = Path(folder)
    circuits = bench_circuits(n, type)
    folder.mkdir(parents=True, exist_ok=True)
    width = len(str(n - 1))
    for i, circuit in enumerate(circuits):
        with open(folder / f"circuit_{i:0{width}d}.json", "w") as f:
            json.dump(circuit.to_dict(), f)


def run_with_optimiser(
    optimiser: SeadogOptimiser | BadgerOptimiser, circuit
) -> Circuit:
    n_gadgets = circuit.n_2qb_gates() // 4

    start_time = time.time()
    res: Circuit = optimiser.optimise(circuit, max_circuit_count=20)
    end_time = time.time()

    print(f"\tTime taken: {end_time - start_time:.2f} s")
    print("\tnum CX gates:", res.n_2qb_gates())

    assert res.n_2qb_gates() == 3 * n_gadgets


def run_benchmark():
    circuits = bench_circuits(5)

    for i, circuit in enumerate(circuits):
        print(f"\nBenchmarking circuit {i + 1}")
        print("Number of CX:", circuits[0].n_2qb_gates())

        seadog = SeadogOptimiser([CXGadget(), ZZPhaseFlip()])
        badger = BadgerOptimiser([CXGadget(), ZZPhaseFlip()])

        print("Running Badger...")
        run_with_optimiser(badger, circuit)
        print("Running Seadog...")
        run_with_optimiser(seadog, circuit)