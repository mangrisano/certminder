"""Performance benchmarks for certminder's pure evaluation hot path.

Run in CI by the Performance workflow via pytest-benchmark. The ``bench_*``
filename keeps them out of default test collection. They exercise the
network-free problem detector on a synthetic result that trips several axes at
once (validity, chain, revocation, hostname, policy, weak crypto).
"""

from certminder.evaluator import detect_problems
from certminder.models import CheckResult, Target


def _make_result() -> CheckResult:
    target = Target(host="example.com", label="bench")
    return CheckResult(
        target=target,
        reachable=True,
        status="EXPIRING",
        exit_code=3,
        days_to_expire=10,
        fingerprint="AA:BB:CC:DD",
        revocation="REVOKED",
        chain_trusted=False,
        hostname_match=False,
        raw={
            "status": "EXPIRING",
            "chain_diagnosis": {
                "code": "INCOMPLETE_CHAIN",
                "detail": "missing intermediate",
            },
            "policy_violations": ["validity exceeds maximum", "weak key size"],
            "weak": ["1024-bit RSA key", "SHA-1 signature"],
            "chain_warnings": ["intermediate expiring soon"],
        },
    )


def test_detect_problems(benchmark):
    result = _make_result()
    events = benchmark(detect_problems, result)
    assert events


def test_detect_problems_batch(benchmark):
    results = [_make_result() for _ in range(100)]
    benchmark(lambda: [detect_problems(r) for r in results])
