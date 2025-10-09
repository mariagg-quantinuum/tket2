from pytket.passes import ThreeQubitSquash
from tket.circuit import Tk2Circuit
from tket.protocol import CircuitReplacer
from pytket import OpType
from pytket.passes import DecomposeBoxes, AutoRebase


def _boundary_permutation_detected(c):
    # After rebasing to a simple gate set, a boundary SWAP shows up explicitly.
    c2 = c.copy()
    DecomposeBoxes().apply(c2)
    AutoRebase({OpType.CX, OpType.Rx, OpType.Rz}).apply(c2)
    return any(cmd.op.type == OpType.SWAP for cmd in c2.get_commands())

class Simplify3SquashGadget(CircuitReplacer):
    def replace_match(self, matched_tk2: Tk2Circuit, match_info):
        # print("[Squash3] called; ports:", match_info)
        c = matched_tk2.to_tket1()
        before_order = list(c.qubits)

        ThreeQubitSquash().apply(c)

        # filter 1: explicit SWAP appearance under simple gate set
        perm = _boundary_permutation_detected(c)
        # filter 2: qubit order changed
        same = (list(c.qubits) == before_order)

        if perm or not same:
            # print("[Squash3] SKIP: perm=", perm, " same_boundary=", same)
            return []  # refuse rewrite cleanly

        # print("[Squash3] APPLY")
        return [Tk2Circuit(c)]

    



from tket.protocol import CircuitMatcher
from tket.matcher import CircuitUnit, MatchOutcome, MatchContext
from tket._tket.ops import TketOp
from tket.ops import TketOp as PyTketOp

ALLOWED_SINGLE_RS = tuple(p._to_rs() for p in (PyTketOp.Rx, PyTketOp.Rz))

def _is(op: TketOp, pyop: PyTketOp) -> bool:
    return op == pyop._to_rs()

def _is_single(op: TketOp) -> bool:
    return any(op == rs for rs in ALLOWED_SINGLE_RS)

def _linear_indices(op_args: list[CircuitUnit]) -> list[int]:
    idxs = []
    for a in op_args:
        li = getattr(a, "linear_index", None)
        if li is not None:
            idxs.append(li)
    return idxs

class Match3SquashGadget(CircuitMatcher):

    def match_tket_op(
        self, op: TketOp, op_args: list[CircuitUnit], match_context: MatchContext
    ) -> MatchOutcome:
        state = match_context["match_info"]
        qidxs = _linear_indices(op_args)

        # Only consider CX and allowed 1q ops
        if not (_is(op, PyTketOp.CX) or _is_single(op)):
            # If we haven't started, just skip; if started, end the match
            return {'stop': state is not None} or {'skip': True}

        if state is None:
            # initialise ordered ports by encounter
            ports: list[int] = []
            for q in qidxs:
                if q not in ports:
                    ports.append(q)
                if len(ports) > 3:
                    return {'stop': True}
            return {'proceed': ("collect", tuple(ports))}

        # Continue
        tag, ports = state
        ports = list(ports)

        # Any new qubit? append in encounter order
        for q in qidxs:
            if q not in ports:
                if len(ports) == 3:
                    # would introduce a 4th boundary wire -> terminate
                    return {'stop': True}
                ports.append(q)

        if len(ports) == 3:
            # We have our boundary; complete WITHOUT sorting
            return {'complete': tuple(ports)}

        # Still <3 unique qubits; keep collecting
        return {'proceed': ("collect", tuple(ports))}
