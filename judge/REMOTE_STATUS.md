# Remote publication status

Target repository: `napolocreed/corridor-research` (private).

The GitHub account is authenticated as `napolocreed`, but the connector still receives `404 Not Found` for the private repository, lists zero accessible repositories, and reports no GitHub App installation. The local Git history is intact and exported as persistent bundles.

Required one-time GitHub setting:

1. open GitHub **Settings → Applications → Installed GitHub Apps**;
2. configure the ChatGPT GitHub app;
3. grant it repository access to `corridor-research`;
4. reconnect or refresh the GitHub connector if the repository still does not appear.

Once the repository is visible to the app, the current `main` tree can be recreated through the GitHub commit/tree API without exposing a personal token.
