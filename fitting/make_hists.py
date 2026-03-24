#!/usr/bin/env python3
"""
Histogram Maker - Fully Configuration-Driven
Supports: VBF Hbb Analysis, ZGamma Validation Region

Author(s): Gabi Hamilton, Lara Zygala, Cristina Mantilla
"""

from __future__ import annotations

import argparse
import gc
import json
import pickle
from pathlib import Path

import hist
import numpy as np
import uproot

from hbb import utils
from template_utils import (
    REGION_MAP,
    get_pdf_list,
    get_scale_list,
    scalevar_process,
    perform_analysis,
    export_to_root,
    set_rootfile,
    accumulate,
    export_to_pkl
)

folder_systs = ["JES", "JER", "UES", "MuonPTScale", "MuonPTRes"]
analysis_systs = ["pdf", "scalevar7pt", "scalevar3pt"]

def fill_binned_histogram(outdict_pkl, outdict_templates,
    events, region_key, setup, args, in_syst="nominal"
):
    samples_qq = setup.get("samples_qq", [])
    
    reg_cfg = setup["categories"][region_key]
    bin_branch = reg_cfg.get("bin_branch", "FatJet0_pt")
    bin_prefix = reg_cfg.get("bin_prefix", "pt")
    bins_list = reg_cfg["bins"]

    obs = setup["observable"]
    axis_var = hist.axis.Regular(obs["nbins"], obs["min"], obs["max"], name=obs["name"], label=obs["name"])
    axis_bin = hist.axis.Variable(np.array(bins_list), name=bin_prefix)  # Replaced axis_pt
    axis_cat = hist.axis.StrCategory(["pass_bb", "pass_cc", "fail", "pass", "inclusive"], name="category")
    axis_flav = hist.axis.IntCategory([0, 1, 2, 3], name="genflavor")

    h_pkl = hist.Hist(axis_var, axis_bin, axis_cat, axis_flav)
    h_rt = hist.Hist(axis_var)

    is_folder = any(fs in in_syst for fs in folder_systs)
    is_analysis_syst = any(ts in in_syst for ts in analysis_systs)
    weight_syst = in_syst if not is_folder and not is_analysis_syst else "nominal"

    for process_name, data in events.items():
        is_data = "data" in process_name.lower()
        should_split = any(s in process_name for s in samples_qq) and not is_data

        # --- 1. WEIGHTING LOGIC ---
        if not is_data and weight_syst != "nominal" and weight_syst in data.columns:
            # Systematic weights (like btagSF) usually need normalization by sum_genWeight
            weight_val = data[weight_syst].astype(float) / data["sum_genWeight"].astype(float)
        else:
            # load_samples already calculated finalWeight (weight / sum_genWeight)
            weight_val = data["finalWeight"].astype(float)

        # --- 2. VARIABLE EXTRACTION ---
        var_col = obs["branch_name"]
        pt = data["FatJet0_pt"]

        Txcc = data["FatJet0_ParTPXccVsQCD"]
        Txbb = data["FatJet0_ParTPXbbVsQCD"]
        Txbbxcc = data["FatJet0_ParTPXbbXcc"]

        pt_min = setup.get("pt_min_scale", 450.0)
        working_point = setup.get("working_point", 0.82)

        # Robust MET extraction from the parquet record
        met_pt = np.zeros(len(data))
        if "MET" in data.columns:
            met_pt = data["MET"].pt if hasattr(data["MET"], "pt") else data["MET"]

        dphi = np.nan
        if "Photon0_phi" in data.columns and "FatJet0_phi" in data.columns:
            dphi_raw = np.abs(data["Photon0_phi"] - data["FatJet0_phi"])
            dphi = np.where(dphi_raw > np.pi, 2 * np.pi - dphi_raw, dphi_raw)

        var_series = dphi if var_col == "delta_phi_photon_jet" else data[var_col]

        genflavordata = (
            np.zeros(len(data), dtype=np.int8) if is_data else data["GenFlavor"].astype(np.int8)
        )

        # --- 3. SELECTION LOGIC ---
        basic_cuts = (var_series > obs["min"]) & (var_series < obs["max"])

        pre_selection = basic_cuts & (pt > pt_min)
        if "zgcr" in region_key:
            # Specific Z-Gamma logic from Gabi's script
            trigger = data["Photon200"] | data["Photon110EB_TightID_TightIso"]
            topo_cuts = (dphi > 2.2) & (met_pt < 50) & (data["Photon0_pt"] > 120)
            pre_selection = basic_cuts & topo_cuts & trigger & (pt > pt_min)

        selection_dict = {
            "pass_bb": pre_selection & (Txbbxcc > working_point) & (Txbb > Txcc),
            "pass_cc": pre_selection & (Txbbxcc > working_point) & (Txcc > Txbb),
            "fail": pre_selection & (Txbbxcc <= working_point),
            "pass": pre_selection & (Txbbxcc > working_point),
            "inclusive": pre_selection,
        }

        flavor_cuts = {
            "": ((genflavordata == 1) | (genflavordata == 2)),
            "bb": (genflavordata == 3),
            "c": (genflavordata == 2),
            "light": (genflavordata == 1)
        }

        # --- 4. FILLING ---
        def fill_h(name, sel):
            factor = perform_analysis(data, sel, weight_val, in_syst) if is_analysis_syst else np.ones_like(bin_branch[sel])

            h_rt.view()[:] = 0
            h_rt.fill(
                var_series[sel],
                weight=weight_val[sel] * factor,
            )
            accumulate(outdict_templates, name, h_rt)

        for category, selection in selection_dict.items():
            if args.save_pkl:
                if category in h_pkl.axes["category"]:

                    # calculate theory uncertainties based on final region acceptance
                    # Lara to Gabi : If you are cutting on these plots more in post-processing, then the theory systematics won't be correct
                    # As they need to be calculated in their final region acceptances here 
                    factor = perform_analysis(data, selection, weight_val, in_syst) if is_analysis_syst else np.ones_like(bin_branch[selection])

                    h_pkl.fill(
                        var_series[selection],
                        bin_branch[selection],  # using dynamic bin data here
                        category=category,
                        genflavor=genflavordata[selection],
                        weight=weight_val[selection] * factor,
                    )
                    accumulate(outdict_pkl, process_name, h_pkl)

            if args.save_root:
                for i in range(len(bins_list) - 1):
                    bin_cut = (bin_branch > bins_list[i]) & (bin_branch < bins_list[i+1]) & pre_selection
                    base_name = f"{region_key}_{category}_{bin_prefix}{i+1}_{process_name}"
                    splits = flavor_cuts if should_split else {"": None}

                    for suffix, flavor_mask in splits.items():
                        sel = selection & bin_cut & flavor_mask if flavor_mask is not None else selection & bin_cut
                        name = f"{base_name}{suffix}_{in_syst}"
                        fill_h(name, sel)

    return outdict_pkl, outdict_templates

def main(args):
    with Path(args.setup).open() as f:
        setup = json.load(f)
    with Path("pmap_run3.json").open() as f:
        pmap = json.load(f)
        
    do_BDT_regions = setup.get("do_BDT_regions", False)

    obs_name = setup["observable"]["name"]  # e.g., "msd"

    output_root = Path(args.outdir) / args.tag / f"fitting_{args.year}_{obs_name}.root"
    if args.save_root:
        set_rootfile(output_root)

    for region_key, reg_cfg in setup["categories"].items():
        print("\n" + "=" * 50)
        print(f"STARTING REGION: {region_key}")
        print("=" * 50)

        pkl_name = f"hists_{args.year}_{region_key}_{obs_name}_TMP.pkl"


        # Define columns to load
        cols = [
            "weight",
            "FatJet0_pt",
            "FatJet0_msd",
            "FatJet0_ParTPXbbVsQCD",
            "FatJet0_ParTPXccVsQCD",
            "FatJet0_ParTPXbbXcc",
            "GenFlavor",
        ]

        # Ensure the dynamic bin branch is loaded
        bin_branch = reg_cfg.get("bin_branch", "FatJet0_pt")
        if bin_branch not in cols:
            cols.append(bin_branch)

        obs_branch = setup["observable"]["branch_name"]
        if obs_branch not in cols:
            cols.append(obs_branch)

        # Determine Data Stream (e.g., EGammadata for zgamma)
        data_map_key = "Jetdata"
        if "zg" in region_key:
            data_map_key = "EGammadata"
            cols += [
                "Photon0_pt",
                "Photon0_phi",
                "FatJet0_phi",
                "MET",
                "Photon200",
                "Photon110EB_TightID_TightIso",
            ]
        elif "mu" in region_key:    #refactor for zmumu
            data_map_key = "Muondata"

        do_folder_systs = ["nominal"]
        if setup.get("do_systematics"):
            active_syst = setup.get("active_systematics", [])
            col_systs = [f"{s}{var}" for s in active_syst if s not in folder_systs for var in ("Up", "Down")]
            do_folder_systs = ["nominal"] + [f"{s}{var}" for s in active_syst if s in folder_systs for var in ("Up", "Down")]

        for variation in do_folder_systs:
            print(f"\n>>> Running Energy Variation Systematic Pass: {syst}")

            histograms_pkl, histograms_rt = {}, {}
            for process, datasets in pmap.items():
                isRealData = "data" in process.lower()
                if isRealData and (process != data_map_key or variation != "nominal"):
                    continue

                col_systs_proc, syst_loop = col_systs, col_systs
                if setup.get("do_systematics"):
                    if process in scalevar_process:
                        if "pdf" in col_systs:
                            col_systs_proc.append(get_pdf_list(103))
                            syst_loop.append(["pdfUp", "pdfDown"])
                        elif "scalevar" in col_systs:
                            col_systs_proc.append(get_scale_list(scalevar_process[process]))
                            syst_loop.append([f"scalevar{scalevar_process[process]}Up", f"scalevar{scalevar_process[process]}Down"])


                load_cols = cols
                if variation is not "nominal" and not isRealData:
                    load_cols = cols+col_systs_proc
                for dataset in datasets:
                    events = utils.load_samples(
                        data_dir=Path(
                            f"/eos/uscms/store/group/lpchbbrun3/skims/{args.tag}/{args.year}"
                        ),
                        samples={process: [dataset]},
                        columns=load_cols,
                        region=REGION_MAP[region_key] if not do_BDT_regions or "cr" in region_key else f"{REGION_MAP[region_key]}-BDT",
                        variation=variation,
                    )
                    if events:

                        if variation is "nominal":
                            #Lara: Why would we reload the same exact sample with the same exact columns a dozen different times? 
                            for syst in ["nominal"] + col_systs:
                                histograms_pkl = {}
                            
                                # Pass the dynamic branch
                                fill_binned_histogram(
                                    histograms_pkl,
                                    histograms_rt,
                                    events,
                                    region_key,
                                    setup,
                                    args,
                                    in_syst=syst
                                )

                                if args.save_pkl:
                                    export_to_pkl(Path(args.outdir) / pkl_name.replace("TMP", syst), histograms_pkl)

                        else:
                            fill_binned_histogram(
                                    histograms_pkl,
                                    histograms_rt,
                                    events,
                                    region_key,
                                    setup,
                                    args,
                                    in_syst=variation
                                )

                            if args.save_pkl:
                                export_to_pkl(Path(args.outdir) / pkl_name.replace("TMP", variation), histograms_pkl)

                    # Memory management within dataset loop
                    del events
                    gc.collect()

            if args.save_root:
                export_to_root(histograms_rt, output_root, data_map_key)

            gc.collect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Histogram Maker for Signal and CR")
    parser.add_argument("--year", required=True, choices=["2022", "2022EE", "2023", "2023BPix"])
    parser.add_argument("--tag", required=True, help="Tag for the skims directory (e.g., 26Feb03)")
    parser.add_argument("--setup", required=True, help="Path to setup.json file")
    parser.add_argument("--outdir", default="results", help="Directory to save ROOT files")
    parser.add_argument("--save-root", action="store_true", help="Actually write the ROOT file")
    parser.add_argument("--save-pkl", action="store_true", help="Actually write the PKL file")

    args = parser.parse_args()

    # Ensure outdir exists before starting
    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    main(args)
