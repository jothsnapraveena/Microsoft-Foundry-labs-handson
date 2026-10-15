"""Small, vendored helpers. Local commands never require Azure packages."""
import hashlib
import json
import math
import os
from pathlib import Path
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

ROOT = Path(__file__).resolve().parent


def load_env():
    path = ROOT / ".env"
    if path.exists():
        from dotenv import load_dotenv
        load_dotenv(path, override=False)


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing {name}; configure this session's .env.example")
    return value


def confirm(args):
    if not args.confirm:
        raise SystemExit("Cloud operation not executed. Review plan, then add --confirm.")


def rows(path=None):
    path = Path(path) if path else ROOT / "data/cases.jsonl"
    result = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r["id"] for r in result]
    if not result or len(ids) != len(set(ids)):
        raise ValueError("Cases must be nonempty with unique IDs")
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def primitive(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported report type: {type(value).__name__}")


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=primitive) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def record(session, results, **extra):
    packages = {}
    for package in ("azure-ai-projects", "azure-identity", "openai", "mcp"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            pass
    return {"session": session, "created_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": uuid4().hex, "packages": packages,
            "dataset_sha256": digest(ROOT / "data/cases.jsonl"),
            "results": results, **extra}


def exact_json(raw, expected):
    try:
        actual = json.loads(raw)
    except (ValueError, TypeError):
        return False
    return (isinstance(actual, dict) and set(actual) == set(expected)
            and all(type(actual[k]) is type(v) and actual[k] == v for k, v in expected.items()))


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return values[max(0, math.ceil(p * len(values)) - 1)]


def stats(results):
    measured = [r for r in results if type(r.get("pass")) is bool]
    ok = [r for r in results if r.get("status") == "completed"]
    return {"attempted": len(results), "completed": len(ok), "graded": len(measured),
            "passed": sum(r["pass"] for r in measured),
            "pass_rate_graded": sum(r["pass"] for r in measured) / len(measured) if measured else None,
            "ungraded": len(results) - len(measured),
            "p50_success_ms": percentile([r["latency_ms"] for r in ok], .5),
            "p95_success_ms": percentile([r["latency_ms"] for r in ok], .95)}


@contextmanager
def project():
    load_env()
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    with DefaultAzureCredential() as credential:
        with AIProjectClient(endpoint=required("AZURE_AI_PROJECT_ENDPOINT"),
                             credential=credential, allow_preview=True) as p:
            with p.get_openai_client() as client:
                client.max_retries = 0
                client.timeout = 90
                yield p, client


def invoke_agent(client, name, version, prompt, store=False):
    return client.responses.create(
        input=prompt, store=store,
        extra_body={"agent_reference": {"type": "agent_reference", "name": name, "version": version}})


def chat(client, deployment, instructions, prompt):
    response = client.chat.completions.create(
        model=deployment, messages=[{"role": "system", "content": instructions},
                                    {"role": "user", "content": prompt}])
    return {"answer": response.choices[0].message.content or "", "response_id": response.id,
            "response_model": response.model,
            "usage": primitive(response.usage) if response.usage else None}


def poll(fetch, terminal, timeout=600, interval=5):
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        status = str(getattr(value, "status", None) or value.get("status", "unknown"))
        if status in terminal:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError("Wait expired; remote work may continue. Use its saved ID to inspect/cancel.")
        time.sleep(min(interval, max(0, deadline - time.monotonic())))


def cli_error(main):
    try:
        main()
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        raise SystemExit(f"{type(error).__name__}: check local configuration and saved resource IDs") from None
