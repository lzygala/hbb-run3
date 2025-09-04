from lpcjobqueue import LPCCondorCluster
from dask.distributed import Client, progress
from make_hists_sig_dask import main
import json
import os
import uproot

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
parser.add_argument(
    "--tagger",
    help="bb or cc",
    type=str,
    required=True,
    choices=["bb","cc"],
)

args = parser.parse_args()
year = args.year
tag = args.tag
tagger = args.tagger

temp_dir = f"/store/group/lpchbbrun3/{os.environ['USER']}/plotting/{tag}/{year}/"
eos_path = f"root://cmseos.fnal.gov/{temp_dir}"

with open('pmap_run3.json') as f:
    pmap = json.load(f)


cluster = LPCCondorCluster(
    memory="10GB",
    ship_env=True,
    image="coffeateam/coffea-dask-almalinux9:latest",
    log_directory=f"/uscmst1b_scratch/lpc1/3DayLifetime/{os.environ['USER']}",
    transfer_input_files=["make_hists_sig_dask.py"],
)
cluster.adapt(minimum=1, maximum=250)


with Client(cluster) as client:
    print("Waiting for at least one worker...")
    client.wait_for_workers(1)

    print("Collecting tasks")
    tasks = main(eos_path, pmap, tagger)

    print("Computing tasks")
    futures = client.compute(tasks)


    results = []
    print("Gathering Results")
    for future_batch in partition_all(1, futures):  
        batch_results = client.gather(future_batch)
        results.extend(batch_results)

    # results = client.gather(futures)
    results = [r for r in results if r is not None]

out_path = f"{tag}/{year}"
if not os.path.exists(out_path):
    os.makedirs(out_path)
with uproot.recreate(f"{out_path}/signalregion_{tagger}.root") as fout:
    for name, histo in results:
        fout[name] = histo
