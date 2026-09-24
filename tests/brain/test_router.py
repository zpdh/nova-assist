"""Tests for :mod:`nova.brain.router`."""

from __future__ import annotations

import pytest

from nova.brain.router import ModelRouter, SingleModelRouter


def test_single_model_router_returns_model():
    router = SingleModelRouter("my-model")

    assert router.choose([]) == "my-model"


def test_single_model_router_satisfies_protocol():
    assert isinstance(SingleModelRouter("m"), ModelRouter)


def test_empty_model_rejected():
    with pytest.raises(ValueError):
        SingleModelRouter("")
