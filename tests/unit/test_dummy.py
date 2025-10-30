"""
Basic test to verify pytest setup is working correctly.
"""


def test_dummy():
    """Simple test that always passes."""
    assert True


def test_basic_math():
    """Test basic arithmetic to verify test runner."""
    assert 2 + 2 == 4
    assert 10 - 5 == 5
    assert 3 * 4 == 12
