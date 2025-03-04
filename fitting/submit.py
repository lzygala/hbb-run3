import os, sys
import subprocess
import json
import uproot
import awkward as ak

from coffea import processor, util, hist
from coffea.nanoevents import NanoEventsFactory, NanoAODSchema
from boostedhiggs import VBFPlotProcessor

from distributed import Client
from lpcjobqueue import LPCCondorCluster

from dask.distributed import performance_report
from dask_jobqueue import HTCondorCluster, SLURMCluster

from datetime import datetime

env_extra = [
    f"export PYTHONPATH=$PYTHONPATH:{os.getcwd()}",
]

cluster = LPCCondorCluster(
    transfer_input_files=["../boostedhiggs"],
    ship_env=True,
    memory="8GB",
)

if not os.path.isdir('outfiles-plots/'):
    os.mkdir('outfiles-plots')

cluster.adapt(minimum=1, maximum=250)
with Client(cluster) as client:

    print(datetime.now())
    print("Waiting for at least one worker...")  # noqa
    client.wait_for_workers(1)
    print(datetime.now())

    year = sys.argv[1]

    with performance_report(filename="dask-report.html"):

        infiles = subprocess.getoutput("ls ../infiles-nano/"+year+"_*.json").split()

        for this_file in infiles:

            index = this_file.split("_")[1].split(".json")[0]
            outfile = 'outfiles-plots/'+str(year)+'_dask_'+index+'.coffea'

            
            if os.path.isfile(outfile):
                print("File " + outfile + " already exists. Skipping.")
                continue
            else:
                print("Begin running " + outfile)
                print(datetime.now())

            uproot.open.defaults["xrootd_handler"] = uproot.source.xrootd.MultithreadedXRootDSource

            p = test_processor(year=year,jet_arbitration='ddb')
            args = {'savemetrics':True, 'schema':NanoAODSchema}

            skip_bad_files = 1
            if "data" in index:
                skip_bad_files = 0
                print("Processing data. Will NOT skip bad files")
            
            output = processor.run_uproot_job(
                this_file,
                treename="Events",
                processor_instance=p,
                executor=processor.dask_executor,
                executor_args={
                    "client": client,
                    "skipbadfiles": skip_bad_files,
                    "schema": processor.NanoAODSchema,
                    "treereduction": 2,
                },
                chunksize=100000,
                maxchunks=1,
            )

            util.save(output, outfile)
            print("saved " + outfile)
            print(datetime.now())