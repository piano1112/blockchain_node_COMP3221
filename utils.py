import json
import sys
import hashlib

# Must be run on the JSON text produced by json.dumps(obj, sort_keys=True,
# indent=2, separators=(',', ': '))
def hash_json(obj: dict) -> str:
    canonical = json.dumps(
        obj,
        sort_keys=True,
        indent=2,
        separators=(',', ': ')
    )

    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    return digest


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: utils.py '<json-string>'")

    raw = sys.argv[1]

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as err:
        sys.exit(f"Invalid JSON: {err}")

    print(hash_json(obj))
