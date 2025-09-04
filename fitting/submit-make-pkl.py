from lpcjobqueue import LPCCondorCluster
from distributed import Client
from make_pkl_dask import process_file
import os
import pickle
import json
import subprocess

import argparse

def partition_all(n, iterable):
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
    required=True,
)

args = parser.parse_args()
year = args.year

with open('pmap_run3.json') as f:
    pmap = json.load(f)

with open('xsec.json') as f:
    xs = json.load(f)

indir = "../outfiles/bbvcc/"
infiles_raw = subprocess.getoutput(f"ls {indir}{year}_*_dask*.coffea").split()
infiles = [s.replace("../outfiles/", "./") for s in infiles_raw]
keep_regions = ["signal-all", "signal-ggf", "signal-vh", "signal-vbf",
                "control-tt", "control-zgamma"
                ]

temp_dir = f"/store/group/lpchbbrun3/{os.environ['USER']}/plotting/{tag}/{year}/"
eos_path = f"root://cmseos.fnal.gov/{temp_dir}"

cluster = LPCCondorCluster(
    memory="10GB",
    ship_env=True,
    image="coffeateam/coffea-dask-almalinux9:latest",
    log_directory=f"/uscmst1b_scratch/lpc1/3DayLifetime/{os.environ['USER']}",
    transfer_input_files=[indir, "make_pkl_dask.py"],
)
cluster.adapt(minimum=1, maximum=250)

with Client(cluster) as client:
    print("Waiting for at least one worker...")
    client.wait_for_workers(1)

    print("Collecting tasks")
    for region in keep_regions:
        tasks = []
        for f in infiles:

            tasks += process_file(f, region, pmap, xs)

            tasks = [r for r in tasks if r is not None]

        print("Submitting tasks")
        futures = client.compute(tasks)

        results = []
        print("Gathering Results")
        for future_batch in partition_all(1, futures): 
            batch_results = client.gather(future_batch)
            results.extend(batch_results)
        # results = client.gather(futures)

        
        print("Merging Hists")
        region_hists = [r for r in results if r is not None]
        if region_hists:
            final_hist = region_hists[0]
            for h in region_hists[1:]:
                final_hist += h
        else:
            final_hist = None
        

        
        outname = f"{year}/templates_{region}.pkl"
        os.makedirs(os.path.dirname(outname), exist_ok=True)

        print("Pickling File")
        with open(outname, 'wb') as f:
            pickle.dump(final_hist, f, protocol=-1)

        print(f"[DASK] Final grouped histogram saved: {outname}")

client.close()