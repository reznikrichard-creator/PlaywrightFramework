# Playwright + Pytest — UI and API Test Framework

[Tests](/actions/workflows/tests.yml/badge.svg)

An automated test suite for a web shop and a REST API, written in Python with Playwright and
pytest. It runs on every push through GitHub Actions and publishes a report anyone can open.

**Live test report:** *insert after completion

| | |
|---|---|
| **Under test** | [Swag Labs](https://www.saucedemo.com/) (browser) · [restful-booker](https://restful-booker.herokuapp.com/apidoc/index.html) (REST API) |
| **Stack** | Python 3.12 · Playwright · pytest · requests · pytest-html · Allure |
| **Patterns** | Page Object Model · service objects · fixtures · data builders |
| **CI** | GitHub Actions on every push, with screenshots, videos and traces kept on failure |

---

## Running it

```bash
git clone https://github.com/<your-username>/pliskin_june11.git
cd pliskin_june11

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium        # the browser is a separate download

python -m pytest
```

Common variations:

```bash
python -m pytest --headed              # watch the browser work
python -m pytest tests/api             # API tests only
python -m pytest -k checkout           # anything matching "checkout"
python -m pytest --setup-show          # show fixtures being built and torn down
```

Every run writes `report.html`. Failures also leave a screenshot, a video and a Playwright trace
in `test-results/`.

---

## Layout

```
pages/                  One class per screen of the website
  LoginPage.py            locators and actions, no assertions
  InventoryPage.py
  CartPage.py
  CheckoutPage.py

api/                    The same idea, applied to endpoints
  booking_client.py       one method per endpoint, no assertions
  builders.py             make_booking() — valid payloads with unique data

tests/                  UI tests
tests/api/              API tests, with their own conftest.py

conftest.py             Shared fixtures for the UI suite
pytest.ini              Base URL, browser, artefact settings
.github/workflows/      tests.yml — the CI pipeline
```

---

## Design choices

**Page objects hold locators and actions. Tests hold the assertions.**
A page object can hand back a locator, but it never decides whether something is correct. That
keeps each class reusable — one `get_error_message()` serves twenty tests checking twenty different
things, where an `expect_error()` would serve one.

**Page objects are stateless.**
They store the `page` and their locators, and nothing else. No cached totals, no saved usernames,
no current-step counter. Every question goes back to the live browser, so nothing can go stale and
no data can leak from one test into the next. The state lives in the browser; the page object is
only a map of how to reach it.

**Methods return the next screen.**
`login_user()` returns an `InventoryPage`, `open_cart()` returns a `CartPage`. Methods that stay put
return `self`. Tests then read like the journey a user takes:

```python
cart_page = login_page.login_user(user, pw).add_item_to_cart("backpack").open_cart()
```

**Setup lives in fixtures, not at the top of every test.**
The login sequence used to be copy-pasted into fifteen tests. It now sits in `conftest.py`, and
fixtures build on each other:

```
page → login_page → inventory_page → checkout_started → completed_order
```

**The API suite follows the same rules as the UI suite.**
`BookingApiClient` is a page object for endpoints — one method per call, no assertions inside it.
`make_booking()` produces valid payloads with a unique name each time, so parallel or repeated runs
can never collide over the same record.

**Tests create their own data and clean it up.**
The `created_booking` fixture creates a booking, hands it to the test, and deletes it afterwards —
including when the test fails. The suite can be run twice in a row and leave the server as it found
it.

**Secrets stay out of the repository.**
Credentials come from `.env` locally and from repository secrets in CI. Neither is ever committed.

---

## Rules this project follows

1. Page objects and API clients never assert. Tests decide what "correct" means.
2. Page objects store no data — the browser holds the state.
3. A method that changes screen returns the new screen's object; one that doesn't returns `self`.
4. Setup that isn't what the test is about belongs in a fixture.
5. Every test creates its own data and cleans it up.
6. Secrets never go in the code or in git.
7. A test that cannot fail is worse than no test.

---
---

## In more detail

Everything below explains how the pieces work. The sections above are enough to run the suite and
understand the shape of it.

### How a test run works

One command does all of this:

1. **`pytest.ini` sets the defaults** — the site address (`base_url`), which browser to use, and what
   to save when something fails. It means the common options never have to be typed.

2. **pytest collects the tests** — it walks the folders and finds every `test_*.py` file, and inside
   them every `test_*` function. Nothing is registered by hand.

3. **Every `conftest.py` on the way is read.** `conftest.py` is a special filename that is never
   imported — pytest finds it by location, and its contents are available to every test in that
   folder and below. There are two: one at the root for the UI suite, one in `tests/api/`.

4. **Each test asks for what it needs, by name.** A test written `def test_cart(inventory_page):`
   causes pytest to find the fixture called `inventory_page`, run it, and pass in the result.

5. **Results are written out** — `report.html` every time, plus screenshots, video and a trace when
   something fails.

### Page objects

Without them, a test carries its own selectors:

```python
page.locator('[data-test="username"]').fill("standard_user")
page.locator('[data-test="password"]').fill("secret_sauce")
page.locator('[data-test="login-button"]').click()
```

If a developer renames that button, every test that clicks it breaks and each one has to be found
and fixed. With a page object the selectors live in one class, and the test reads:

```python
inventory_page = login_page.login_user("standard_user", "secret_sauce")
```

One rename, one file, one line.

The class itself holds only locators and the actions that use them:

```python
class LoginPage:
    def __init__(self, page):
        self.page = page
        self.username = page.locator('[data-test="username"]')
        self.password = page.locator('[data-test="password"]')
        self.login_button = page.locator('[data-test="login-button"]')

    def login_user(self, username, password):
        self.username.fill(username)
        self.password.fill(password)
        self.login_button.click()
        return InventoryPage(self.page)     # a new screen, so a new page object
```

Assertions stay out of it. The page hands over a locator and the test judges it:

```python
expect(login_page.get_error_message()).to_contain_text("Username is required")
```

### Fixtures

A fixture prepares something and hands it to a test. These two live in `conftest.py`:

```python
@pytest.fixture
def login_page(page):
    login_page = LoginPage(page)
    login_page.open()
    return login_page

@pytest.fixture
def inventory_page(login_page):
    return login_page.login_user(USERNAME, PASSWORD)
```

The second one asks for the first as an argument — fixtures can use other fixtures, and pytest
builds the chain in order. A test that only needs to be logged in is then two lines:

```python
def test_inventory_shows_six_items(inventory_page):
    expect(inventory_page.get_items()).to_have_count(6)
```

`page` is a fixture too — it comes from `pytest-playwright` and supplies a fresh browser tab.
Running `python -m pytest --setup-show` prints the whole chain as it is built and torn down.

### The API suite

API tests take milliseconds where browser tests take seconds, and they ignore layout, spinners and
animation entirely. When both fail, the API test usually says *what* broke and the browser test says
*what the user sees*.

`ApiSession` adds the two things `requests` doesn't do on its own — a base address on every URL, and
a timeout so a hung request can't freeze the suite:

```python
class ApiSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 10)
        return super().request(method, BASE_URL + url, **kwargs)
```

`BookingApiClient` wraps it, one method per endpoint, returning the raw response every time:

```python
def create_booking(self, payload):
    return self.session.post("/booking", json=payload)

def delete_booking(self, booking_id):
    return self.session.delete(f"/booking/{booking_id}", headers=self._auth_headers())
```

It never says whether a response was good. The test does:

```python
def test_created_booking_can_be_read(booking_client):
    booking_id = booking_client.create_booking(make_booking()).json()["bookingid"]
    assert booking_client.get_booking(booking_id).status_code == 200
```

`make_booking()` returns a complete valid payload, with keyword arguments overriding any field:

```python
make_booking()                     # valid
make_booking(firstname="Meryl")    # one field changed
make_booking(totalprice=-5)        # deliberately invalid, for negative tests
```

Each payload gets a random unique name such as `qa-3f9a17c2`. The test API is shared, so two people
running the suite at once would otherwise both create "John Smith" — and a test searching for that
name would find two records and fail for no real reason.

### Cleaning up

```python
@pytest.fixture
def created_booking(booking_client):
    payload = make_booking()
    booking_id = booking_client.create_booking(payload).json()["bookingid"]

    yield booking_id, payload                    # the test runs here

    booking_client.delete_booking(booking_id)    # runs even if the test failed
```

Everything before `yield` is setup; everything after it is cleanup, and cleanup runs whatever the
outcome. Two rules apply to it: no assertions after `yield`, because a failing teardown hides the
real result — and "it's already gone" counts as success, since some tests delete their own data.

### The CI pipeline

Every push starts a fresh Ubuntu machine that clones the repo, installs everything from scratch and
runs the suite. Nothing on it survives the run, which is what makes the result meaningful — there
are no leftover files and no local configuration to lean on.

```yaml
name: Tests
on: push

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4          # copy the repo onto the machine
      - uses: actions/setup-python@v5      # install Python
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: playwright install --with-deps chromium
      - name: Run tests
        run: xvfb-run python -m pytest     # a fake screen; the runner has no monitor
```

Two steps exist purely because of the environment: `playwright install` downloads the browser, which
`pip` does not, and `xvfb-run` supplies the display Chromium expects even in headless mode.

Because the machine is deleted afterwards, anything worth keeping has to be uploaded first:

```yaml
      - name: Upload report and artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-report-${{ github.run_number }}
          path: |
            report.html
            test-results/
          if-no-files-found: ignore
```

`if: always()` matters more than it looks. A step is normally skipped once something has failed,
which is exactly when the screenshot and the trace are needed.

To investigate a failed run, download that artifact and open `report.html`, or drop
`test-results/**/trace.zip` onto [trace.playwright.dev](https://trace.playwright.dev). A trace
records every action with the page state before and after it, plus network and console output.

---

## Troubleshooting

| Problem | Cause |
|---|---|
| `ModuleNotFoundError: No module named 'pages'` | Run from the project root, using `python -m pytest` |
| `Executable doesn't exist at .../chrome` | The browser wasn't downloaded — run `playwright install chromium` |
| Passes locally, fails in CI | A package missing from `requirements.txt`, an uncommitted file, or a test depending on another test's data |
| An API test fails intermittently | restful-booker is a free shared server: it sleeps when idle and resets its data every few minutes |
| A test only passes with the whole file | It depends on another test — each one must work alone, in any order |
