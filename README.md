# hbb-run3

Starting with datasets from Jennet's repo, processors drawn heavily from Connor's boostedhiggs

## Running Processor
Set up environment by following instructions at https://github.com/CoffeaTeam/lpcjobqueue/


Ensure you have a valid grid certificate.

Enable singularity
```bash
./shell coffeateam/coffea-dask-almalinux9:latest
```

Run the processor for a certain year:
```bash
python submit.py 2022
```

Make pickle of hists:
```bash
python make-pkl.py 2022
```

Create signal region and control region hists:
```bash
python make-hists-sig.py 2022
python make-hists-cr.py 2022
```

Create datacards:
```bash
python make_datacards.py
```


## Run Fitting framework

lpcjobqueu singularity is not needed, ensure you have deactivated

Micromamba is recommended for mangaing environments:
```bash
# Download the micromamba setup script (change if needed for your machine https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)
# Install: (the micromamba directory can end up taking O(1-10GB) so make sure the directory you're using allows that quota)
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)
# You may need to restart your shell
```

Create virtual environment from fit_env.yml
```bash
cd fitting
micromamba env create -f fit_env.yml --name fit_env
```

Link correct version of root:
```bash
source /cvmfs/cms.cern.ch/el9_amd64_gcc12/cms/cmssw/CMSSW_14_2_2/external/el9_amd64_gcc12/bin/thisroot.sh
```

activate environment:
```bash
micromamba activate fit_env
```

run datacard script:
```bash
python3 make_datacards.py
```
