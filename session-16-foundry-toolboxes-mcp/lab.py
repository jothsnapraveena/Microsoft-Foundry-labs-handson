"""Inventory operator commands and Foundry toolbox consumers."""
import argparse
import json
import os
from pathlib import Path
from inventory import Inventory
from support import ROOT, confirm, invoke_agent, load_env, primitive, project, required, save, text

STATE = ROOT / "artifacts/resources.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "init", "stock", "approve", "toolbox", "agents", "ask", "approval-response", "cleanup"])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--sku", default="J-101")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--request-id", default="JR-001")
    parser.add_argument("--actor", default="lab-demo-user")
    parser.add_argument("--question", default="How many J-101 drills are available?")
    parser.add_argument("--consumer", choices=["stock", "purchasing"], default="stock")
    parser.add_argument("--response-id")
    parser.add_argument("--approval-id")
    parser.add_argument("--decision", choices=["approve", "deny"], default="deny")
    args = parser.parse_args()
    if args.command == "plan":
        print("Local: init, stock, approve, python server.py. Cloud: toolbox, agents, ask, cleanup --confirm.")
        return
    if args.command in ("init", "stock", "approve"):
        db = Inventory(ROOT / "artifacts/inventory.sqlite", ROOT / "data/inventory.json")
        db.initialize()
        if args.command == "stock":
            print(json.dumps(db.stock(args.sku)))
        elif args.command == "approve":
            db.approve(args.request_id, args.actor, args.sku, args.quantity)
            print("Operator approval recorded. This command is not exposed as an agent tool.")
        else:
            print("Synthetic inventory initialized without overwriting existing quantities.")
        return
    confirm(args)
    resources = json.loads(STATE.read_text()) if STATE.exists() else {"agents": []}
    with project() as (p, client):
        endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
        if resources.get("project_endpoint") not in (None, endpoint):
            raise ValueError("Resource ledger belongs to another Foundry project")
        resources["project_endpoint"] = endpoint
        if args.command == "toolbox":
            if resources.get("toolbox"):
                raise ValueError("A toolbox version is already recorded; inspect it before creating another")
            from azure.ai.projects.models import MCPToolboxTool
            created = p.toolboxes.create_version(name="s16-juniper",
                description="Session 16 authenticated synthetic inventory",
                tools=[MCPToolboxTool(server_label="juniper",
                    server_url=required("MCP_SERVER_URL"), require_approval="always",
                    project_connection_id=required("MCP_CONNECTION_ID"))])
            resources["toolbox"] = {"name": created.name, "version": created.version}
            save(STATE, resources)
            save(ROOT / "artifacts/toolbox.json", primitive(created))
            print("Saved toolbox version. Configure TOOLBOX_MCP_URL to its version-specific consumer URL.")
        elif args.command == "agents":
            from azure.ai.projects.models import PromptAgentDefinition, MCPTool
            for name in ("stock", "purchasing"):
                if any(a["consumer"] == name for a in resources["agents"]):
                    continue
                agent = p.agents.create_version(agent_name="s16-juniper-" + name,
                    definition=PromptAgentDefinition(model=required("MODEL_DEPLOYMENT"),
                        instructions=text("assets/baseline-instructions.md") + "\nYou are the " + name + " consumer.",
                        tools=[MCPTool(server_label="inventory", server_url=required("TOOLBOX_MCP_URL"),
                                       require_approval="always")]))
                resources["agents"].append({"consumer": name, "name": agent.name, "version": agent.version})
                save(STATE, resources)
        elif args.command == "ask":
            agent = next(a for a in reversed(resources["agents"]) if a["consumer"] == args.consumer)
            response = invoke_agent(client, agent["name"], agent["version"], args.question, store=True)
            # Approval requests are shown for review, never silently approved.
            save(ROOT / "artifacts/last-response.json", primitive(response))
            print(response.output_text or "Inspect last-response.json for pending tool approval requests.")
        elif args.command == "approval-response":
            if not args.response_id or not args.approval_id:
                raise ValueError("Supply --response-id and --approval-id from the saved request")
            agent = next(a for a in reversed(resources["agents"]) if a["consumer"] == args.consumer)
            response = client.responses.create(previous_response_id=args.response_id,
                input=[{"type": "mcp_approval_response", "approval_request_id": args.approval_id,
                        "approve": args.decision == "approve"}],
                extra_body={"agent_reference": {"type": "agent_reference", "name": agent["name"], "version": agent["version"]}})
            save(ROOT / "artifacts/last-response.json", primitive(response))
            print(response.output_text or "Another explicit approval may be pending; inspect saved output.")
        elif args.command == "cleanup":
            for agent in list(resources["agents"]):
                p.agents.delete_version(agent_name=agent["name"], agent_version=agent["version"])
                resources["agents"].remove(agent)
                save(STATE, resources)
            if resources.get("toolbox"):
                box = resources["toolbox"]
                p.toolboxes.delete_version(name=box["name"], version=box["version"])
                del resources["toolbox"]
                save(STATE, resources)
            print("Session agent/toolbox versions removed; connections and MCP hosting remain explicitly owned by you.")


if __name__ == "__main__":
    main()
