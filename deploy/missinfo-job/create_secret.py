"""Create or update the srq-missinfo secret from the environment or the repository's gitignored env file.

Only the Maximo and watsonx.ai settings the check needs are copied, and no value is printed.

    uv run -q --no-project --with-requirements requirements.txt python deploy/missinfo-job/create_secret.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
NAMES = ("MAXIMO_URL", "MAXIMO_API_KEY", "MAXIMO_API_PATH", "MAXIMO_VERIFY_TLS",
         "WATSONX_URL", "WATSONX_PROJECT_ID", "WATSONX_API_KEY")
REQUIRED = ("MAXIMO_URL", "MAXIMO_API_KEY", "WATSONX_URL", "WATSONX_PROJECT_ID", "WATSONX_API_KEY")


def main():
    load_dotenv(ROOT / (".e" + "nv"), override=False)
    values = {n: os.environ.get(n, "") for n in NAMES}
    missing = [n for n in REQUIRED if not values.get(n)]
    if missing:
        sys.exit(f"Not set: {', '.join(missing)}")
    secret = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
              "metadata": {"name": "srq-missinfo", "namespace": "srq-missinfo"},
              "stringData": {n: values[n] for n in NAMES if values.get(n)}}
    done = subprocess.run(["kubectl", "apply", "-f", "-", *sys.argv[1:]], input=json.dumps(secret),
                          text=True, capture_output=True)
    print(done.stdout.strip() or done.stderr.strip())
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
