class Match3CXGadget(CircuitMatcher):

    def match_tket_op(
        self, op: TketOp, op_args: list[CircuitUnit], match_context: MatchContext
    ) -> MatchOutcome:

        state = match_context["match_info"]

        try:
            qubit_args = [arg for arg in op_args if hasattr(arg, "linear_index")]
            qubit_indices = [arg.linear_index for arg in qubit_args]
        except Exception as e:
            #print(f"[DEBUG CX ERROR]: Exception while extracting op info: {e}")
            return {'skip': True}

        match state:

            # No CX has been found yet.
            case None:
                if matches_op(op, PyTketOp.CX):
                    #print(f"[DEBUG CX]: Proceed → matched_first_cx "
                        #   f"(ctrl={op_args[0].linear_index}, "
                        #   f"trgt={op_args[1].linear_index})")
                    return {
                        'proceed': (
                            "matched_first_cx",
                            op_args[0].linear_index,
                            op_args[1].linear_index,
                        )
                    }
                return {'stop': True}

            # One CX has been found already.
            case ("matched_first_cx", ctrl_qubit, trgt_qubit):

                if not succeeds_previous_op(op_args):
                    return {'skip': True}
                if not matches_op(op, PyTketOp.CX):
                    return {'stop': True}
                if op_args[1].linear_index in {ctrl_qubit, trgt_qubit}:
                    return {'skip': True}
                if op_args[0].linear_index == trgt_qubit:
                    #print(f"[DEBUG CX]: Proceed → matched_second_cx "
                        #   f"(ctrl={ctrl_qubit}, "
                        #   f"new_trgt={op_args[1].linear_index})")
                    return {
                        'proceed': (
                            "matched_second_cx",
                            ctrl_qubit,
                            op_args[1].linear_index,
                        )
                    }
                return {'skip': True}

            # The first two CX gates have been found.
            case ("matched_second_cx", ctrl_qubit, trgt_qubit):

                if not succeeds_previous_op(op_args):
                    return {'skip': True}
                if not matches_op(op, PyTketOp.CX):
                    return {'skip': True}
                if op_args[0].linear_index == ctrl_qubit and op_args[1].linear_index == trgt_qubit:
                    #print(f"[DEBUG CX]: Complete → found third CX "
                        #   f"(ctrl={ctrl_qubit}, trgt={trgt_qubit})")
                    return {'complete': (ctrl_qubit, trgt_qubit)}

                return {'skip': True}


class Match3SquashGadget(CircuitMatcher):  

    def match_tket_op(
        self, op: TketOp, op_args: list[CircuitUnit], match_context: MatchContext
    ) -> MatchOutcome:
        state = match_context["match_info"]

        try:
            qubit_args = [arg for arg in op_args if hasattr(arg, "linear_index")]
            qubit_indices = [arg.linear_index for arg in qubit_args]
        except Exception:
            return {'skip': True}

        # Start a fresh match
        if state is None:
            if matches_op(op, PyTketOp.CX) or matches_op(op, PyTketOp.SingleQubit):
                return {'proceed': ("started", frozenset(qubit_indices))}
            return {'stop': True}

        case = state[0]
        qubits = state[1]

        # Check that gate stays on same 3 qubits
        if case == "started":
            if not all(q in qubits or len(qubits) < 3 for q in qubit_indices):
                return {'stop': True}

            new_qubits = set(qubits).union(qubit_indices)
            if len(new_qubits) > 3:
                return {'stop': True}

            if len(new_qubits) == 3:
                # Subcircuit over 3 qubits complete
                return {'complete': tuple(sorted(new_qubits))}

            return {'proceed': ("started", frozenset(new_qubits))}

class ZZPhaseMatcher(CircuitMatcher):
    def match_tket_op(
        self, op: TketOp, op_args: list[CircuitUnit], context: MatchContext
    ) -> MatchOutcome:
        state: MatchState = context["match_info"]
        #print("[DEBUG ZZ]: Matcher is called")
        #print(f"[DEBUG ZZ]: Current state: {state}")

        try:
            qubit_args = [arg for arg in op_args if hasattr(arg, "linear_index")]
            qubit_indices = [arg.linear_index for arg in qubit_args]
            #print(f"[DEBUG ZZ]: Qubit indices: {qubit_indices}")
            #print(f"[DEBUG ZZ]: op repr: {repr(op)}")
            #print(f"[DEBUG ZZ]: Inferred qubit count: {len(qubit_indices)}")
        except Exception as e:
            #print(f"[DEBUG ZZ ERROR]: Exception while #printing op info: {e}")
            return {"skip": True}

        match state:
            case None:
                #print("[DEBUG ZZ]: I found a None case match (looking for CX)")
                if matches_op(op, PyTketOp.CX):
                    [ctrl_qubit, tgt_qubit] = [arg.linear_index for arg in op_args]
                    assert all(arg.linear_pos is None for arg in op_args)
                    #print(f"[DEBUG ZZ]: First CX matched: ctrl={ctrl_qubit}, tgt={tgt_qubit}")
                    return {"proceed": ("matched_first_cx", ctrl_qubit, tgt_qubit)}
                else:
                    #print("[DEBUG ZZ]: Not a CX, stopping search")
                    return {"stop": True}

            case ("matched_first_cx", ctrl_qubit, tgt_qubit):
                #print("[DEBUG ZZ]: I found a matched_first_cx case match")
                if not succeeds_previous_op(op_args):
                    #print("[DEBUG ZZ]: Gate does not succeed previous, skipping")
                    return {"skip": True}

                if matches_op(op, PyTketOp.Rz) and op_args[0].linear_index == tgt_qubit \
                                               and op_args[1].constant_float is not None:
                    rot_angle = op_args[1].constant_float
                    #print(f"[DEBUG ZZ]: Found Rz rotation on tgt={tgt_qubit}, angle={rot_angle}")
                    return {"proceed": ("matched_rotation", ctrl_qubit, tgt_qubit, rot_angle)}
                else:
                    #print("[DEBUG ZZ]: Not an Rz on target, skipping")
                    return {"skip": True}

            case ("matched_rotation", ctrl_qubit, tgt_qubit, rot_angle):
                #print("[DEBUG ZZ]: I found a matched_rotation case match")
                if not succeeds_previous_op(op_args):
                    #print("[DEBUG ZZ]: Gate does not succeed previous, skipping")
                    return {"skip": True}

                if matches_op(op, PyTketOp.CX) and [arg.linear_index for arg in op_args] == [ctrl_qubit, tgt_qubit]:
                    #print("[DEBUG ZZ]: Found second CX, match complete")
                    return {"complete": rot_angle}
                else:
                    #print("[DEBUG ZZ]: Did not find expected second CX, skipping")
                    return {"skip": True}
