from __future__ import annotations

import pytest

# ── Unit Tests ────────────────────────────────────────────────
@pytest.fixture()
def client_with_captcha(app):
    """A test client that does NOT skip CAPTCHA (TESTING=False for auth)."""
    app.config["TESTING"] = False
    yield app.test_client()
    app.config["TESTING"] = True

@pytest.mark.unit
def test_captcha_image_returns_png(client):
    """CAPTCHA endpoint should return a PNG image and set session answer."""
    response = client.get("/auth/captcha-image")
    assert response.status_code == 200
    assert response.content_type == "image/png"


@pytest.mark.unit
def test_captcha_image_sets_session(client):
    """Each request to captcha-image should store an answer in the session."""
    with client.session_transaction() as sess:
        sess.clear()

    client.get("/auth/captcha-image")

    with client.session_transaction() as sess:
        assert "captcha_answer" in sess
        answer = sess["captcha_answer"]
        assert len(answer) == 4
        assert answer.isupper() or answer.isdigit() or any(c.isalpha() for c in answer)


@pytest.mark.unit
def test_captcha_answer_changes_on_refresh(client):
    """Each new request should generate a different answer."""
    client.get("/auth/captcha-image")
    with client.session_transaction() as sess:
        first = sess.get("captcha_answer")

    answers = set()
    for _ in range(5):
        client.get("/auth/captcha-image")
        with client.session_transaction() as sess:
            answers.add(sess.get("captcha_answer"))

    # 5回請求不可能全部一樣
    assert len(answers) > 1


# ── Integration Tests ─────────────────────────────────────────


@pytest.mark.integration
def test_register_fails_without_captcha(client_with_captcha):
    """Registration should fail when captcha field is empty."""
    response = client_with_captcha.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "請輸入驗證碼" in response.data.decode("utf-8")


@pytest.mark.integration
def test_register_fails_with_wrong_captcha(client_with_captcha):
    """Registration should fail when captcha answer is wrong."""
    client_with_captcha.get("/auth/captcha-image")
    with client_with_captcha.session_transaction() as sess:
        sess["captcha_answer"] = "ABCD"

    response = client_with_captcha.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha": "ZZZZ",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "驗證碼錯誤" in response.data.decode("utf-8")


@pytest.mark.integration
def test_register_succeeds_with_correct_captcha(client):
    """Registration should succeed when captcha answer is correct."""
    with client.session_transaction() as sess:
        sess["captcha_answer"] = "ABCD"

    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha": "ABCD",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Feed" in response.data


# ── End-to-End Tests (Selenium) ───────────────────────────────


@pytest.mark.ui
def test_captcha_image_visible_on_register_page(browser, live_server_url):
    """Captcha image should be visible on the registration page."""
    from selenium.webdriver.common.by import By
    browser.get(f"{live_server_url}/auth/register")
    img = browser.find_element(By.ID, "captcha-img")
    assert img.is_displayed()


@pytest.mark.ui
def test_register_fails_with_wrong_captcha_e2e(browser, live_server_url):
    """E2E: wrong captcha should show error message."""
    from selenium.webdriver.common.by import By
    browser.get(f"{live_server_url}/auth/register")
    browser.find_element(By.NAME, "username").send_keys("testuser")
    browser.find_element(By.NAME, "email").send_keys("test@example.com")
    browser.find_element(By.NAME, "password").send_keys("password123")
    browser.find_element(By.NAME, "captcha").send_keys("ZZZZ")
    browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    assert "驗證碼錯誤" in browser.page_source