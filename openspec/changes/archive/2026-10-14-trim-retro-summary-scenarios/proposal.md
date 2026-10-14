# Proposal

## Why

`check_spec_proof.py`'s format guard reports one live requirement over the 3-scenario limit in
`openspec/config.yaml` `rules.specs`: "Summarising recent spec-to-pr runs" in `run-ledgers` has four.

## What Changes

- Retire that requirement and add its rewrite under a new heading, "Summarising recent spec-to-pr
  runs and their second rounds", as `rules.specs` directs. The sentence is unchanged. The two
  second-round scenarios merge into one, which keeps both facts (the total and the split by trigger).
  No scenario here protects money, security, personal data or an honesty claim.
- The `requirement:` markers in `test_spec_to_pr_aggregate.py` move to the new heading.

## Capabilities

### Modified Capabilities

- `run-ledgers`: one requirement replaced as above.

## Impact

One spec and one test file. No code, no version change.
