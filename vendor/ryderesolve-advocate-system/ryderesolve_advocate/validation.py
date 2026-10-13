import json
from importlib.resources import files
from jsonschema import Draft202012Validator


class ContractError(ValueError):
    pass


def validate_pack(pack):
    schema = json.loads(files("ryderesolve_advocate").joinpath("contracts/evidence-pack.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(pack), key=lambda e: str(e.path))
    if errors:
        raise ContractError("Invalid Evidence Pack: " + errors[0].message)
    json.dumps(pack, allow_nan=False)
    for field, key in (("facts", "evidence_id"), ("policy", "policy_id")):
        ids = [row[key] for row in pack[field]]
        if len(ids) != len(set(ids)):
            raise ContractError("Duplicate " + key)


def validate_output(output, pack, side):
    validate_pack(pack)
    schema = json.loads(files("ryderesolve_advocate").joinpath("contracts/advocate.schema.json").read_text(encoding="utf-8"))
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(output)]
    try:
        json.dumps(output, allow_nan=False)
    except (ValueError, TypeError):
        errors.append("Output must contain finite JSON values")
    warnings = []
    if isinstance(output, dict):
        if output.get("case_id") != pack["case_id"]:
            errors.append("case_id mismatch")
        if output.get("side") != side:
            errors.append("side mismatch")
        known_e = {x["evidence_id"] for x in pack["facts"]}
        known_p = {x["policy_id"] for x in pack["policy"]}
        for group in ("claims", "counterpoints"):
            rows = output.get(group, [])
            if not isinstance(rows, list):
                continue
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                for field, known in (("evidence_refs", known_e), ("policy_refs", known_p)):
                    refs = row.get(field, [])
                    if isinstance(refs, list):
                        for ref in refs:
                            if not isinstance(ref, str) or ref not in known:
                                errors.append(f"Unknown {field} in {group}[{i}]")
                if row.get("evidence_refs") == []:
                    warnings.append({"code": "UNSUPPORTED_STATEMENT", "path": f"/{group}/{i}"})
        if output.get("claims") == []:
            warnings.append({"code": "NO_CLAIMS", "path": "/claims"})
    return {"structurally_valid": not errors, "errors": errors, "warnings": warnings,
            "semantic_support_verified": False}
