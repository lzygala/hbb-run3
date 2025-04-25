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

You can edit submit.py to enable the skimming option, in the definition of the processor:

```python
p = categorizer(
    year=year,
    jet_arbitration='ddb',
    ewkHcorr=False,
    systematics=False,
    skipJER=True, 
    save_skim=True, 
    skim_outpath="root://cmseos.fnal.gov//store/group/lpchbbrun3/tmp/"
    )
```

The processor will output parquet files for each of the regions defined in categorizer.py, for example:

```python
regions = {
    'signal-ggf': ['trigger','lumimask','metfilter','minjetkin','jetid','antiak4btagMediumOppHem','met','noleptons','notvbf','not2FJ'],
    'signal-vh': ['trigger','lumimask','metfilter','minjetkin','jetid','antiak4btagMediumOppHem','met','noleptons','notvbf','2FJ'],
    'signal-vbf': ['trigger','lumimask','metfilter','minjetkin','jetid','antiak4btagMediumOppHem','met','noleptons','isvbf'],
    'muoncontrol':['muontrigger','lumimask','metfilter','minjetkinmu', 'jetid',  'ak4btagMedium08', 'onemuon', 'muonkin','muonDphiAK8']
}
```
It is then straightforward to define regions and cuts in order to customize skims for individual studies.


## Processor Hist Output
Make pickle of hists:
```bash
python make-pkl.py 2022
```

Create signal region and control region hists:
```bash
python make-hists-sig.py 2022
python make-hists-cr.py 2022
```

