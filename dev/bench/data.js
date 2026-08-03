window.BENCHMARK_DATA = {
  "lastUpdate": 1785780327877,
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
      },
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
          "id": "d6285decdd3bc1c9842adee5b8701adda38288ae",
          "message": "chore(release): 1.7.0",
          "timestamp": "2026-08-03T20:04:54+02:00",
          "tree_id": "518eda12dd8be27982c8a3f2b9846be62fdb21e7",
          "url": "https://github.com/mangrisano/certminder/commit/d6285decdd3bc1c9842adee5b8701adda38288ae"
        },
        "date": 1785780326756,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 173322.51449296216,
            "unit": "iter/sec",
            "range": "stddev: 6.178957059140644e-7",
            "extra": "mean: 5.769590886246954 usec\nrounds: 20168"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1668.1114293677185,
            "unit": "iter/sec",
            "range": "stddev: 0.000008902180552030672",
            "extra": "mean: 599.4803359024045 usec\nrounds: 908"
          }
        ]
      }
    ]
  }
}