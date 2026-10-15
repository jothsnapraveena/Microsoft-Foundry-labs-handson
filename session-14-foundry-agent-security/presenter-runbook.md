# Presenter Runbook

## Title and opening

**Agent Security and Red Teaming: Can we reduce successful instruction overrides while preserving useful policy answers?**

Open with this scenario: A fictional Cedar employee-policy assistant answers travel and expense questions from a bundled policy. It has no operational tools and cannot approve or pay expenses. Ask the audience to predict one failure mode before showing implementation details.

## 60-minute delivery plan

| Minutes | What to show | What the audience should learn |
| --- | --- | --- |
| 0?5 | Problem, input example and experiment question | Why this capability matters |
| 5?12 | Architecture and responsibility boundary | What Microsoft provides and what we build |
| 12?20 | Prepare the assistant; Establish legitimate behavior | How to establish a reproducible baseline |
| 20?35 | Run the fixed attacks; Configure an automated scan | The named Microsoft capability in action |
| 35?45 | Read the findings; Apply a controlled mitigation | How to inspect behavior and compare a change |
| 45?52 | Scorecard, failures and trade-offs | What the evidence supports |
| 52?57 | Cleanup and knowledge-check discussion | How to reproduce responsibly |
| 57?60 | Questions and community exercise | What to try next |

## Demo narration

1. Show fixture sec-01, hide its expected label from the tested request and explain the task.
2. Display the target configuration/version before invocation.
3. Run the relevant Microsoft operation and capture its real identifier.
4. Show fixture sec-04 or another edge case and ask whether the outcome meets the rubric.
5. Introduce only the intended experimental change and show the comparison.
6. End at the scorecard; explain a limitation alongside any improvement.

## Long-running or unavailable operations

Rehearse provisioning, scans or training in advance. Save genuine dated output and a screen recording. If a live operation is queued, label saved results as a prior rehearsal. If access was never obtained, show only the design and mark that capability unexecuted.

Do not promise that all eight fixtures will pass or that an optimization will improve quality. The session remains useful when the measurements reveal a regression.

## Presenter acceptance checklist

- Confirm all required access and feature support a day before presenting.
- Verify the public branch has synthetic fixtures and no credentials.
- Run the exact demo path and fill the evidence record.
- Prepare one healthy control case and one edge/failure case.
- Practice the explanation of Foundry AI Red Teaming Agent and safety evaluation.
- Check cleanup and ongoing charges after the presentation.
