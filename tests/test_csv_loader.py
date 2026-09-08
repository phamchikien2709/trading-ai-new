import pandas as pd

from rsi_fvg.data.csv_loader import load_csv
from rsi_fvg.data.mt5_loader import RATE_COLUMNS


def test_load_csv_datetime_strings(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("time,open,high,low,close\n2025-01-01 00:05:00,1,2,0,1.5\n2025-01-01 00:00:00,1,2,0,1.5\n")
    df = load_csv(p)
    assert list(df.columns) == RATE_COLUMNS
    assert df["time"].dtype == "int64"
    assert list(df["time"]) == sorted(df["time"])            # sorted ascending
    assert df["time"].iloc[0] == int(pd.Timestamp("2025-01-01 00:00:00", tz="UTC").timestamp())
    assert (df["spread"] == 0).all() and (df["tick_volume"] == 0).all()


def test_load_csv_epoch_and_dedupe(tmp_path):
    p = tmp_path / "y.csv"
    p.write_text("time,open,high,low,close,spread\n300,1,2,0,1.5,20\n300,1,2,0,1.5,20\n600,1,2,0,1.5,21\n")
    df = load_csv(p)
    assert list(df["time"]) == [300, 600] and df["spread"].iloc[1] == 21
