from gh_status.github_client import GitHubClient


def test_github_client_init() -> None:
    client = GitHubClient("test_user", "test_token")
    assert client.username == "test_user"
    assert client.client is not None
