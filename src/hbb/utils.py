"""
Common functions for processors.

Author(s): Raghav Kansal
"""

from __future__ import annotations

import pickle
import warnings
from pathlib import Path

import awkward as ak
import numpy as np
import pandas as pd
from coffea.analysis_tools import PackedSelection

P4 = {
    "eta": "Eta",
    "phi": "Phi",
    "mass": "Mass",
    "pt": "Pt",
}


def add_selection(
    name: str,
    sel: np.ndarray,
    selection: PackedSelection,
    cutflow: dict,
    isData: bool,
    genWeights: ak.Array = None,
):
    """adds selection to PackedSelection object and the cutflow dictionary"""
    if isinstance(sel, ak.Array):
        sel = sel.to_numpy()

    selection.add(name, sel.astype(bool))
    cutflow[name] = (
        np.sum(selection.all(*selection.names))
        if isData
        # add up genWeights for MC
        else np.sum(genWeights[selection.all(*selection.names)])
    )


def load_samples(
    data_dir: Path,
    process: str,
    samples: list[str],
    year: str,
    filters: list = None,
    columns: list = None,
) -> dict[str, pd.DataFrame]:
    """
    Loads events with an optional filter.
    Divides MC samples by the total pre-skimming, to take the acceptance into account.

    Args:
        data_dir (str): path to data directory.
        samples (List[str]): list of sample names to load.
        year (str): year.
        filters (List): Optional filters when loading data.
        columns (List): Optional columns to load.

    Returns:
        Dict[str, pd.DataFrame]: Dictionary of events dataframe for each sample.
    """
    data_dir = Path(data_dir) / year
    full_samples_list = [
        p.name for p in data_dir.iterdir() if p.is_dir()
    ]  # get all directories in data_dir
    events_dict = {}

    for sample_name in samples:
        # Initialize the events list for the sample
        print("sample_name", sample_name)
        events_list = []
        # Check if sample directory exists in full_samples_list
        for sample in full_samples_list:
            if not check_selector(sample, sample_name):
                continue

            sample_path = data_dir / sample
            parquet_path, pickles_path = sample_path / "parquet", sample_path / "pickles"

            # No parquet directory?
            if not parquet_path.exists():
                warnings.warn(f"No parquet directory for {sample}!", stacklevel=1)
                continue

            print(f"Loading {sample}")
            events = pd.read_parquet(parquet_path, filters=filters, columns=columns)

            # No events?
            if not len(events):
                warnings.warn(f"No events for {sample}!", stacklevel=1)
                continue

            # Normalize by total events
            if process != "data":
                n_events = get_nevents(pickles_path, year, sample)
                events["weight_nonorm"] = events["weight"]
                events["finalWeight"] = events["weight"] / n_events
                # print(events["finalWeight"])
            else:
                events["finalWeight"] = events["weight"]

            events_list.append(events)
            print(f"Loaded {sample: <50}: {len(events)} entries")

        # Combine all DataFrames for the sample
        if events_list:
            events_dict[sample_name] = pd.concat(events_list)
        else:
            warnings.warn(f"No valid events loaded for sample {sample_name}.", stacklevel=1)

    return events_dict


def format_columns(columns: list):
    """
    Reformat input of (`column name`, `num columns`) into (`column name`, `idx`) format for
    reading multiindex columns
    """
    ret_columns = []
    for key, num_columns in columns:
        for i in range(num_columns):
            ret_columns.append(f"('{key}', '{i}')")
    return ret_columns


def get_nevents(pickles_path, year, sample_name):
    """Adds up nevents over all pickles in ``pickles_path`` directory"""
    try:
        out_pickles = [p.name for p in Path(pickles_path).iterdir()]
    except:
        return None

    file_name = out_pickles[0]
    with Path(f"{pickles_path}/{file_name}").open("rb") as file:
        try:
            out_dict = pickle.load(file)
        except EOFError:
            print(f"Problem opening {pickles_path}/{file_name}")
        nevents = out_dict[year][sample_name]["nevents"]  # index by year, then sample name

    for file_name in out_pickles[1:]:
        with Path(f"{pickles_path}/{file_name}").open("rb") as file:
            try:
                out_dict = pickle.load(file)
            except EOFError:
                print(f"Problem opening {pickles_path}/{file_name}")
            nevents += out_dict[year][sample_name]["nevents"]

    return nevents


def check_selector(sample: str, selector: str | list[str]):
    if not isinstance(selector, (list, tuple)):
        selector = [selector]

    for s in selector:
        if s.endswith("?"):
            if s[:-1] == sample:
                return True
        elif s.startswith("*"):
            if s[1:] in sample:
                return True
        else:
            if sample.startswith(s):
                return True

    return False
