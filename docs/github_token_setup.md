# GitHub Personal Access Token Setup

To crawl public GitHub repositories at scale, IMPACT requires a GitHub Personal Access Token (PAT). Unauthenticated requests to the GitHub API are capped at 60 requests per hour, whereas authenticated requests allow up to 5,000 requests per hour.

Here is how you can obtain and configure your token:

## 1. How to Generate a Personal Access Token (Classic)

1. Log in to your account on [GitHub](https://github.com).
2. Click your profile picture in the top-right corner and select **Settings**.
3. Scroll to the bottom of the left sidebar and click **Developer settings**.
4. In the left sidebar under **Personal access tokens**, click **Tokens (classic)**.
5. Click the **Generate new token** dropdown and select **Generate new token (classic)**.
6. Provide a descriptive name in the **Note** field (e.g., `IMPACT Crawler`).
7. Select an **Expiration** date (e.g., 30 days, or "No expiration" if only using it locally).
8. **Scopes**: Do not select any checkboxes/scopes. Leaving all scopes unchecked creates a read-only token, which is the safest and sufficient permission level for public crawler tasks.
9. Scroll to the bottom and click **Generate token**.
10. **Copy the token immediately** (it will start with `ghp_...`). You will not be able to see it again once you navigate away from the page.

---

## 2. Configure Local Environment

1. Create a `.env` file in the root of the project by copying the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Open the `.env` file and set the `GITHUB_TOKEN` variable to your copied token:
   ```env
   GITHUB_TOKEN=ghp_yourTokenHere
   ```

Both the local dashboard and ecosystem crawler will automatically detect the `.env` file and use this token for all outgoing GitHub API calls.
