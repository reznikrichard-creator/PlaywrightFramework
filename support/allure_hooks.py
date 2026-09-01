"""Allure extras, as a pytest plugin.

Registered from conftest.py with ONE line:

    pytest_plugins = ["support.allure_hooks"]

Keeping it out of conftest.py means conftest stays about fixtures, and this
file stays about reporting. Delete the line and everything still runs — you
just get a plainer report.

What it does:
  1. attaches a screenshot, the page HTML and the URL to failing UI tests
  2. writes environment.properties so the report says what it ran against
  3. gives you attach_exchange() for API request/response bodies
"""
import os

import allure
import pytest

RESULTS_DIR = "allure-results"


# ---------------------------------------------------------------------------
# 1. Know whether the test passed.
#
# Fixtures can't see their test's outcome, so this hook stashes the report on
# the item. `result_call` is the test body; setup and teardown get their own.
# ---------------------------------------------------------------------------
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"result_{report.when}", report)


# ---------------------------------------------------------------------------
# 2. Attach the evidence when a UI test fails.
#
# autouse, so it applies to every test without anyone asking for it. It does
# nothing at all on a pass, and nothing on an API test (no `page` fixture).
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _attach_on_failure(request):
    yield

    report = getattr(request.node, "result_call", None)
    if report is None or not report.failed:
        return

    page = request.node.funcargs.get("page")
    if page is None:
        return

    try:
        allure.attach(
            page.screenshot(full_page=True),
            name="screenshot",
            attachment_type=allure.attachment_type.PNG,
        )
        allure.attach(
            page.content(),
            name="page HTML",
            attachment_type=allure.attachment_type.HTML,
        )
        allure.attach(
            page.url,
            name="URL at failure",
            attachment_type=allure.attachment_type.TEXT,
        )
    except Exception:
        # The page may already be closed. A broken attachment must never turn
        # a real failure into a confusing one.
        pass


# ---------------------------------------------------------------------------
# 3. environment.properties — the panel on the report's front page.
#
# In CI the values come from GitHub; locally they fall back to something
# readable. Written once per session, before the report is ever generated.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _allure_environment():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    values = {
        "Base.URL": os.getenv("BASE_URL", "https://www.saucedemo.com/"),
        "API.URL": "https://restful-booker.herokuapp.com",
        "Browser": "chromium",
        "Python": os.getenv("PYTHON_VERSION", "3.12"),
        "Run.by": os.getenv("GITHUB_ACTOR", "local"),
        "Branch": os.getenv("GITHUB_REF_NAME", "local"),
        "Commit": os.getenv("GITHUB_SHA", "")[:7],
    }

    with open(f"{RESULTS_DIR}/environment.properties", "w") as f:
        for key, value in values.items():
            if value:
                f.write(f"{key}={value}\n")

    yield


# ---------------------------------------------------------------------------
# 4. For API tests — attach what was actually sent and received.
#
#     from support.allure_hooks import attach_exchange
#     response = attach_exchange(booking_client.create_booking(payload))
#
# Being able to see the real payload is most of what makes an API failure
# diagnosable without rerunning it.
# ---------------------------------------------------------------------------
def attach_exchange(response):
    """Attach a requests.Response and the request that produced it."""
    request = response.request

    allure.attach(
        f"{request.method} {request.url}",
        name="request",
        attachment_type=allure.attachment_type.TEXT,
    )
    if request.body:
        body = request.body
        allure.attach(
            body if isinstance(body, str) else body.decode(errors="replace"),
            name="request body",
            attachment_type=allure.attachment_type.JSON,
        )
    allure.attach(
        f"{response.status_code} in {response.elapsed.total_seconds():.2f}s",
        name="response status",
        attachment_type=allure.attachment_type.TEXT,
    )
    allure.attach(
        response.text,
        name="response body",
        attachment_type=allure.attachment_type.JSON,
    )
    return response
