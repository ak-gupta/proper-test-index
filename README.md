# Overview

A very simple implementation of Big Randy's Proper Test Index (PTI) for U.S. Open golf.

$$PTI = \frac{\text{Number of rounds with a score of 80+}}{\text{Number of rounds with a score of <70}}$$

Available results are in `pti.csv`.

# Usage

To use this code, you'll need to have an annual Scratch Plus membership with Data Golf. Please create a
`.env` file with your API token (key `API_TOKEN`).

```bash
uv run collect.py
uv run aggregate.py
```
