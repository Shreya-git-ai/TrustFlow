from app.agent.evals.eval_cases import CASES
from app.agent.evals.run_evals import OracleProvider, evaluate


def test_case_names_are_unique():
    names = [c["name"] for c in CASES]
    assert len(names) == len(set(names))


def test_proofs_appear_in_evidence():
    for c in CASES:
        for quote in c["proof"].values():
            assert quote in c["evidence"], c["name"]


def test_oracle_passes_every_case():
    for c in CASES:
        r = evaluate(c, OracleProvider(c))
        assert r["ok"], r