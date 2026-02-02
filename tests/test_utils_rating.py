import pytest
from app.utils import format_rating


def test_format_rating_with_reviews():
    assert format_rating(4.72, 23) == '⭐ 4.7 (23)'


def test_format_rating_no_reviews():
    assert format_rating(0.0, 0) == ''
