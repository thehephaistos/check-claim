# Safety gate checks

At the end of `pipeline.py` the lead sorts every result in `logs/` into a confirmed list and a rejected list. Two checks guard that split, and the same functions run as pytest tests (`tests/test_safety.py`) and as the gate inside the pipeline:

- **Confirmed list:** every item has an `aws.amazon.com` link that is a snapshot page, at least one quote, every quote word for word on that page, and a public LangSmith trace link.
- **Rejected list:** every item has a reason and a public LangSmith trace link.

If either check fails, the pipeline prints `STOPPED`, exits with code 1 and does not write `briefing_lists.json`, so a bad item never reaches the briefing.

## Passing run (the five real results)

```
$ python -m pytest tests/test_safety.py -v -p no:warnings --tb=line
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0 -- .venv/bin/python
cachedir: .pytest_cache
rootdir: .
plugins: langsmith-0.14.12, anyio-4.15.1
collecting ... collected 2 items

tests/test_safety.py::test_confirmed_list PASSED                         [ 50%]
tests/test_safety.py::test_rejected_list PASSED                          [100%]

============================== 2 passed in 0.40s ===============================
(exit code 0)

$ python pipeline.py --lists-only
PASSED: safety gate; 2 confirmed, 3 rejected -> briefing_lists.json
(exit code 0)
```

## Stopped run (one planted bad item)

Planted item: `logs/PLANTED-01.json`, a copy of a real record marked **confirmed** but citing a third-party blog, `https://someone.medium.com/aws-quantum-region-is-coming`.

```
$ python -m pytest tests/test_safety.py -v -p no:warnings --tb=line
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0 -- .venv/bin/python
cachedir: .pytest_cache
rootdir: .
plugins: langsmith-0.14.12, anyio-4.15.1
collecting ... collected 2 items

tests/test_safety.py::test_confirmed_list FAILED                         [ 50%]
tests/test_safety.py::test_rejected_list PASSED                          [100%]

=================================== FAILURES ===================================
E   AssertionError: assert ['PLANTED-01:...on-is-coming'] == []
      
      Left contains one more item: 'PLANTED-01: confirmed with a non-aws.amazon.com link: https://someone.medium.com/aws-quantum-region-is-coming'
      
      Full diff: (-: missing in left side, +: extra in left side)
      - []
      + [
      +     'PLANTED-01: confirmed with a non-aws.amazon.com link: '
      +     'https://someone.medium.com/aws-quantum-region-is-coming',
      + ]
tests/test_safety.py:14: AssertionError: assert ['PLANTED-01:...on-is-coming'] == []
=========================== short test summary info ============================
FAILED tests/test_safety.py::test_confirmed_list - AssertionError: assert ['P...
========================= 1 failed, 1 passed in 0.41s ==========================
(exit code 1)

$ python pipeline.py --lists-only
STOPPED: safety gate failed; briefing lists not written.
  - PLANTED-01: confirmed with a non-aws.amazon.com link: https://someone.medium.com/aws-quantum-region-is-coming
(exit code 1)
```

## After removing the planted item

```
$ python -m pytest tests/test_safety.py -v -p no:warnings --tb=line
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0 -- .venv/bin/python
cachedir: .pytest_cache
rootdir: .
plugins: langsmith-0.14.12, anyio-4.15.1
collecting ... collected 2 items

tests/test_safety.py::test_confirmed_list PASSED                         [ 50%]
tests/test_safety.py::test_rejected_list PASSED                          [100%]

============================== 2 passed in 0.42s ===============================
(exit code 0)

$ python pipeline.py --lists-only
PASSED: safety gate; 2 confirmed, 3 rejected -> briefing_lists.json
(exit code 0)
```
