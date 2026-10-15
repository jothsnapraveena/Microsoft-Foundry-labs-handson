"""Curate/validate SFT splits, run baselines, submit training and evaluate deployments."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from support import ROOT, chat, confirm, digest, exact_json, project, record, required, rows, save, stats, text

STATE = ROOT / "artifacts/resources.json"


def normalize(value):
    return re.sub(r"\s+", " ", value.casefold()).strip()


def validate_source(source):
    seen, families = {}, {}
    valid = {"billing", "access", "delivery"}
    for row in source:
        if row["split"] not in ("train", "validation"):
            raise ValueError("Only train/validation allowed in curated source; holdout is separate")
        expected = row["expected"]
        if (set(expected) != {"category", "priority"} or expected["category"] not in valid
                or expected["priority"] not in ("normal", "urgent")):
            raise ValueError("Invalid label")
        key = normalize(row["text"])
        if key in seen:
            raise ValueError("Duplicate normalized input")
        seen[key] = row["split"]
        if row["family"] in families and families[row["family"]] != row["split"]:
            raise ValueError("Scenario family crosses splits")
        families[row["family"]] = row["split"]
    holdout = {normalize(c["input"]) for c in rows()}
    if holdout.intersection(seen):
        raise ValueError("Holdout leakage")
    return {split: sum(r["split"] == split for r in source) for split in ("train", "validation")}


def prepare():
    source = [json.loads(line) for line in text("data/curated-tickets.jsonl").splitlines() if line.strip()]
    counts = validate_source(source)
    manifest = {"mode": "synthetic teaching corpus; human review required before submission",
                "source_sha256": digest(ROOT / "data/curated-tickets.jsonl"),
                "heldout_sha256": digest(ROOT / "data/cases.jsonl"), "counts": counts, "files": {}}
    for split in ("train", "validation"):
        entries = [{"messages": [
            {"role": "system", "content": text("assets/hardened-instructions.md")},
            {"role": "user", "content": r["text"]},
            {"role": "assistant", "content": json.dumps(r["expected"], sort_keys=True)}]}
            for r in source if r["split"] == split]
        path = ROOT / f"artifacts/{split}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in entries), encoding="utf-8")
        manifest["files"][split] = {"path": str(path), "sha256": digest(path)}
    save(ROOT / "artifacts/split-manifest.json", manifest)
    return manifest


def evaluate(client, targets, checkpoint=None, cases=None):
    result = []
    for name, deployment, instructions in targets:
        for case in (cases if cases is not None else rows()):
            tick = perf_counter()
            item = {"variant": name, "deployment": deployment, "case_id": case["id"], "expected": case["expected"]}
            try:
                response = chat(client, deployment, instructions, case["input"])
                item.update(status="completed", **response, **{"pass": exact_json(response["answer"], case["expected"])})
            except Exception as error:
                item.update(status="error", error_type=type(error).__name__, **{"pass": False})
            item["latency_ms"] = round((perf_counter() - tick) * 1000, 2)
            result.append(item)
            if checkpoint:
                checkpoint(result)
    return result


def summarize(result):
    return {variant: stats([r for r in result if r["variant"] == variant])
            for variant in sorted({r["variant"] for r in result})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "prepare", "baseline", "train", "status", "checkpoints", "evaluate", "cleanup"])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--data-reviewed", action="store_true")
    parser.add_argument("--min-examples", type=int, default=100)
    parser.add_argument("--baseline-report", type=Path, default=ROOT / "artifacts/baseline.json")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/comparison.json")
    args = parser.parse_args()
    if args.command == "plan":
        print("Local: prepare validates scenario-family splits. Cloud: baseline, train, status, checkpoints, evaluate, cleanup --confirm.")
        return
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2))
        return
    confirm(args)
    resources = json.loads(STATE.read_text()) if STATE.exists() else {"files": []}
    with project() as (_, client):
        endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
        if resources.get("project_endpoint") not in (None, endpoint):
            raise ValueError("Resource ledger belongs to another Foundry project")
        resources["project_endpoint"] = endpoint
        if args.command in ("baseline", "evaluate"):
            base = required("BASE_DEPLOYMENT")
            targets = [("baseline", base, text("assets/baseline-instructions.md")),
                       ("explicit_prompt", base, text("assets/hardened-instructions.md"))]
            path = args.baseline_report if args.command == "baseline" else args.report
            if args.command == "evaluate":
                tuned = required("FINE_TUNED_DEPLOYMENT")
                if tuned == base:
                    raise ValueError("Fine-tuned deployment must differ from base deployment")
                targets.append(("fine_tuned", tuned, text("assets/hardened-instructions.md")))
            if args.command == "baseline":
                source = [json.loads(line) for line in text("data/curated-tickets.jsonl").splitlines()]
                cases = [{"id": r["id"], "category": r["expected"]["category"], "input": r["text"], "expected": r["expected"]}
                         for r in source if r["split"] == "validation"]
            else:
                cases = rows()
            dataset_hash = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
            def checkpoint(result):
                save(path, record(19, result, summary=summarize(result),
                    dataset_sha256=dataset_hash, heldout_sha256=digest(ROOT / "data/cases.jsonl"),
                    evaluation_split="development_validation" if args.command == "baseline" else "held_out_test",
                    split_source_sha256=digest(ROOT / "data/curated-tickets.jsonl"),
                    target_prompts={name: hashlib.sha256(instructions.encode()).hexdigest()
                                    for name, _, instructions in targets},
                    training_job_id=resources.get("job_id")))
            result = evaluate(client, targets, checkpoint, cases)
            print(json.dumps(summarize(result), indent=2))
        elif args.command == "train":
            if resources.get("job_id"):
                raise ValueError("A job is already recorded; inspect it before submitting another")
            if not args.data_reviewed:
                raise ValueError("Review data and supply --data-reviewed before submission")
            if not args.baseline_report.exists():
                raise ValueError("Run a measured baseline first")
            baseline = json.loads(args.baseline_report.read_text())
            if (baseline.get("heldout_sha256") != digest(ROOT / "data/cases.jsonl")
                    or baseline.get("evaluation_split") != "development_validation"
                    or baseline.get("split_source_sha256") != digest(ROOT / "data/curated-tickets.jsonl")
                    or not any(r["status"] == "completed" for r in baseline["results"])):
                raise ValueError("Baseline must match current data and include completed model calls")
            base_model = required("FINE_TUNE_BASE_MODEL")
            manifest = prepare()
            if args.min_examples < 10 or manifest["counts"]["train"] < args.min_examples:
                raise ValueError("Training corpus below chosen eligible minimum")
            resources["data_reviewed"] = True
            resources["manifest"] = manifest
            save(STATE, resources)
            uploads = {}
            for split, info in manifest["files"].items():
                with Path(info["path"]).open("rb") as handle:
                    upload = client.files.create(file=handle, purpose="fine-tune")
                resources["files"].append(upload.id)
                uploads[split] = upload.id
                save(STATE, resources)
            job = client.fine_tuning.jobs.create(model=base_model,
                training_file=uploads["train"], validation_file=uploads["validation"],
                method={"type": "supervised", "supervised": {"hyperparameters": {"n_epochs": 1}}})
            resources["job_id"] = job.id
            save(STATE, resources)
            print(json.dumps({"job_id": job.id, "status": job.status}))
        elif args.command in ("status", "checkpoints"):
            job_id = resources["job_id"]
            if args.command == "status":
                job = client.fine_tuning.jobs.retrieve(job_id)
                save(ROOT / "artifacts/job-status.json", job)
                print(json.dumps({"id": job.id, "status": job.status, "fine_tuned_model": job.fine_tuned_model}))
            else:
                items = list(client.fine_tuning.jobs.checkpoints.list(job_id))
                save(ROOT / "artifacts/checkpoints.json", items)
                print(f"Saved {len(items)} checkpoint records")
        elif args.command == "cleanup":
            if resources.get("job_id"):
                job = client.fine_tuning.jobs.retrieve(resources["job_id"])
                if job.status not in ("succeeded", "failed", "cancelled"):
                    client.fine_tuning.jobs.cancel(job.id)
                    print("Cancellation requested. Re-run cleanup after terminal status.")
                    return
            for file_id in list(resources["files"]):
                client.files.delete(file_id)
                resources["files"].remove(file_id)
                save(STATE, resources)
            print("Recorded uploads deleted. Custom deployment/model artifacts require separate explicit cleanup.")


if __name__ == "__main__":
    main()
