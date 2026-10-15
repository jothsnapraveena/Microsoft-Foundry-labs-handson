# Running Session 19

Create an environment, install requirements.txt and run:

~~~powershell
python -m unittest discover -s tests -v
python lab.py prepare
~~~

The source corpus has 160 synthetic training and 40 validation examples with scenario-family metadata. Preparation checks labels, normalized exact duplicates, family separation and overlap with the separate eight-row holdout. The output is chat-format JSONL and a split/hash manifest. This templated teaching corpus is not proof of real-world generalization; review data/dataset-card.md.

## Measure prompt baselines first

Configure this session's .env from .env.example, including BASE_DEPLOYMENT and a verified FINE_TUNE_BASE_MODEL identifier. These are different: inference uses a deployment name; training uses a supported base model/version identifier.

~~~powershell
python lab.py baseline --confirm
~~~

The two prompt baselines use the 40 development/validation examples (80 calls), not the final test set. Review errors and exact JSON accuracy. Record model identity, dataset hashes and prompt hashes before spending money on training.

## Submit and inspect training

Independently review labels, diversity and model-specific dataset requirements first. The default local floor is 100 training examples; it is a teaching check, not a universal service eligibility rule.

~~~powershell
python lab.py train --data-reviewed --min-examples 100 --confirm
python lab.py status --confirm
python lab.py checkpoints --confirm
~~~

Training uploads the prepared files, records file IDs immediately, then submits one supervised epoch. It refuses a second recorded job and requires a matching measured development baseline. SDK submission and polling are implemented; actual model/region eligibility and training success still require live Azure validation.

Review status and checkpoint artifacts. Select the checkpoint using validation evidence; do not select by inspecting the final holdout.

## Deploy and compare

Set FOUNDRY_ACCOUNT_RESOURCE_ID. Copy the chosen completed model/checkpoint identifier from the actual job output. Verify format, version, SKU and capacity for that model before deployment.

~~~powershell
python deployments.py create --name s19-alder-tuned --model YOUR_COMPLETED_CUSTOM_MODEL_ID --model-version VERIFIED_VERSION --format VERIFIED_FORMAT --sku VERIFIED_SKU --capacity VERIFIED_CAPACITY --confirm
python deployments.py status --name s19-alder-tuned --confirm
~~~

Set FINE_TUNED_DEPLOYMENT to this active custom deployment, then:

~~~powershell
python lab.py evaluate --confirm
~~~

This evaluates baseline, explicit prompt and fine-tuned conditions on the same eight held-out cases (24 calls). It records token usage and latency with exact JSON grading. Report class sample counts, failures and training/deployment costs separately; no free or guaranteed break-even inference is assumed.

## Cleanup

~~~powershell
python deployments.py delete --name s19-alder-tuned --confirm
python lab.py cleanup --confirm
~~~

Verify deployment absence to stop applicable hosting charges. The second command requests cancellation of active training and removes recorded uploaded files only after terminal job status; rerun after cancellation completes. Completed trained model artifacts remain for explicit lifecycle review/deletion in Foundry. A deleted upload is not a deleted deployment.
