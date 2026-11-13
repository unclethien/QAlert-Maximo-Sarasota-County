# Deployment

Two slide decks are published together with GitHub Pages.

- **URLs:**
  - Dataset deck (`presentation/`): https://unclethien.github.io/QAlert-Maximo-Sarasota-County/
  - Similarity and data pipeline deck (`assets/showoff/sarasota-similarity-data-pipeline/`): https://unclethien.github.io/QAlert-Maximo-Sarasota-County/similarity-pipeline/
- **How it deploys:** the workflow [`.github/workflows/deploy-presentation.yml`](../.github/workflows/deploy-presentation.yml) builds the dataset deck into `presentation/dist`. It then copies the similarity deck's `index.html`, `css/`, `js/` and `fonts/` into `presentation/dist/similarity-pipeline/` and publishes the folder. The speaker script `content.md` is not published, and the `images/` captures are git-ignored, so they stay local. The workflow runs on every push to `main` that changes `presentation/`, `data/`, the similarity deck, or the workflow itself. To redeploy by hand, open the repository's **Actions** tab, pick **Deploy slide deck to GitHub Pages**, and click **Run workflow**.
- **Settings:** in the repository's **Settings → Pages**, the source is **GitHub Actions**.
- **Environment variables:** none. Both decks are static sites. The dataset deck reads its numbers from `data/` when it is built; the similarity deck is copied as it is.
- **Rollback:** revert the commit that broke a deck and push to `main`, or re-run an earlier successful run of the workflow.
