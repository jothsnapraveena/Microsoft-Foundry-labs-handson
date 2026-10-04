# Session 10: Foundry Local — CLI and Python SDK

Run your first language model on your own computer, then evaluate whether it can help draft retail support responses. This session introduces Foundry Local through hands-on CLI and Python SDK workflows and a fictional retail support exercise.

## What you'll learn

- Install and verify the CLI.
- Discover model aliases and run a model selected for your hardware.
- Distinguish catalog, cached, and loaded models.
- Automate metadata inspection, model lifecycle, and streaming chat with Python.
- Discover and stop an optional local HTTP service.
- Assess responses against a small, repeatable support scenario.
- Explain where local inference fits alongside the cloud sessions.

## Why it matters

Sessions 8 and 9 introduced a retail support workflow. Here you explore a smaller task: drafting a reply from facts supplied directly in a prompt. Compare the result with the grounded support workflow you already built. Record what the model gets right, what it invents, and what a reviewer would need to check before using the draft.

## Local and cloud: choosing an execution environment

| Decision | What to examine |
|---|---|
| Hardware | Can the learner's device run the selected model comfortably? |
| Connectivity | Can setup finish before the offline exercise? |
| Response quality | Does the draft preserve the supplied facts? |
| Operations | Who maintains the device, model files, and runtime? |
| Workflow | Does the application need shared knowledge, live tools, or centralized controls? |

Local execution changes where inference happens. Assess the complete application separately, including any tools, logging, or remote dependencies you add later.

## Prerequisites and time

Use a Windows or macOS computer for this CLI lab, with internet access for installation and the initial model download. Plan around 90–120 minutes, plus download time. Azure resources and credentials are not needed for this lab. Review [the prerequisites](lab/01-prerequisites.md) before starting and leave enough memory and disk space for your chosen model.

## Start here

Open [lab/README.md](lab/README.md), complete the files in order, then answer [knowledge-check.md](knowledge-check.md). Record actual results in the evidence template rather than treating example prompts as proof of execution.

## Files

```text
session-10-foundry-local/
├── README.md
├── knowledge-check.md
├── requirements.txt
├── scripts/sdk_lab.py
└── lab/
    ├── README.md
    ├── 01-prerequisites.md
    ├── 02-architecture-flow.md
    ├── 03-implementation-steps.md
    ├── 04-validation-checks.md
    ├── 05-troubleshooting.md
    ├── 06-cleanup.md
    └── 07-proof-of-execution.md
```

## Extend the exercise

Try a second model with the same retail prompts. Compare factual fidelity, response time, and memory use, then explain which model you would choose for drafting support replies and why.
