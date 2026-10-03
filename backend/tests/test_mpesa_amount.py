"""Part-payment amount rules for the STK push — no database needed."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.routers.mpesa import MIN_PART_PAYMENT, _resolve_pay_amount


def D(x):
    return Decimal(str(x))


def test_no_amount_means_pay_full_whole_shilling_balance():
    assert _resolve_pay_amount(None, D("10000.00")) == 10000
    assert _resolve_pay_amount(None, D("4500.75")) == 4500  # M-Pesa works in whole shillings


def test_part_payment_accepted():
    assert _resolve_pay_amount(D(2500), D("10000")) == 2500


def test_can_pay_exactly_the_balance():
    assert _resolve_pay_amount(D(10000), D("10000")) == 10000


def test_more_than_owed_rejected():
    with pytest.raises(HTTPException) as e:
        _resolve_pay_amount(D(10001), D("10000"))
    assert e.value.status_code == 422


def test_fractional_amount_rejected():
    with pytest.raises(HTTPException) as e:
        _resolve_pay_amount(D("99.50"), D("10000"))
    assert e.value.status_code == 422


def test_below_minimum_rejected_unless_it_clears_the_invoice():
    with pytest.raises(HTTPException):
        _resolve_pay_amount(D(MIN_PART_PAYMENT - 1), D("10000"))
    assert _resolve_pay_amount(D(5), D("5")) == 5  # last 5 bob is always payable


def test_balance_under_one_shilling_rejected():
    with pytest.raises(HTTPException):
        _resolve_pay_amount(None, D("0.60"))
