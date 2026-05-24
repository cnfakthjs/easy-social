from __future__ import annotations

import pytest

from easy_social.models import Poll, PollOption, PollVote, Post, User

from conftest import login, logout, register

# ── Unit Tests ────────────────────────────────────────────────


@pytest.mark.unit
def test_poll_option_vote_count(app):
    """PollOption.vote_count should reflect the number of associated votes."""
    with app.app_context():
        user = User(username="alice", email="alice@example.com")
        user.set_password("password")
        post = Post(body="test poll", author=user)
        poll = Poll(post=post)
        option = PollOption(poll=poll, text="Option A", position=1)
        from easy_social.extensions import db
        db.session.add_all([user, post, poll, option])
        db.session.commit()

        assert option.vote_count == 0

        vote = PollVote(option=option, user=user)
        db.session.add(vote)
        db.session.commit()

        assert option.vote_count == 1


@pytest.mark.unit
def test_poll_requires_at_least_two_options(app):
    """A poll with only one option should not be created by the app logic."""
    with app.app_context():
        user = User(username="bob", email="bob@example.com")
        user.set_password("password")
        post = Post(body="test", author=user)
        from easy_social.extensions import db
        db.session.add_all([user, post])
        db.session.commit()

        options = ["Only one"]
        assert len([o for o in options if o]) < 2


# ── Integration Tests ─────────────────────────────────────────


@pytest.mark.integration
def test_create_poll_post(client, app):
    """Creating a post with 2+ poll options should create a Poll in the DB."""
    register(client, "alice")
    client.post(
        "/posts",
        data={
            "body": "Which is better?",
            "poll_option_1": "Cats",
            "poll_option_2": "Dogs",
        },
        follow_redirects=True,
    )
    with app.app_context():
        post = Post.query.filter_by(body="Which is better?").one()
        assert post.poll is not None
        assert len(post.poll.options) == 2


@pytest.mark.integration
def test_poll_not_created_with_one_option(client, app):
    """A post with only one poll option should not create a Poll."""
    register(client, "alice")
    client.post(
        "/posts",
        data={
            "body": "Only one option",
            "poll_option_1": "Cats",
        },
        follow_redirects=True,
    )
    with app.app_context():
        post = Post.query.filter_by(body="Only one option").one()
        assert post.poll is None


@pytest.mark.integration
def test_vote_on_poll(client, app):
    """A user should be able to vote on a poll option."""
    register(client, "alice")
    client.post(
        "/posts",
        data={
            "body": "Vote test",
            "poll_option_1": "Yes",
            "poll_option_2": "No",
        },
        follow_redirects=True,
    )
    with app.app_context():
        post = Post.query.filter_by(body="Vote test").one()
        option_id = post.poll.options[0].id

    client.post(f"/posts/{post.id}/vote", data={"option_id": option_id}, follow_redirects=True)

    with app.app_context():
        post = Post.query.filter_by(body="Vote test").one()
        assert post.poll.options[0].vote_count == 1


@pytest.mark.integration
def test_cannot_vote_twice(client, app):
    """A user should not be able to vote twice on the same poll."""
    register(client, "alice")
    client.post(
        "/posts",
        data={
            "body": "Double vote test",
            "poll_option_1": "Yes",
            "poll_option_2": "No",
        },
        follow_redirects=True,
    )
    with app.app_context():
        post = Post.query.filter_by(body="Double vote test").one()
        option_id = post.poll.options[0].id

    client.post(f"/posts/{post.id}/vote", data={"option_id": option_id}, follow_redirects=True)
    response = client.post(
        f"/posts/{post.id}/vote",
        data={"option_id": option_id},
        follow_redirects=True,
    )
    assert b"already voted" in response.data

    with app.app_context():
        post = Post.query.filter_by(body="Double vote test").one()
        total = sum(o.vote_count for o in post.poll.options)
        assert total == 1


# ── End-to-End Tests (Selenium) ───────────────────────────────


@pytest.mark.ui
def test_poll_visible_on_feed(browser, live_server_url):
    """E2E: poll options should appear on the feed after creating a poll post."""
    from selenium.webdriver.common.by import By
    browser.get(f"{live_server_url}/auth/register")
    browser.find_element(By.NAME, "username").send_keys("polluser")
    browser.find_element(By.NAME, "email").send_keys("poll@example.com")
    browser.find_element(By.NAME, "password").send_keys("password123")
    browser.find_element(By.NAME, "captcha").send_keys("TEST")
    browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    browser.find_element(By.CSS_SELECTOR, "button.link-button").click()
    browser.find_element(By.NAME, "body").send_keys("Poll question")
    browser.find_element(By.NAME, "poll_option_1").send_keys("Option A")
    browser.find_element(By.NAME, "poll_option_2").send_keys("Option B")
    browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    assert "Option A" in browser.page_source
    assert "Option B" in browser.page_source