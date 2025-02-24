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


def add_selection_no_cutflow(
    name: str,
    sel: np.ndarray,
    selection: PackedSelection,
):
    """adds selection to PackedSelection object"""
    selection.add(name, ak.fill_none(sel, False))


def concatenate_dicts(dicts_list: list[dict[str, np.ndarray]]):
    """given a list of dicts of numpy arrays, concatenates the numpy arrays across the lists"""
    if len(dicts_list) > 1:
        return {
            key: np.concatenate(
                [
                    dicts_list[i][key].reshape(dicts_list[i][key].shape[0], -1)
                    for i in range(len(dicts_list))
                ],
                axis=1,
            )
            for key in dicts_list[0]
        }

    return dicts_list[0]


def select_dicts(dicts_list: list[dict[str, np.ndarray]], sel: np.ndarray):
    """given a list of dicts of numpy arrays, select the entries per array across the lists according to ``sel``"""
    return {
        key: np.stack(
            [
                dicts_list[i][key].reshape(dicts_list[i][key].shape[0], -1)
                for i in range(len(dicts_list))
            ],
            axis=1,
        )[sel]
        for key in dicts_list[0]
    }


def remove_variation_suffix(var: str):
    """removes the variation suffix from the variable name"""
    if var.endswith("Down"):
        return var.split("Down")[0]
    elif var.endswith("Up"):
        return var.split("Up")[0]
    return var


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


def _load_trig_effs(year: str, label: str, region: str):
    return correctionlib.CorrectionSet.from_file(
        f"{package_path}/corrections/data/fatjet_triggereff_{year}_{label}_{region}.json"
    )


def trigger_SF(
    year: str, events_dict: dict[str, pd.DataFrame], pnet_str: str, region: str, legacy: bool = True
):
    """
    Evaluate trigger Scale Factors
    """

    # hard code axes
    if "2023" in year:
        pt_range = [
            0.0,
            10.0,
            20.0,
            30.0,
            40.0,
            50.0,
            60.0,
            70.0,
            80.0,
            90.0,
            100.0,
            110.0,
            120.0,
            130.0,
            140.0,
            150.0,
            160.0,
            170.0,
            180.0,
            190.0,
            200.0,
            210.0,
            220.0,
            230.0,
            240.0,
            250.0,
            260.0,
            270.0,
            280.0,
            290.0,
            300.0,
            320.0,
            340.0,
            360.0,
            380.0,
            400.0,
            420.0,
            440.0,
            460.0,
            480.0,
            500.0,
            550.0,
            600.0,
            700.0,
            800.0,
            1000.0,
        ]
        xbb_range = [
            0.0,
            0.05,
            0.1,
            0.15,
            0.2,
            0.25,
            0.3,
            0.35,
            0.4,
            0.45,
            0.5,
            0.55,
            0.6,
            0.65,
            0.7,
            0.75,
            0.8,
            0.85,
            0.9,
            0.95,
            1.0,
        ]
    else:
        pt_range = [
            0.0,
            30.0,
            60.0,
            90.0,
            120.0,
            150.0,
            180.0,
            210.0,
            240.0,
            270.0,
            300.0,
            360.0,
            420.0,
            480.0,
            600.0,
            1000.0,
        ]
        xbb_range = [
            0.0,
            0.04,
            0.08,
            0.12,
            0.16,
            0.2,
            0.24,
            0.28,
            0.32,
            0.36,
            0.4,
            0.44,
            0.48,
            0.52,
            0.56,
            0.6,
            0.64,
            0.68,
            0.72,
            0.76,
            0.8,
            0.84,
            0.88,
            0.92,
            0.96,
            1.0,
        ]
    xbbv11_range = [
        0.0,
        0.05,
        0.1,
        0.15,
        0.2,
        0.25,
        0.3,
        0.35,
        0.4,
        0.45,
        0.5,
        0.55,
        0.6,
        0.65,
        0.7,
        0.75,
        0.8,
        0.85,
        0.9,
        0.95,
        1.0,
    ]
    msd_range = [
        0.0,
        5.0,
        10.0,
        20.0,
        30.0,
        40.0,
        50.0,
        60.0,
        80.0,
        100.0,
        120.0,
        150.0,
        200.0,
        250.0,
        300.0,
        350.0,
    ]

    xbb_axis = hist.axis.Variable(xbbv11_range if legacy else xbb_range, name="xbb")
    pt_axis = hist.axis.Variable(pt_range, name="pt")
    msd_axis = hist.axis.Variable(msd_range, name="msd")
    # load trigger efficiencies
    triggereff_ptmsd = _load_trig_effs(year, "ptmsd", region)
    txbb = "txbbv11" if legacy else "txbb"
    triggereff_btag = _load_trig_effs(year, txbb, region)
    eff_data = triggereff_ptmsd[f"fatjet_triggereffdata_{year}_ptmsd"]
    eff_mc = triggereff_ptmsd[f"fatjet_triggereffmc_{year}_ptmsd"]
    eff_data_btag = triggereff_btag[f"fatjet_triggereffdata_{year}_{txbb}"]
    eff_mc_btag = triggereff_btag[f"fatjet_triggereffmc_{year}_{txbb}"]

    # efficiencies per jet
    eff_data_per_jet = {}
    eff_mc_per_jet = {}

    # weight (no trigger SF)
    weight = events_dict["finalWeight"]

    # yield histogram
    totals = []
    total_errs = []

    # iterate over jets
    for jet in range(2):
        pt = events_dict["bbFatJetPt"][jet]
        msd = events_dict["bbFatJetMsd"][jet]
        xbb = events_dict[f"bbFatJet{pnet_str}"][jet]

        num_ev = pt.shape[0]

        # TODO: add matching to trigger objects
        # for now, assuming both are matched
        matched = np.ones(num_ev)

        eff_data_per_jet[jet] = {}
        eff_mc_per_jet[jet] = {}

        for var in ["nominal", "stat_up"]:
            eff_data_val = np.zeros(num_ev)
            eff_data_btag_val = np.zeros(num_ev)
            eff_mc_val = np.zeros(num_ev)
            eff_mc_btag_val = np.zeros(num_ev)

            eff_data_all = eff_data.evaluate(pt, msd, var)
            eff_data_btag_all = eff_data_btag.evaluate(xbb, var)
            eff_mc_all = eff_mc.evaluate(pt, msd, var)
            eff_mc_btag_all = eff_mc_btag.evaluate(xbb, var)

            # replace zeros (!) should belong to unmatched...
            if var == "nominal":
                eff_data_all[eff_data_all == 0] = 1.0
                eff_data_btag_all[eff_data_btag_all == 0] = 1.0
                eff_mc_all[eff_mc_all == 0] = 1.0
                eff_mc_btag_all[eff_mc_btag_all == 0] = 1.0

            eff_data_val[matched == 1] = eff_data_all[matched == 1]
            eff_data_btag_val[matched == 1] = eff_data_btag_all[matched == 1]
            eff_mc_val[matched == 1] = eff_mc_all[matched == 1]
            eff_mc_btag_val[matched == 1] = eff_mc_btag_all[matched == 1]

            eff_data_per_jet[jet][var] = eff_data_val * eff_data_btag_val
            eff_mc_per_jet[jet][var] = eff_mc_val * eff_mc_btag_val

        sf_per_jet = eff_data_per_jet[jet]["nominal"] / eff_mc_per_jet[jet]["nominal"]
        sf_err_per_jet = sf_per_jet * np.sqrt(
            (eff_data_per_jet[jet]["stat_up"] / eff_data_per_jet[jet]["nominal"]) ** 2
            + (eff_mc_per_jet[jet]["stat_up"] / eff_mc_per_jet[jet]["nominal"]) ** 2
        )
        h_yield = hist.Hist(pt_axis, msd_axis, xbb_axis)
        h_yield_err = hist.Hist(pt_axis, msd_axis, xbb_axis)
        h_yield.fill(pt, msd, xbb, weight=weight * sf_per_jet)
        h_yield_err.fill(pt, msd, xbb, weight=weight * sf_err_per_jet)

        total = np.sum(h_yield.values(flow=True))
        totals.append(total)
        total_err = np.linalg.norm(np.nan_to_num(h_yield_err.values(flow=True)))
        total_errs.append(total_err)

    """
    fill histogram with the yields, with the same binning as the efficiencies,
    then take the product of that histogram * the efficiencies and * the errors
    """
    total = np.sum(totals)
    total_err = np.linalg.norm(total_errs)

    tot_eff_data = 1 - (1 - eff_data_per_jet[0]["nominal"]) * (1 - eff_data_per_jet[1]["nominal"])
    tot_eff_mc = 1 - (1 - eff_mc_per_jet[0]["nominal"]) * (1 - eff_mc_per_jet[1]["nominal"])

    if np.any(tot_eff_data == 0):
        print("Warning: eff data has 0 values")
    if np.any(tot_eff_mc == 0):
        print("Warning: eff mc has 0 values")

    sf = tot_eff_data / tot_eff_mc

    # unc on eff: (1 - z): dz
    # z = x * y = (1-eff_1)(1-eff_2)
    # dz = z * sqrt( (dx/x)**2 + (dy/y)**2 )
    for var in ["up"]:
        dx_data = eff_data_per_jet[0][f"stat_{var}"]
        dy_data = eff_data_per_jet[1][f"stat_{var}"]
        x_data = 1 - eff_data_per_jet[0]["nominal"]
        y_data = 1 - eff_data_per_jet[1]["nominal"]
        z = x_data * y_data
        dz = z * np.sqrt((dx_data / x_data) ** 2 + (dy_data / y_data) ** 2)
        unc_eff_data = dz

        dx_mc = eff_mc_per_jet[0][f"stat_{var}"]
        dy_mc = eff_mc_per_jet[1][f"stat_{var}"]
        x_mc = 1 - eff_mc_per_jet[0]["nominal"]
        y_mc = 1 - eff_mc_per_jet[1]["nominal"]
        z = x_mc * y_mc
        dz = z * np.sqrt((dx_mc / x_mc) ** 2 + (dy_mc / y_mc) ** 2)
        unc_eff_mc = dz

        unc_sf = sf * np.sqrt((unc_eff_data / tot_eff_data) ** 2 + (unc_eff_mc / tot_eff_mc) ** 2)

    return sf, unc_sf, total, total_err