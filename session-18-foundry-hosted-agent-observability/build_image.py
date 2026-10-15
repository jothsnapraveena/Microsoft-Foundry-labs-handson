"""Explicit ACR build using an existing registry; no credentials placed in the image."""
import argparse
import re
import shutil
import subprocess
from support import ROOT, confirm, load_env, required

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--tag", default="s18-willow:demo")
    args = parser.parse_args()
    if not re.fullmatch(r"s18-willow:[a-zA-Z0-9_.-]+", args.tag):
        parser.error("Use a tag such as s18-willow:demo")
    confirm(args)
    load_env()
    executable = shutil.which("az")
    if not executable:
        raise SystemExit("Install Azure CLI and sign in manually")
    subprocess.run([executable, "acr", "build", "--registry", required("ACR_NAME"),
                    "--image", args.tag, "."], cwd=ROOT, check=True)
