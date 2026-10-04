"""Triage agent: routes supported requests and escalates everything else."""
from contracts import COMMON

NAME = "triage"
PROMPT = COMMON + '\nClassify the request: {"category":"mismatch"} or {"category":"other"}.'


def valid(value):
    return set(value) == {"category"} and value["category"] in ("mismatch", "other")


def classify(pipeline, payload, result):
    return (yield from pipeline.invoke(NAME, payload, result))["category"]
