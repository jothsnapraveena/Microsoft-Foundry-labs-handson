"""Run the independent Sessions 14?19 local checks; never call Azure."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = {
    14: "session-14-foundry-agent-security",
    15: "session-15-foundry-model-router",
    16: "session-16-foundry-toolboxes-mcp",
    17: "session-17-foundry-agent-skills",
    18: "session-18-foundry-hosted-agent-observability",
    19: "session-19-foundry-fine-tuning",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=int, action="append", choices=range(14,20))
    args = parser.parse_args()
    reports = []
    for number in args.session or list(SESSIONS):
        folder = ROOT / SESSIONS[number]
        checks = []
        for command in ([sys.executable, "lab.py", "plan"],
                        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]):
            run = subprocess.run(command, cwd=folder, text=True, capture_output=True, timeout=120)
            output = run.stdout + run.stderr
            match = re.search(r"Ran (\d+) tests?", output)
            checks.append({"command": command[1:], "exit_code": run.returncode,
                           "test_count": int(match.group(1)) if match else None, "output": output})
        report = {"session": number, "mode": "local checks; no live Azure proof",
                  "created_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
                  "passed": all(c["exit_code"] == 0 for c in checks)}
        path = folder / "artifacts/local-checks.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        reports.append(report)
        count = sum(c["test_count"] or 0 for c in checks)
        print(f"Session {number}: {'PASS' if report['passed'] else 'FAIL'} ({count} tests); {path.relative_to(ROOT)}")
        if not report["passed"]:
            for check in checks:
                if check["exit_code"]:
                    print(check["output"])
    raise SystemExit(0 if all(r["passed"] for r in reports) else 1)


if __name__ == "__main__":
    main()
