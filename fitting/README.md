### Going from skims to datacards

Still use hbb environment (make sure it has root installed)
```
micromamba activate hbb
```

Create pickled hist templates per year
```
python3 make_pkl.py --year 2022EE --tag 25July21
```

Create signal region root pass / fail histograms 
Select which tagger you want to use to define your pass and fail regions (bb or cc)
```
python3 make_hists_sig.py --year 2022EE --tag 25July21 --tagger bb
```

Create your datacards and fit your QCD MC transfer factors
```
python3 make_datacards.py --year 2022EE --tag 25July21 --tagger bb
```

