from __future__ import annotations

import os
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path

import dask
import uproot
import yaml
from coffea.dataset_tools import apply_to_fileset, max_chunks, preprocess
from coffea.nanoevents import NanoAODSchema
from dask.distributed import performance_report
from distributed import Client
from lpcjobqueue import LPCCondorCluster

from hbb.run_utils import get_dataset_spec, get_fileset

if __name__ == "__main__":

    try:
        year = sys.argv[1]
    except IndexError:
        print("Please provide a year as an argument.")

    nano_version = "v12v2_private"
    print("year: ", year)
    local_dir = Path(__file__).resolve().parent
    print("local_dir: ", local_dir)
    yaml_path = local_dir / f"src/submit_configs/hbb_{year}.yaml"

    skim_outpath = "root://cmseos.fnal.gov//store/user/cmantill/tmp/"

    print("Running on year: ", year)
    print("Using yaml file: ", yaml_path)

    with Path(yaml_path).open() as file:
        samples_to_submit = yaml.safe_load(file)
    try:
        samples_to_submit = samples_to_submit[year]
    except Exception as e:
        raise KeyError(f"Year {year} not present in yaml dictionary") from e

    samples = list(samples_to_submit.keys())
    subsamples = []
    for sample in samples:
        subsamples.extend(samples_to_submit[sample].keys())
    print("Samples: ", samples)
    print("Subsamples: ", subsamples)

    # get full list of files
    fileset = get_fileset(
        year,
        nano_version,
        samples,
        subsamples,
    )
    print("Fileset: ", fileset)

    cluster = LPCCondorCluster(
        transfer_input_files=["src"],
        ship_env=True,
        memory="10GB",
        image="coffeateam/coffea-dask-almalinux9:latest",
        # log_directory="/uscmst1b_scratch/lpc1/3DayLifetime/workerlogs/",
    )
    cluster.adapt(minimum=1, maximum=250)

    with Client(cluster) as client:
        print(time.time())
        print("Waiting for at least one worker...")
        client.wait_for_workers(1)
        print(time.time())

        with performance_report(filename="dask-report.html"):
            # process each subsample
            for subsample in fileset:
                sub_fileset = {subsample: fileset[subsample]}
                dict_process_files = get_dataset_spec(sub_fileset)

                outpath = "outfiles/"
                Path(outpath).mkdir(parents=True, exist_ok=True)
                outfile = outpath + subsample + "_dask.coffea"
                print("Will save to: ", outfile)

                local_parquet_dir = local_dir / "outparquet"
                if local_parquet_dir.is_dir():
                    os.system(f"rm -rf {local_parquet_dir}")
                local_parquet_dir.mkdir()

                if Path(outfile).is_file():
                    print("File " + outfile + " already exists. Skipping.")
                    continue
                else:
                    print("Begin running " + outfile)
                    print(datetime.now())

                print("preprocess", dict_process_files)
                # Use preprocess from coffea
                preprocessed_available, preprocessed_total = preprocess(
                    dict_process_files,
                    align_clusters=True,
                    skip_bad_files=True,
                    recalculate_steps=False,
                    files_per_batch=1,
                    file_exceptions=(OSError,),
                    step_size=20_000,
                    save_form=False,
                    uproot_options={
                        "xrootd_handler": uproot.source.xrootd.MultithreadedXRootDSource,
                        "allow_read_errors_with_report": True,
                    },
                    step_size_safety_factor=0.5,
                )
                print(preprocessed_available)
                print(
                    "Number of files preprocessed: ",
                    len(preprocessed_available),
                    " out of ",
                    len(preprocessed_total),
                )

                # TODO: customize processor
                from hbb.processors import categorizer

                p = categorizer(
                    year=year,
                    save_skim=True,
                    skim_outpath="root://cmseos.fnal.gov//store/user/cmantill/tmp/",
                )

                full_tg, rep = apply_to_fileset(
                    data_manipulation=p,
                    fileset=max_chunks(preprocessed_available, 300),
                    schemaclass=NanoAODSchema,
                    uproot_options={
                        "allow_read_errors_with_report": (OSError, KeyError),
                        "xrootd_handler": uproot.source.xrootd.MultithreadedXRootDSource,
                        "timeout": 1800,
                    },
                )

                output, _ = dask.compute(full_tg, rep)

                # save the output to a pickle file
                with Path(outfile).open("wb") as f:
                    pickle.dump(output, f)
                print("Saved output to ", outfile)
                print(datetime.now())

                # need to combine all the files from these processors before transferring to EOS

                # # only find subfolders with parquet files
                # parquet_folders = set()
                # for parquet_file in local_parquet_dir.rglob("*.parquet"):
                #     parquet_folders.add(str(parquet_file.parent.resolve()))
                # # print("Subfolders: ", parquet_folders)

                # for folder in parquet_folders:
                #     full_path = Path(folder)
                #     region_name = full_path.name
                #     pddf = pd.read_parquet(folder)

                #     # need to write with pyarrow as pd.to_parquet doesn't support different types in
                #     # multi-index column names
                #     table = pa.Table.from_pandas(pddf)
                #     output_file = f"{skim_outpath}/{region_name}.parquet"
                #     pq.write_table(table, output_file)
                #     print("Saved parquet file to ", output_file)

    cluster.close()
