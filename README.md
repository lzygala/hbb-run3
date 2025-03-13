# hbb-run3

Starting with datasets from Jennet's repo, processors drawn heavily from Connor's boostedhiggs

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
