import os
import pytest
from playwright.sync_api import Page
from dotenv import load_dotenv

from pages.CheckoutPage import CheckoutPage
from pages.LoginPage import LoginPage
from pages.InventoryPage import InventoryPage

pytest_plugins = ["support.allure_hooks"]

load_dotenv()

USERNAME = os.getenv("SAUCE_USERNAME")
PASSWORD = os.getenv("SAUCE_PASSWORD")
# BASE_URL is config, not a secret — it gets a default, never a raise:
BASE_URL = os.getenv("BASE_URL", "https://www.saucedemo.com/")

AUTH_STATE_PATH = "playwright/.auth/state.json"

# browser > context > page
@pytest.fixture(scope="session")
def auth_state(browser):

    # Created the path
    os.makedirs(os.path.dirname(AUTH_STATE_PATH), exist_ok=True)
    context = browser.new_context(base_url=BASE_URL)

    login_page = LoginPage(context.new_page())
    login_page.open()
    login_page.login_user(USERNAME, PASSWORD)
    # Setup guard: prove the login WORKED before saving the session.
    # Without this, a failed login saves a logged-out state.json and every
    # downstream test times out on inventory locators instead.
    login_page.page.wait_for_url("**/inventory.html")
    context.storage_state(path=AUTH_STATE_PATH)
    context.close()

    return AUTH_STATE_PATH

@pytest.fixture                            # runs per test
def logged_in_page(new_context, auth_state):
    return new_context(storage_state=auth_state).new_page()   # fresh page, already logged in
@pytest.fixture
def login_page(page: Page) -> LoginPage:
    """Fixture to login the user"""
    login_page = LoginPage(page)
    login_page.open()
    return login_page


@pytest.fixture
def inventory_page(login_page: LoginPage) -> InventoryPage:
    return login_page.login_standard_user()

@pytest.fixture
def checkout_started(inventory_page: InventoryPage) -> CheckoutPage:
    inventory_page.add_item_to_cart("sauce-labs-backpack")
    #          Inventory.open_cart() - > CartPage : CartPage.start_checkout() ->CheckoutPage
    return inventory_page.open_cart().start_checkout()

@pytest.fixture
def completed_order(checkout_started: CheckoutPage) -> CheckoutPage:
    return checkout_started.form_fill_out("Solid", "Snake", "00001").finish()


