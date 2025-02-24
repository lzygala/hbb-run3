"""
Runs coffea processors on the LPC via either condor or dask.

Author(s): Cristina Mantilla Suarez, Raghav Kansal
"""

from __future__ import annotations

import argparse
import os
import pickle
from pathlib import Path

import numpy as np
import uproot
import yaml
from coffea import nanoevents, processor

from hbb import run_utils
from hbb.common_vars import DATA_SAMPLES

def run(p: processor, fileset: dict, skipbadfiles: bool, args):
    """Run processor without fancy dask (outputs then need to be accumulated manually)"""
    run_utils.add_mixins(nanoevents)  # update nanoevents schema

    # outputs are saved here as pickles
    outdir = "./outfiles"
    os.system(f"mkdir -p {outdir}")

    save_parquet = True
    save_root = False

    if save_parquet or save_root:
        # these processors store intermediate files in the "./outparquet" local directory
        local_dir = Path().resolve()
        local_parquet_dir = local_dir / "outparquet"

        if local_parquet_dir.is_dir():
            os.system(f"rm -rf {local_parquet_dir}")

        local_parquet_dir.mkdir()

    uproot.open.defaults["xrootd_handler"] = uproot.source.xrootd.MultithreadedXRootDSource

    if args.executor == "futures":
        executor = processor.FuturesExecutor(status=True)
    else:
        executor = processor.IterativeExecutor(status=True)

    run = processor.Runner(
        executor=executor,
        savemetrics=True,
        schema=nanoevents.NanoAODSchema,
        chunksize=args.chunksize,
        maxchunks=None if args.maxchunks == 0 else args.maxchunks,
        skipbadfiles=skipbadfiles,
    )

    # try file opening 3 times if it fails
    for i in range(3):
        try:
            out, metrics = run(fileset, "Events", processor_instance=p)
            break
        except FileNotFoundError as e:
            import time

            print("Error!")
            print(e)
            if i < 2:
                print("Retrying in 1 minute")
                time.sleep(60)
            else:
                raise e

    with Path(f"{outdir}/{args.starti}-{args.endi}.pkl").open("wb") as f:
        pickle.dump(out, f)

    # need to combine all the files from these processors before transferring to EOS
    # otherwise it will complain about too many small files
    if save_parquet or save_root:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq

        pddf = pd.read_parquet(local_parquet_dir)

        if save_parquet:
            # need to write with pyarrow as pd.to_parquet doesn't support different types in
            # multi-index column names
            table = pa.Table.from_pandas(pddf)
            pq.write_table(table, f"{local_dir}/{args.starti}-{args.endi}.parquet")

        if save_root and args.save_root:
            import awkward as ak

            with uproot.recreate(
                f"{local_dir}/nano_skim_{args.starti}-{args.endi}.root", compression=uproot.LZ4(4)
            ) as rfile:
                rfile["Events"] = ak.Array(
                    # take only top-level column names in multiindex df
                    run_utils.flatten_dict(
                        {key: np.squeeze(pddf[key].values) for key in pddf.columns.levels[0]}
                    )
                )


def main(args):
    p = run_utils.get_processor(
        args.processor,
        args.save_array,
        args.nano_version,
    )
    print(p)

    skipbadfiles = True

    if len(args.files):
        fileset = {f"{args.year}_{args.files_name}": args.files}
        skipbadfiles = False  # not added functionality for args.files yet
    else:
        if args.yaml:
            with Path(args.yaml).open() as file:
                samples_to_submit = yaml.safe_load(file)
            try:
                samples_to_submit = samples_to_submit[args.year]
            except Exception as e:
                raise KeyError(f"Year {args.year} not present in yaml dictionary") from e

            samples = samples_to_submit.keys()
            subsamples = []
            for sample in samples:
                subsamples.extend(samples_to_submit[sample].get("subsamples", []))
        else:
            samples = args.samples
            subsamples = args.subsamples

        fileset = run_utils.get_fileset(
            args.processor,
            args.year,
            args.nano_version,
            samples,
            subsamples,
            args.starti,
            args.endi,
        )

        # don't skip "bad" files for data - we want it throw an error in that case
        for key in fileset:
            if key in DATA_SAMPLES:
                skipbadfiles = False

    print(f"Running on fileset {fileset}")
    if args.executor == "dask":
        run_dask(p, fileset, args)
    else:
        run(p, fileset, skipbadfiles, args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    run_utils.parse_common_args(parser)
    parser.add_argument("--starti", default=0, help="start index of files", type=int)
    parser.add_argument("--endi", default=-1, help="end index of files", type=int)
    parser.add_argument(
        "--executor",
        type=str,
        default="iterative",
        choices=["futures", "iterative", "dask"],
        help="type of processor executor",
    )
    parser.add_argument(
        "--files", default=[], help="set of files to run on instead of samples", nargs="*"
    )
    parser.add_argument(
        "--files-name",
        type=str,
        default="files",
        help="sample name of files being run on, if --files option used",
    )
    parser.add_argument("--yaml", default=None, help="yaml file", type=str)

    args = parser.parse_args()

    main(args)
