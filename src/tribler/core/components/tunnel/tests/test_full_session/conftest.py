import asyncio

import pytest


@pytest.fixture
def event_loop():
    # We use a SelectorEventLoop on all platforms so our test suite should use a similar event loop.
    return asyncio.SelectorEventLoop()


def pytest_addoption(parser):
    parser.addoption('--tunneltests', action='store_true', dest="tunneltests",
                     default=False, help="enable tunnel tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--tunneltests"):
        # --tunneltests given in cli: do not skip GUI tests
        return
    skip_tunneltests = pytest.mark.skip(reason="need --tunneltests option to run")
    for item in items:
        if "tunneltest" in item.keywords:
            item.add_marker(skip_tunneltests)
