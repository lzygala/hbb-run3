#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import hist
import numpy as np
from common import common_mc, data_by_year

from hbb import utils
from axis_info import axis_to_histaxis, column_to_axis


# --- FUNCTION MODIFIED ---
# It now takes an existing histogram `h` as an argument to fill
def fill_ptbinned_histogram(events, column):
    """
    Fills a histogram with events from a single dataset.
    """
            
    h = hist.Hist(
        axis_to_histaxis[column_to_axis[column]],
        axis_to_histaxis["category"],
    )

    for _process_name, data in events.items():
        weight_val = data["finalWeight"].astype(float)
        var = data[column]

        genflavordata = data["GenFlavor"]

        # Event selection
        Txbb = data["HiggsAK8_ParTPXbbVsQCD"]
        msd = data["HiggsAK8_msd"]
        pt = data["HiggsAK8_pt"]
        pre_selection = (msd > 40) & (pt > 250)
        selection_dict = {
            "pass": pre_selection & (Txbb > 0.8),
            "fail": pre_selection & (Txbb < 0.8),
        }

        # Fill histograms
        for category, selection in selection_dict.items():
            h.fill(
                var[selection],
                # pt1=pt[selection],
                category=category,
                # genflavor=genflavordata[selection],
                weight=weight_val[selection],
            )
    return h


def main(args):
    year = args.year
    region = args.region

    MAIN_DIR = "/eos/uscms/store/group/lpchbbrun3/"
    dir_name = "lzygala/25Dec10_hvv_v15_private"
    path_to_dir = f"{MAIN_DIR}/{dir_name}/"

    load_columns = [
        "weight",
        "HiggsAK8_pt",
        "HiggsAK8_msd",
        "HiggsAK8_ParTPXbbVsQCD",
        "GenFlavor",
    ]
    for column in column_to_axis.keys():
        if column not in load_columns:
            load_columns.append(column) 
    filters = None

    histograms = {}
    data_dir = Path(path_to_dir) / year
    samples = {
        **common_mc,
        # "data": data_by_year[year],
    }

    histograms = {column: {} for column in column_to_axis.keys()}

    # --- MAIN LOOP RESTRUCTURED ---
    # Loop through each process
    for process, datasets in samples.items():
        print(f"Processing {process} for year {year}...")


        # Loop through each dataset within the process
        for dataset in datasets:
            # Load only one dataset at a time to save memory
            search_path = Path(data_dir / dataset / "parquet" / region / "nominal")
            print(f"\n[DEBUG] Script is searching for files in: {search_path}\n")

            events = utils.load_samples(
                data_dir,
                {process: [dataset]},  # Pass a list with a single dataset
                columns=load_columns,
                region=region,
                filters=filters,
            )

            if not events:
                print(f"No events found for dataset {dataset} in year {year}. Skipping.")
                continue

            for column in column_to_axis.keys():
                # Fill the histogram with the events from this single dataset
                h = fill_ptbinned_histogram(events, column)

                if h.sum() == 0:
                    continue

                if not process in histograms[column]:
                    histograms[column][process] = h
                else:
                    histograms[column][process] += h

        # --- ADDED CHECK ---
        # Only add the histogram to our dictionary if it has entries

    output_dir = Path(args.outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"histograms_{year}_{region}.pkl"

    with output_file.open("wb") as f:
        pickle.dump(histograms, f)

    print(f"Histograms saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make histograms for a given year.")
    parser.add_argument(
        "--year",
        help="year",
        type=str,
        required=True,
        choices=["2022", "2022EE", "2023", "2023BPix", "2024"],
    )
    parser.add_argument(
        "--region",
        help="region",
        type=str,
        required=True,
        choices=[
            "signal-wwh",
            "signal-zzh-1FJ",
            "signal-wzh-zzh-2FJ"
        ],
    )
    parser.add_argument(
        "--outdir", help="Output directory to save histograms.", type=str, default="histograms"
    )
    args = parser.parse_args()

    main(args)
