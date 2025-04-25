import os, sys
import subprocess
import json
import uproot
import dask

from coffea import  util
from coffea.nanoevents import NanoAODSchema
from coffea.dataset_tools import apply_to_fileset, max_chunks, preprocess
# from boostedhiggs import VBFProcessor

from distributed import Client
from lpcjobqueue import LPCCondorCluster

from src.hbb.processors import categorizer

from dask.distributed import performance_report

from datetime import datetime
from pathlib import Path

env_extra = [
    f"export PYTHONPATH=$PYTHONPATH:{os.getcwd()}",
]

cluster = LPCCondorCluster(
    transfer_input_files=["src"],
    ship_env=True,
    memory="10GB",
    image="coffeateam/coffea-dask-almalinux9:latest",
    log_directory="/uscmst1b_scratch/lpc1/3DayLifetime/workerlogs/"
)


cluster.adapt(minimum=1, maximum=250)
with Client(cluster) as client:

    print(datetime.now())
    print("Waiting for at least one worker...")  # noqa
    client.wait_for_workers(1)
    print(datetime.now())

    year = sys.argv[1]

    with performance_report(filename="dask-report.html"):

        infiles = subprocess.getoutput("ls infiles/"+year+"/"+year+"_*.json").split()

        for this_file in infiles:

            index = this_file.split("_")[1].split(".json")[0]
            outpath = "outfiles/"
            Path(outpath).mkdir(parents=True, exist_ok=True)
            outfile = outpath+str(year)+'_dask_'+index+'.coffea'
            
            
            if os.path.isfile(outfile):
                print("File " + outfile + " already exists. Skipping.")
                continue
            else:
                print("Begin running " + outfile)
                print(datetime.now())

            p = categorizer(
                year=year,
                jet_arbitration='ddb',
                ewkHcorr=False,
                systematics=False,
                skipJER=True, 
                save_skim=True, 
                skim_outpath="root://cmseos.fnal.gov//store/group/lpchbbrun3/tmp/"
                )
            args = {'savemetrics':True, 'schema':NanoAODSchema}

            dict_process_files = {}
            nFiles = 0
            with open(this_file) as json_file:
                dict_files = json.load(json_file)

                for key in dict_files:
                    dict_samp = {}
                    dict_samp["files"] = {}
                    for file in dict_files[key]:
                        dict_samp["files"][file] = "Events"
                        nFiles += 1
                    if not dict_samp["files"]:
                        continue
                    dict_process_files[key] = dict_samp

            print("preprocessing: ", nFiles, " files")
            preprocessed_available, preprocessed_total = preprocess(
                dict_process_files,
                align_clusters=True,
                skip_bad_files=True,
                recalculate_steps=False,
                files_per_batch=1,
                file_exceptions=(OSError,),
                step_size=20_000,
                save_form=False,
                uproot_options={"xrootd_handler": uproot.source.xrootd.MultithreadedXRootDSource, "allow_read_errors_with_report": True},
                step_size_safety_factor=0.5,
            )

            full_tg, rep = apply_to_fileset(data_manipulation=p,
                            fileset=max_chunks(preprocessed_available, 300),
                            schemaclass=NanoAODSchema,
                            uproot_options={
                                "allow_read_errors_with_report": (OSError, KeyError), 
                                "xrootd_handler": uproot.source.xrootd.MultithreadedXRootDSource,
                                "timeout": 1800,
                                },
                        )
            


            output, rep = dask.compute(full_tg, rep)

            util.save(output, outfile)
            print("saved " + outfile)
            print(datetime.now())

cluster.close()