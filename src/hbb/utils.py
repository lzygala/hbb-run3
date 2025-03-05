"""
Common functions for processors.

Author(s): Raghav Kansal
"""

from __future__ import annotations

from __future__ import annotations

import contextlib
import pickle
import time
import warnings
from copy import deepcopy
from dataclasses import dataclass, field
from os import listdir
from pathlib import Path

import hist
import numpy as np
import pandas as pd
import vector
from hist import Hist

import awkward as ak
import numpy as np
from coffea.analysis_tools import PackedSelection

from .common_vars import (
    LUMI,
    data_key,
)

P4 = {
    "eta": "Eta",
    "phi": "Phi",
    "mass": "Mass",
    "pt": "Pt",
}


PAD_VAL = -99999


def pad_val(
    arr: ak.Array,
    target: int,
    value: float = PAD_VAL,
    axis: int = 0,
    to_numpy: bool = True,
    clip: bool = True,
):
    """
    pads awkward array up to ``target`` index along axis ``axis`` with value ``value``,
    optionally converts to numpy array
    """
    ret = ak.fill_none(ak.pad_none(arr, target, axis=axis, clip=clip), value, axis=axis)
    return ret.to_numpy() if to_numpy else ret


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

import warnings
import pandas as pd
from pathlib import Path

def load_samples(
    data_dir: Path,
    process: str,
    samples: list[str],
    year: str,
    filters: list = None,
    columns: list = None,
    load_weight_noxsec: bool = True,
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
    full_samples_list = listdir(data_dir)  # get all directories in data_dir
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
                #print(events["finalWeight"])
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


def diffload_samples(
    data_dir: Path,
    process: str,
    samples: list[str],
    year: str,
    filters: list = None,
    columns: list = None,
    load_weight_noxsec: bool = True,
    chunksize: int = 100_000  # Adjust the chunk size based on memory
):
    """
    Loads events in chunks and processes them directly to minimize memory usage.

    Args:
        data_dir (str): Path to data directory.
        samples (List[str]): List of sample names to load.
        year (str): Year of the data.
        filters (List): Optional filters when loading data.
        columns (List): Optional columns to load.
        chunksize (int): Number of rows to load per chunk.

    Returns:
        None: Processes data directly to fill histograms.
    """
    data_dir = Path(data_dir) / year
    full_samples_list = listdir(data_dir)  # Get all directories in data_dir

    for sample_name in samples:
        print(f"Processing sample: {sample_name}")
        for sample in full_samples_list:
            if not check_selector(sample, sample_name):
                continue

            sample_path = data_dir / sample
            parquet_path, pickles_path = sample_path / "parquet", sample_path / "pickles"

            if not parquet_path.exists():
                warnings.warn(f"No parquet directory for {sample}!", stacklevel=1)
                continue

            # Process each chunk directly to avoid loading entire data
            for chunk in pd.read_parquet(
                parquet_path, filters=filters, columns=columns, chunksize=chunksize
            ):
                if not len(chunk):
                    warnings.warn(f"No events for {sample}!", stacklevel=1)
                    continue

                # Normalize by total events for MC samples
                if process != "data":
                    n_events = get_nevents(pickles_path, year, sample)
                    chunk["weight_nonorm"] = chunk["weight"]
                    chunk["finalWeight"] = chunk["weight"] / n_events
                else:
                    chunk["finalWeight"] = chunk["weight"]

                # Process this chunk and fill histograms immediately
                fill_histograms(chunk, sample_name)

                # Clear memory after processing the chunk
                del chunk

            print(f"Finished processing {sample_name}")

def get_nevents(pickles_path, year, sample_name):
    """Adds up nevents over all pickles in ``pickles_path`` directory"""
    try:
        out_pickles = listdir(pickles_path)
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
