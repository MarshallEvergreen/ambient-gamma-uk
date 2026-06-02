"""Build the full dataset and write it to a parquet file at the given path."""  # noqa: INP001

import sys
from pathlib import Path

from uk_rimnet_core import build_dataset

if __name__ == "__main__":
    output = Path(sys.argv[1])
    df = build_dataset(destination="./data")
    df.write_parquet(output)
