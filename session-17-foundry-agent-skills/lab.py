"""Versioned Foundry skills consumed explicitly by a small SDK model client."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from time import perf_counter
from zipfile import ZipFile
from support import ROOT, chat, confirm, exact_json, project, record, required, rows, save, stats, text

STATE = ROOT / "artifacts/resources.json"


def parse_skill(content):
    if not content.startswith("---\n"):
        raise ValueError("Missing front matter")
    parts = content.split("---\n", 2)
    if len(parts) != 3:
        raise ValueError("Invalid front matter")
    metadata = {}
    for line in parts[1].splitlines():
        key, value = line.split(":", 1)
        metadata[key] = value.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata.get("name", "")):
        raise ValueError("Invalid skill name")
    if not metadata.get("description") or not parts[2].strip():
        raise ValueError("Missing description or instructions")
    return metadata, parts[2].strip()


def downloaded_instructions(data):
    # The SDK downloads an archive. Read one file in memory, never extract paths.
    with ZipFile(BytesIO(data)) as archive:
        matches = [i for i in archive.infolist() if i.filename.split("/")[-1] == "SKILL.md"]
        if len(matches) != 1 or matches[0].file_size > 1_000_000:
            raise ValueError("Expected exactly one bounded SKILL.md")
        content = archive.read(matches[0]).decode("utf-8")
    return parse_skill(content)[1]


def local_validation():
    found = {}
    for variant in ("v1", "v2"):
        file = ROOT / f"assets/skills/{variant}/ticket-triage/SKILL.md"
        metadata, body = parse_skill(file.read_text(encoding="utf-8"))
        found[variant] = {"name": metadata["name"], "body_sha256": hashlib.sha256(body.encode()).hexdigest()}
    return {"mode": "local artifact validation; no model or Skills API called", "skills": found, "cases": len(rows())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "local", "register", "evaluate", "promote", "cleanup"])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--name", default="s17-ticket-triage")
    parser.add_argument("--variant", choices=["v1", "v2"], default="v2")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/skills-evaluation.json")
    args = parser.parse_args()
    if args.command in ("plan", "local"):
        result = local_validation()
        if args.command == "local":
            save(ROOT / "artifacts/local-validation.json", result)
        print(json.dumps(result, indent=2))
        return
    confirm(args)
    resources = json.loads(STATE.read_text()) if STATE.exists() else {"name": args.name, "versions": {}}
    if resources["name"] != args.name:
        raise ValueError("Use the name already recorded by this lab")
    with project() as (p, client):
        endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
        if resources.get("project_endpoint") not in (None, endpoint):
            raise ValueError("Resource ledger belongs to another Foundry project")
        resources["project_endpoint"] = endpoint
        if args.command == "register":
            from azure.ai.projects.models import SkillInlineContent
            for variant in ("v1", "v2"):
                if variant in resources["versions"]:
                    continue
                metadata, body = parse_skill(text(f"assets/skills/{variant}/ticket-triage/SKILL.md"))
                created = p.beta.skills.create(name=args.name, inline_content=SkillInlineContent(
                    description=metadata["description"], instructions=body), default=False)
                resources["versions"][variant] = {"version": created.version,
                    "source_sha256": hashlib.sha256(body.encode()).hexdigest()}
                save(STATE, resources)
            print(json.dumps(resources, indent=2))
        elif args.command == "evaluate":
            if set(resources["versions"]) != {"v1", "v2"}:
                raise ValueError("Register both skill variants first")
            variants = {"baseline": {"body": "", "version": None, "sha256": None}}
            for name, info in resources["versions"].items():
                payload = b"".join(p.beta.skills.download_version(name=args.name, version=info["version"]))
                body = downloaded_instructions(payload)
                variants[name] = {"body": body, "version": info["version"],
                                  "sha256": hashlib.sha256(body.encode()).hexdigest()}
                if variants[name]["sha256"] != info["source_sha256"]:
                    raise ValueError("Downloaded skill body differs from the registered source; inspect artifact")
            output = []
            model = required("MODEL_DEPLOYMENT")
            for name, info in variants.items():
                for case in rows():
                    tick = perf_counter()
                    row = {"case_id": case["id"], "variant": name, "skill_version": info["version"],
                           "loaded_body_sha256": info["sha256"], "expected": case["expected"]}
                    try:
                        response = chat(client, model,
                            text("assets/baseline-instructions.md") + "\n\n" + info["body"], case["input"])
                        row.update(status="completed", **response,
                                   **{"pass": exact_json(response["answer"], case["expected"])})
                    except Exception as error:
                        row.update(status="error", error_type=type(error).__name__, **{"pass": False})
                    row["latency_ms"] = round((perf_counter() - tick) * 1000, 2)
                    output.append(row)
                    save(args.report, record(17, output, model=model,
                        consumer="Explicit pinned Skills API download injected into fresh model context",
                        summary={v: stats([r for r in output if r["variant"] == v]) for v in variants}))
            print(f"Saved {args.report}")
        elif args.command == "promote":
            version = resources["versions"][args.variant]["version"]
            updated = p.beta.skills.update(args.name, default_version=version)
            print(json.dumps({"name": args.name, "default_version": updated.default_version}))
        elif args.command == "cleanup":
            for variant, info in list(resources["versions"].items()):
                p.beta.skills.delete_version(name=args.name, version=info["version"])
                del resources["versions"][variant]
                save(STATE, resources)
            print("Recorded skill versions removed. Inspect remaining parent/default metadata in Foundry.")


if __name__ == "__main__":
    main()
