#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import hist
import numpy as np
import json
import os

# from coffea import util
from hbb import utils

ptbins = np.array([300, 450, 500, 550, 600, 675, 800, 1200])

axis_to_histaxis = {
    "category": hist.axis.StrCategory([], name="category", label="Category", growth=True),
    "region": hist.axis.StrCategory([], name="region", label="Region", growth=True),
    "systematic": hist.axis.StrCategory([], name="systematic", label="Systematic", growth=True),
    "pt1": hist.axis.Variable(ptbins, name="pt1", label=r"Jet 0 $p_{T}$ [GeV]"),
    "msd1": hist.axis.Regular(23, 60, 221, name="msd1", label="Jet 0 $m_{sd}$ [GeV]"),
    "mass1": hist.axis.Regular(30, 0, 200, name="mass1", label="Jet 0 PNet mass [GeV]"),
    # "TXbb": hist.axis.Regular(100,0,1.0, name="pnet1", label="Jet ParticleNet TXbb score"),
    # "TXcc": hist.axis.Regular(100,0,1.0, name="pnet2", label="Jet ParticleNet TXcc score"),
    "TXbb": hist.axis.Variable([0, 0.8, 0.9, 0.95, 1], name="pnet1", label="Jet ParticleNet TXbb score"),
    "TXcc": hist.axis.Variable([0, 0.8, 0.9, 0.95, 1], name="pnet2", label="Jet ParticleNet TXcc score"),
    "bbvcc": hist.axis.Integer(-1, 2, name="bbvcc", label="PN TXbb > PN TXcc"),
    "mjj": hist.axis.Variable([0, 1000, 2000, 13000], name="mjj", label="$m_{jj}$ [GeV]"),
    "genflavor": hist.axis.Variable([0, 1, 3, 4], name="genflavor", label="Gen. jet flavor"),
    "process": hist.axis.StrCategory([], name="process", label="Process", growth=True)
}

# add more as needed
axis_to_column = {
    "region": "region",
    "pt1": "FatJet0_pt",
    "msd1": "FatJet0_msd",
    "mass1": "FatJet0_pnetMass",
    "category": "category",
    "TXbb": "FatJet0_pnetTXbb",
    "TXcc": "FatJet0_pnetTXcc",
    "bbvcc": "FatJet0_pnetTXbbVTXcc",
    "mjj": "VBFPair_mjj",
    "genflavor": "GenFlavor",
    "process": "process",
    "systematic": "systematic"
}


def fill_ptbinned_histogram(events, region):
    """
    The histogram has a pt-binned axis for FatJet0.

    :param events: Dictionary of events loaded from parquet files.
    """

    h = hist.Hist(
        axis_to_histaxis["process"],
        axis_to_histaxis["region"],
        axis_to_histaxis["systematic"],
        axis_to_histaxis["pt1"],
        axis_to_histaxis["mjj"], 
        axis_to_histaxis["msd1"], 
        axis_to_histaxis["TXbb"],
        axis_to_histaxis["TXcc"],
        axis_to_histaxis["genflavor"],
        axis_to_histaxis["bbvcc"],
        )

    for _process_name, data in events.items():
        weight_val = data["finalWeight"].astype(float)

        ### Event selection

        # Leading FatJet
        Txbb = data["FatJet0_pnetTXbb"]
        Txcc = data["FatJet0_pnetTXcc"]
        msd = data["FatJet0_msd"]
        pt = data["FatJet0_pt"]
        genf = data["GenFlavor"]
        vmjj=data["VBFPair_mjj"]

        # Pre-selection criteria
        selection = (msd > 60) & (msd < 220) & (pt > 300) & (pt < 1200)

        h.fill(
            region=region,
            process=_process_name,
            systematic="nominal",
            msd1=msd[selection],
            pt1=pt[selection],
            mjj=vmjj[selection],
            genflavor=genf[selection],
            pnet1=Txbb[selection],
            pnet2=Txcc[selection],
            bbvcc=(Txbb[selection] > Txcc[selection]),
            weight=weight_val[selection],
        )

    return h


def main(args):
    year = args.year
    tag = args.year

    regions=["signal-ggf","signal-vbf","signal-vh","control-tt","control-zgamma"]

    path_to_dir = f"/eos/uscms/store/group/lpchbbrun3/skims/{tag}"

    # Define the columns to load for each sample
    load_columns = [
        "weight",
        "FatJet0_pt",
        "FatJet0_msd",
        # "FatJet0_pnetMass",
        "FatJet0_pnetTXbb",
        "FatJet0_pnetTXcc",
        "VBFPair_mjj",
        "GenFlavor"
    ]
    filters = None

    data_dir = Path(path_to_dir) / year

    with open('pmap_run3.json') as f:
        pmap = json.load(f)

    out_hist=None
    # Loop through each process individually to avoid loading everything at once
    for process, datasets in pmap.items():
        for reg in regions:

            events = utils.load_samples(
                data_dir,
                {process: datasets},  # Dictionary with one process
                columns=load_columns,
                region=reg,
                filters=filters
            )

            # Fill histograms with the loaded events dictionary
            h = fill_ptbinned_histogram(events, reg)
            if out_hist is None:
                out_hist = h
            else:
                out_hist += h 

    
    out_path = f"results/{tag}/{year}"
    output_file = Path(f"{out_path}/template_{year}.pkl")

    if not os.path.exists(out_path):
        os.makedirs(out_path)
    with output_file.open("wb") as f:
        pickle.dump(out_hist, f)

    print(f"Histograms saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make histograms for a given year.")
    parser.add_argument(
        "--year",
        help="year",
        type=str,
        required=True,
        choices=["2022", "2022EE", "2023", "2023BPix"],
    )
    parser.add_argument(
        "--tag",
        help="tag",
        type=str,
        required=True
    )
    args = parser.parse_args()

    main(args)
