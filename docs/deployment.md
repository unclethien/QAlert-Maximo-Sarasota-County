# Deployment

The slide deck in `presentation/` is published with GitHub Pages.

- **URL:** https://unclethien.github.io/QAlert-Maximo-Sarasota-County/
- **How it deploys:** the workflow [`.github/workflows/deploy-presentation.yml`](../.github/workflows/deploy-presentation.yml) builds the deck and publishes `presentation/dist`. It runs on every push to `main` that changes `presentation/`, `data/`, or the workflow itself. To redeploy by hand, open the repository's **Actions** tab, pick **Deploy slide deck to GitHub Pages**, and click **Run workflow**.
- **Settings:** in the repository's **Settings → Pages**, the source is **GitHub Actions**.
- **Environment variables:** none. The deck is a static site; its numbers are read from `data/` when it is built.
- **Rollback:** revert the commit that broke the deck and push to `main`, or re-run an earlier successful run of the workflow.
