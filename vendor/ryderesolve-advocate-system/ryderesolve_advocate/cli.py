import argparse
import json
import sys
from pathlib import Path
from .agents import AdvocateSystem
from .providers import GeminiProvider, ProviderError
from .validation import ContractError, validate_output


def main():
    p = argparse.ArgumentParser(description="Run live advocates on a pack or Evidence snapshot")
    p.add_argument("--input", required=True)
    p.add_argument("--audit")
    p.add_argument("--output", required=True, help="New directory; refuses to overwrite")
    p.add_argument("--rebuttal", action="store_true")
    args = p.parse_args()
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        pack = data.get("evidence_pack", data)
        audit = json.loads(Path(args.audit).read_text(encoding="utf-8")) if args.audit else data.get("audit", {})
        target = Path(args.output)
        if target.exists():
            raise ContractError("Output directory already exists; choose a new run directory")
        provider = GeminiProvider.from_env()
        result = AdvocateSystem(provider).run_pair(pack, audit, args.rebuttal)
        target.mkdir(parents=True, exist_ok=False)
        for side, output in result["final"].items():
            (target / (side + ".json")).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        report = {s: validate_output(o, pack, s) for s, o in result["final"].items()}
        record = {"mode": "live_gemini", "model": provider.model,
                  "case_id": pack["case_id"], "snapshot_id": data.get("snapshot_id"),
                  "validation": report, **result}
        (target / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Saved live outputs to " + str(target))
    except (ContractError, ProviderError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
