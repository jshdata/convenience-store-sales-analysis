from unittest.mock import Mock, create_autospec


def test_app_level_token_is_passed_as_sdk_keyword(monkeypatch):
    import slack_sdk
    from cv_store.integrations.slack.check import check_online

    bot = create_autospec(slack_sdk.WebClient, instance=True)
    socket = create_autospec(slack_sdk.WebClient, instance=True)
    factory = Mock(side_effect=[bot, socket])
    monkeypatch.setattr(slack_sdk, "WebClient", factory)
    monkeypatch.setenv("SLACK_BOT_TOKEN", "synthetic-bot-credential")
    monkeypatch.setenv("SLACK_APP_TOKEN", "synthetic-app-credential")
    check_online()
    bot.auth_test.assert_called_once_with()
    socket.apps_connections_open.assert_called_once_with(app_token="synthetic-app-credential")
