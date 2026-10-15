"""Describe policy sources without inventing platform policy or altering teammate data."""
from hashlib import sha256
from copy import deepcopy
import json

VERSION = "0.8"
LOCAL_RULES = [
    {"rule_id": "LOCAL-REFERENCES", "origin": "team_implementation", "description": "Evidence and policy IDs must belong to the current snapshot."},
    {"rule_id": "LOCAL-MATERIAL-GAPS", "origin": "team_implementation", "description": "Unresolved material policy/data gaps block a definitive recommendation."},
    {"rule_id": "LOCAL-MONEY", "origin": "team_implementation", "description": "Validate currency, refund bounds and decision/amount consistency."},
    {"rule_id": "LOCAL-STATEMENTS", "origin": "team_implementation", "description": "A party statement alone does not establish physical presence or responsibility."},
]


def policy_provenance(snapshot):
    audit = snapshot["audit"]
    rows = [{"policy_id": ref, "origin": item.get("policy_origin") or audit.get("policy_origin") or "unknown",
             "source_refs": list(item["source_refs"]),
             **{k: item[k] for k in ('source_document_id', 'document_sha256', 'version', 'effective_date') if k in item}}
            for ref, item in snapshot["source_index"]["policy"].items()]
    result = {"version": VERSION, "dataset_policy": rows,
              "dataset_origin": audit.get("data_origin") or "unknown",
              "local_safeguards": deepcopy(LOCAL_RULES),
              "boundary": "Source labels are provenance metadata, not independently authenticated policy. Local safeguards do not establish Ryde charging entitlement."}
    # Bind each evaluation to the actual provenance contract, not just a release name.
    result["sha256"] = sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result
