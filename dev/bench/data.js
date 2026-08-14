window.BENCHMARK_DATA = {
  "lastUpdate": 1786746952453,
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
          "id": "b4e5f68175ae395f4cfd6c2762e6edebcd379023",
          "message": "chore(release)!: 2.0.0\n\nThe 1.7.0 tag failed CI: certinspect 2.0 requires Python >= 3.12, so a\nmatrix job on 3.10 could not resolve the dependency. certminder must drop\nPython 3.10/3.11 to match its dependency, which is a breaking change, so\nthis is released as 2.0.0 instead of 1.7.0.\n\nBREAKING CHANGE: minimum supported Python is now 3.12.",
          "timestamp": "2026-08-03T20:09:07+02:00",
          "tree_id": "2307db128391e8f4e462b72ddb5c22f1c1c019aa",
          "url": "https://github.com/mangrisano/certminder/commit/b4e5f68175ae395f4cfd6c2762e6edebcd379023"
        },
        "date": 1785780597367,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 215523.19633341584,
            "unit": "iter/sec",
            "range": "stddev: 6.070688555365418e-7",
            "extra": "mean: 4.6398717957625 usec\nrounds: 29765"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 2115.331680459954,
            "unit": "iter/sec",
            "range": "stddev: 0.000010717366990926247",
            "extra": "mean: 472.7391024477834 usec\nrounds: 1103"
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
          "id": "55fc9182b1dc7fdaf486f731dd4f7098becb807a",
          "message": "chore(release): 2.0.1",
          "timestamp": "2026-08-03T20:15:55+02:00",
          "tree_id": "5398aeb94f972e14098bda05753cf7c55851a3fb",
          "url": "https://github.com/mangrisano/certminder/commit/55fc9182b1dc7fdaf486f731dd4f7098becb807a"
        },
        "date": 1785780979076,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 123066.78695616884,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016999864921422733",
            "extra": "mean: 8.12566919745908 usec\nrounds: 21732"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1229.9457750808006,
            "unit": "iter/sec",
            "range": "stddev: 0.00001453074800911393",
            "extra": "mean: 813.0439733689118 usec\nrounds: 751"
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
          "id": "ee0eb454fbc3b1b074f311a186ea639259ce3d4b",
          "message": "chore(release): 2.1.0",
          "timestamp": "2026-08-15T00:35:32+02:00",
          "tree_id": "8efd8957c2918f97ab49a81e8692b2764f953a9e",
          "url": "https://github.com/mangrisano/certminder/commit/ee0eb454fbc3b1b074f311a186ea639259ce3d4b"
        },
        "date": 1786746951220,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 126517.98624623427,
            "unit": "iter/sec",
            "range": "stddev: 9.947495101481607e-7",
            "extra": "mean: 7.904014517380642 usec\nrounds: 21836"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1241.0683850128883,
            "unit": "iter/sec",
            "range": "stddev: 0.000014905696281934167",
            "extra": "mean: 805.7573716935955 usec\nrounds: 756"
          }
        ]
      }
    ]
  }
}