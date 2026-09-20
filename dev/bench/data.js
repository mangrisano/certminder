window.BENCHMARK_DATA = {
  "lastUpdate": 1789922317760,
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
          "id": "77395c485ad42d6d8865b435388628766591dd44",
          "message": "chore(deps): bump certinspect minimum to 2.1.1\n\nAlign the pinned floor in pyproject.toml and requirements.txt with the\ncurrently installed certinspect release.",
          "timestamp": "2026-08-28T20:54:57+02:00",
          "tree_id": "cf0994518ec48e5ca651eee615884fba1c16b3ed",
          "url": "https://github.com/mangrisano/certminder/commit/77395c485ad42d6d8865b435388628766591dd44"
        },
        "date": 1787943322163,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 121922.0665383142,
            "unit": "iter/sec",
            "range": "stddev: 9.703426578534946e-7",
            "extra": "mean: 8.201960714681196 usec\nrounds: 43375"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1214.0421510934907,
            "unit": "iter/sec",
            "range": "stddev: 0.000014754037929444055",
            "extra": "mean: 823.694629629867 usec\nrounds: 648"
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
          "id": "004bf56a40599a57ec8b89da17009efde93f90b9",
          "message": "chore(deps): bump minimum dependency versions\n\nUpdate PyYAML, pytest, and ruff minimum versions to their latest\nreleases.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>",
          "timestamp": "2026-08-28T21:02:55+02:00",
          "tree_id": "648e6ec8301ba020c7bedb701a387caf68b7e6e6",
          "url": "https://github.com/mangrisano/certminder/commit/004bf56a40599a57ec8b89da17009efde93f90b9"
        },
        "date": 1787943799267,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 123042.4162980801,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011714351441695863",
            "extra": "mean: 8.127278625424749 usec\nrounds: 43912"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1235.5202909776303,
            "unit": "iter/sec",
            "range": "stddev: 0.0000240935077867942",
            "extra": "mean: 809.375618759551 usec\nrounds: 661"
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
          "id": "8dae8e3877532e96e7e61b9f95a42244d3cbeba8",
          "message": "chore(release): 2.2.0",
          "timestamp": "2026-09-18T10:27:42+02:00",
          "tree_id": "dc2c5f9c5c4137f993fddbe8fef083a117423187",
          "url": "https://github.com/mangrisano/certminder/commit/8dae8e3877532e96e7e61b9f95a42244d3cbeba8"
        },
        "date": 1789720088131,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 125026.25705255962,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018794867448827461",
            "extra": "mean: 7.99831990155165 usec\nrounds: 44323"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1232.4014082017259,
            "unit": "iter/sec",
            "range": "stddev: 0.000015507281363850535",
            "extra": "mean: 811.4239348843025 usec\nrounds: 645"
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
          "id": "2ad863d83cbb756129d887d0ce81b11a4841a01e",
          "message": "chore(release): 2.2.1\n\nRequire certinspect >= 2.2.0 (was >= 2.1.1) to track the current release.",
          "timestamp": "2026-09-18T10:34:54+02:00",
          "tree_id": "4b50e9dc6a5a6a551012d4a831920486b0bb0c97",
          "url": "https://github.com/mangrisano/certminder/commit/2ad863d83cbb756129d887d0ce81b11a4841a01e"
        },
        "date": 1789720512854,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 127150.45586645164,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011701943344186425",
            "extra": "mean: 7.864698503718443 usec\nrounds: 44979"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1244.1471461948734,
            "unit": "iter/sec",
            "range": "stddev: 0.000013173520167860661",
            "extra": "mean: 803.7634479638697 usec\nrounds: 663"
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
          "id": "86bf7ec47b119a036b2d30defc1270c529564cb4",
          "message": "build(docker): add portable PyPI-based deployment under deploy/docker\n\nBuilds the image from the published certminder release instead of the local\nsource, so it runs on a machine without a checkout of this repo (e.g. a Windows\nhost). Uses build context '.' and a managed named volume, avoiding the absolute\nbuild path and external volume of the source-based setup.",
          "timestamp": "2026-09-18T11:17:35+02:00",
          "tree_id": "5f8eb263115722cce4cef954a5c8ca0d5f80c986",
          "url": "https://github.com/mangrisano/certminder/commit/86bf7ec47b119a036b2d30defc1270c529564cb4"
        },
        "date": 1789723076840,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 124340.33376186462,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013455994888501048",
            "extra": "mean: 8.042442622964082 usec\nrounds: 45933"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1243.5033882524797,
            "unit": "iter/sec",
            "range": "stddev: 0.00006917338784278423",
            "extra": "mean: 804.179553869427 usec\nrounds: 659"
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
          "id": "5beb1a88f3aa4a60294f909c9940b3e5e53f126b",
          "message": "chore(release): 2.3.0",
          "timestamp": "2026-09-20T14:19:15+02:00",
          "tree_id": "324f9693a3eec59f654eeed371c0643c937fe275",
          "url": "https://github.com/mangrisano/certminder/commit/5beb1a88f3aa4a60294f909c9940b3e5e53f126b"
        },
        "date": 1789906781150,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 162938.56214316018,
            "unit": "iter/sec",
            "range": "stddev: 9.502026649253507e-7",
            "extra": "mean: 6.137282585821431 usec\nrounds: 39956"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1533.7740198535244,
            "unit": "iter/sec",
            "range": "stddev: 0.00012241731543188587",
            "extra": "mean: 651.9865293425039 usec\nrounds: 852"
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
          "id": "0523b3edd43f6a01ce427d888fc3e03c5ff58cbe",
          "message": "chore(release): 2.4.0",
          "timestamp": "2026-09-20T18:37:45+02:00",
          "tree_id": "873137cd6bc1679e2d6884a72c9de3f3813ef205",
          "url": "https://github.com/mangrisano/certminder/commit/0523b3edd43f6a01ce427d888fc3e03c5ff58cbe"
        },
        "date": 1789922316797,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems",
            "value": 159423.53515603047,
            "unit": "iter/sec",
            "range": "stddev: 7.798781380338031e-7",
            "extra": "mean: 6.272599582121192 usec\nrounds: 55045"
          },
          {
            "name": "benchmarks/bench_perf.py::test_detect_problems_batch",
            "value": 1556.5295429035589,
            "unit": "iter/sec",
            "range": "stddev: 0.00001111302076999069",
            "extra": "mean: 642.4548795486365 usec\nrounds: 797"
          }
        ]
      }
    ]
  }
}