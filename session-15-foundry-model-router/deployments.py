"""Create/status/delete a session-owned Azure model deployment via ARM."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from support import ROOT, confirm, load_env, required, save

STATE = ROOT / "artifacts/deployments.json"


def resource_path(account, name):
    if not re.fullmatch(r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft\.CognitiveServices/accounts/[^/]+", account, re.I):
        raise ValueError("FOUNDRY_ACCOUNT_RESOURCE_ID must be a Cognitive Services account ARM ID")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,63}", name):
        raise ValueError("Invalid deployment name")
    return account + "/deployments/" + name


def arm(path, method="GET", body=None):
    from azure.identity import DefaultAzureCredential
    with DefaultAzureCredential() as credential:
        token = credential.get_token("https://management.azure.com/.default").token
        request = Request("https://management.azure.com" + path + "?api-version=2024-10-01",
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                          method=method)
        with urlopen(request, timeout=90) as response:
            content = response.read()
            return json.loads(content) if content else {"status": response.status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "create", "status", "delete"])
    parser.add_argument("--name", required=True)
    parser.add_argument("--model")
    parser.add_argument("--model-version")
    parser.add_argument("--format", default="OpenAI")
    parser.add_argument("--sku")
    parser.add_argument("--capacity", type=int)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        print("No cloud call. Create requires verified model, model-version, format, sku, capacity and account ARM ID.")
        return
    confirm(args)
    load_env()
    path = resource_path(required("FOUNDRY_ACCOUNT_RESOURCE_ID"), args.name)
    ledger = json.loads(STATE.read_text()) if STATE.exists() else {}
    if args.command == "create":
        if not args.model or not args.model_version or not args.sku or not args.capacity or args.capacity < 1:
            parser.error("Create requires --model, --model-version, --sku and positive --capacity")
        try:
            arm(path)
        except HTTPError as error:
            if error.code != 404:
                raise
        else:
            raise ValueError("Deployment already exists; refusing to overwrite")
        payload = {"sku": {"name": args.sku, "capacity": args.capacity},
                   "properties": {"model": {"format": args.format, "name": args.model, "version": args.model_version}}}
        ledger[path] = {"state": "create_requested", "payload": payload}
        save(STATE, ledger)
        result = arm(path, "PUT", payload)
        ledger[path]["state"] = "submitted"
        save(STATE, ledger)
    elif args.command == "delete":
        if path not in ledger:
            raise ValueError("Refusing to delete an unrecorded deployment")
        try:
            result = arm(path, "DELETE")
        except HTTPError as error:
            if error.code != 404:
                raise
            result = {"status": "already_absent"}
        ledger[path]["state"] = "delete_requested"
        save(STATE, ledger)
    else:
        result = arm(path)
    save(ROOT / "artifacts/deployment-status.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
