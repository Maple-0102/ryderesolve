import copy
import json
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from .validation import ContractError, validate_output, validate_pack


def _parse(value):
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise ContractError("Model output must be JSON text or a dict")
    text = value.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    try:
        return json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, TypeError):
        raise ContractError("Model output is not valid finite JSON") from None


class AdvocateSystem:
    def __init__(self, provider):
        self.provider = provider

    def run_advocate(self, evidence_pack, audit=None, side="rider", opponent_output=None):
        if side not in ("rider", "driver"):
            raise ContractError("side must be rider or driver")
        validate_pack(evidence_pack)
        root = files("ryderesolve_advocate").joinpath("prompts")
        system = root.joinpath("common.txt").read_text(encoding="utf-8") + "\n" + root.joinpath(side + ".txt").read_text(encoding="utf-8")
        # Deliberately do not pass raw Markdown, expected rulings or evaluation labels.
        context = {"evidence_pack": evidence_pack, "audit": audit or {}}
        if opponent_output is not None:
            report = validate_output(opponent_output, evidence_pack, "driver" if side == "rider" else "rider")
            if not report["structurally_valid"]:
                raise ContractError("Invalid opponent output")
            context["opponent_output"] = opponent_output
        result = _parse(self.provider.generate(system, json.dumps(context, ensure_ascii=False, allow_nan=False)))
        report = validate_output(result, evidence_pack, side)
        if not report["structurally_valid"]:
            raise ContractError("Advocate validation failed: " + "; ".join(report["errors"]))
        return result

    def run_pair(self, evidence_pack, audit=None, rebuttal=False, parallel=False):
        # Parallel requires a thread-safe provider. Default is sequential but independent.
        def pair(opponents=None):
            def call(side):
                other = "driver" if side == "rider" else "rider"
                return self.run_advocate(evidence_pack, audit, side, opponents[other] if opponents else None)
            if parallel:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = {s: pool.submit(call, s) for s in ("rider", "driver")}
                    return {s: f.result() for s, f in futures.items()}
            return {s: call(s) for s in ("rider", "driver")}
        initial = pair()
        final = pair(initial) if rebuttal else initial
        return {"initial": initial, "final": final, "rounds": 2 if rebuttal else 1}


def run_advocate(evidence_pack, audit=None, side="rider", *, provider):
    return AdvocateSystem(provider).run_advocate(evidence_pack, audit, side)
