"""Local fault exercise and SDK hosted-agent version lifecycle."""
import argparse
import json
from pathlib import Path
from assistant import LookupFailure, answer
from support import ROOT, confirm, invoke_agent, primitive, project, record, required, save

STATE = ROOT / "artifacts/resources.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "local", "deploy", "status", "ask", "cleanup"])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--handler", choices=["v1", "v2"], default="v2")
    parser.add_argument("--question", default="Get the checklist for W-101.")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/local.json")
    args = parser.parse_args()
    if args.command == "plan":
        print("Local: local; python server.py --local. Cloud: build image, deploy, status, ask, cleanup --confirm.")
        return
    if args.command == "local":
        results = []
        for question in ("Get W-101.", "Get W-999.", "Get DEMO-FAIL.", "Get W-102."):
            try:
                result = answer(question, args.handler)
            except LookupFailure:
                result = {"status": "error", "error_code": "DEMO_LOOKUP_FAILURE"}
            results.append({"question": question, **result})
        save(args.report, record(18, results, mode="local function exercise; no hosted deployment/model call"))
        print(json.dumps(results, indent=2))
        return
    confirm(args)
    resources = json.loads(STATE.read_text()) if STATE.exists() else {"versions": []}
    with project() as (p, client):
        endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
        if resources.get("project_endpoint") not in (None, endpoint):
            raise ValueError("Resource ledger belongs to another Foundry project")
        resources["project_endpoint"] = endpoint
        if args.command == "deploy":
            from azure.ai.projects.models import HostedAgentDefinition, ContainerConfiguration, ProtocolVersionRecord, AgentEndpointProtocol
            created = p.agents.create_version(agent_name="s18-willow",
                definition=HostedAgentDefinition(
                    protocol_versions=[ProtocolVersionRecord(protocol=AgentEndpointProtocol.RESPONSES, version="2.0.0")],
                    cpu="1", memory="2Gi",
                    container_configuration=ContainerConfiguration(image=required("AGENT_IMAGE")),
                    environment_variables={"MODEL_DEPLOYMENT": required("MODEL_DEPLOYMENT"),
                        "MODEL_BACKEND": "azure", "HANDLER_VERSION": args.handler}))
            resources["versions"].append({"name": created.name, "version": created.version, "handler": args.handler})
            save(STATE, resources)
            print("Version submitted; use status until active before ask.")
        elif args.command in ("status", "ask"):
            version = resources["versions"][-1]
            info = p.agents.get_version(agent_name=version["name"], agent_version=version["version"])
            save(ROOT / "artifacts/remote-status.json", primitive(info))
            if args.command == "status":
                print(json.dumps(primitive(info), indent=2))
            else:
                if info.get("status") != "active":
                    raise ValueError("Recorded version is not active")
                response = invoke_agent(client, version["name"], version["version"], args.question)
                save(ROOT / "artifacts/remote-response.json", primitive(response))
                print(response.output_text)
        elif args.command == "cleanup":
            for version in list(resources["versions"]):
                p.agents.delete_version(agent_name=version["name"], agent_version=version["version"], force=True)
                resources["versions"].remove(version)
                save(STATE, resources)
            print("Recorded versions removed. Inspect remaining registry/log resources separately.")


if __name__ == "__main__":
    main()
