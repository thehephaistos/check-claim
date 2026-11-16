"""Safety gate: the lead's confirmed and rejected lists must be safe to publish."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import check_confirmed, check_rejected, load_records, sort_results

CONFIRMED, REJECTED = sort_results(load_records())


def test_confirmed_list():
    """Every confirmed item has an aws.amazon.com link, word-for-word quotes and a trace link."""
    assert check_confirmed(CONFIRMED) == []


def test_rejected_list():
    """Every rejected item has a reason and a trace link."""
    assert check_rejected(REJECTED) == []
