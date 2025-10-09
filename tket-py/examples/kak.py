from pytket.passes import KAKDecomposition
from tket.circuit import Tk2Circuit
from tket.protocol import CircuitReplacer

class ReplacerKAKGadget(CircuitReplacer):

    def replace_match(self, circuit: Tk2Circuit, match_info: float) -> list[Tk2Circuit]: 
        circuit_tket1 = circuit.to_tket1()
        KAKDecomposition().apply(circuit_tket1)
        return [Tk2Circuit(circuit_tket1)] 

# ---

from KAK.matcher_kak import MatcherKAKGadget
from KAK.replacer_kak import ReplacerKAKGadget
from tket.matcher import MatchReplaceRewriter

def KAKGadget():
    return MatchReplaceRewriter(
        MatcherKAKGadget(), ReplacerKAKGadget(), "2-qubit squash"
    )

# ---

from tket.protocol import CircuitMatcher
from tket.matcher import CircuitUnit
from tket._tket.ops import TketOp
from tket.matcher import MatchOutcome
from tket.matcher import MatchContext
from tket.ops import TketOp as PyTketOp

def matches_op(op: TketOp, op2: PyTketOp) -> bool:
    return op == op2._to_rs()

def succeeds_previous_op(op_args: list[CircuitUnit]) -> bool:
    """Whether this current op is in the future of previously matched ops."""
    return all(arg.linear_pos in ["after", None] for arg in op_args)

def get_qubits(op_args):
    return [a.linear_index for a in op_args if hasattr(a, "linear_index") and a.linear_index is not None]


def is_single_qubit_op(op_args):
    qs = get_qubits(op_args)
    return len(qs) == 1

class MatcherKAKGadget(CircuitMatcher):
    """
    Minimal KAK skeleton matcher.
    Pattern: CX(qi,qj) → single-qubit op (on qi or qj) → CX(qi,qj)
    """

    def match_tket_op(self, op: PyTketOp, op_args: list[CircuitUnit], ctx: MatchContext) -> MatchOutcome:
        state = ctx["match_info"]
        qubits = get_qubits(op_args)

        match state:
            # start: first CX
            case None:
                if matches_op(op, PyTketOp.CX):
                    ctrl, tgt = op_args[0].linear_index, op_args[1].linear_index
                    return {"proceed": ("first_cx", ctrl, tgt, False)}
                return {"skip": True}

            # after first CX, waiting for a local gate and then a second CX
            case ("first_cx", ctrl, tgt, saw_local):
                if not succeeds_previous_op(op_args):
                    return {"skip": True}

                # second CX
                if matches_op(op, PyTketOp.CX) and set(qubits) == {ctrl, tgt}:
                    return {"complete": (ctrl, tgt)}

                # any single-qubit gate on one of the pair — mark it
                if is_single_qubit_op(op_args) and any(q in {ctrl, tgt} for q in qubits):
                    return {"proceed": ("first_cx", ctrl, tgt, True)}

                # anything else -> skip or stop depending on qubits
                if len(qubits) == 0:
                    return {"skip": True}
                if not set(qubits).issubset({ctrl, tgt}):
                    return {"skip": True}

                return {"skip": True}

            case _:
                return {"skip": True}

