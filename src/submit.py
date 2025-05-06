from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import yaml
from dask.distributed import performance_report
from distributed import Client
from lpcjobqueue import LPCCondorCluster

cluster = LPCCondorCluster(
    transfer_input_files=["src"],
    ship_env=True,
    memory="10GB",
    image="coffeateam/coffea-dask-almalinux9:latest",
    log_directory="/uscmst1b_scratch/lpc1/3DayLifetime/workerlogs/",
)


cluster.adapt(minimum=1, maximum=250)
with Client(cluster) as client:

    print(datetime.now())
    print("Waiting for at least one worker...")
    client.wait_for_workers(1)
    print(datetime.now())

    year = sys.argv[1]
    local_dir = Path(__file__).resolve().parent
    yaml_path = local_dir / f"submit_configs/hbb_{year}.yaml"

    with performance_report(filename="dask-report.html"):

        with Path(yaml_path).open() as file:
            samples_to_submit = yaml.safe_load(file)
        try:
            samples_to_submit = samples_to_submit[year]
        except Exception as e:
            raise KeyError(f"Year {year} not present in yaml dictionary") from e

        """
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
                save_skim=True,
                skim_outpath="outparquet",
            )

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
            """

cluster.close()
