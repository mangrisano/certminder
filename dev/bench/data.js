window.BENCHMARK_DATA = {
  "lastUpdate": 1785532948396,
  "repoUrl": "https://github.com/mangrisano/certminder",
  "entries": {
    "certminder benchmarks": [
      {
        "commit": {
          "author": {
            "email": "michele.angrisano@gmail.com",
            "name": "Michele Angrisano",
            "username": "mangrisano"
          },
          "committer": {
            "email": "michele.angrisano@gmail.com",
            "name": "Michele Angrisano",
            "username": "mangrisano"
          },
          "distinct": true,
          "id": "1ac296cef26e459ee80165540c9e435e48084aa3",
          "message": "ci: add performance benchmark workflow and badge",
          "timestamp": "2026-07-31T23:22:06+02:00",
          "tree_id": "9bee0fffacebe268521b90bbe6302b68aad02ba4",
          "url": "https://github.com/mangrisano/certminder/commit/1ac296cef26e459ee80165540c9e435e48084aa3"
        },
        "date": 1785532947719,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 126734.31711950614,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018401825623056747",
            "extra": "mean: 7.890522651864168 usec\nrounds: 14480"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1282.6792214400034,
            "unit": "iter/sec",
            "range": "stddev: 0.00003390741762097421",
            "extra": "mean: 779.6181487038881 usec\nrounds: 733"
          }
        ]
      }
    ]
  }
}