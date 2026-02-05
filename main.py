name: Silver Bot Auto Run

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:
  repository_dispatch:
    types: [external_cron]  # 크론잡 Body의 event_type과 일치해야 함

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install yfinance pandas requests

      - name: Run Bot
        run: python main.py

      - name: Commit and Push changes
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add portfolio_state.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "Update state" && git push)
