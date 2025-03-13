#!/usr/bin/python  

import os, sys
import subprocess
import json
import awkward as ak
import numpy as np
from coffea import processor, util
from collections import defaultdict
import hist
import pickle
import dask_awkward as dak


def group(h: hist.Hist, oldname: str, newname: str, grouping: dict[str, list[str]]):
    hnew = hist.Hist(
        hist.axis.StrCategory(grouping, name=newname),
        *(ax for ax in h.axes if ax.name != oldname),
        storage=h.storage_type,
    )

    tmp_fix_grouping = {}
    for process in grouping:
        proc_inc = []
        for dataset in list(h.axes[oldname]):
            if dataset in grouping[process]:
                proc_inc.append(dataset)
            if proc_inc:
                tmp_fix_grouping[process] = proc_inc

    for i, indices in enumerate(tmp_fix_grouping.values()):
        hnew.view(flow=True)[i] = h[{oldname: indices}][{oldname: sum}].view(flow=True)

    return hnew

# Main method
def main():

    if len(sys.argv) < 2:
        print("Enter year")
        return 

    year = sys.argv[1]

    with open('../xsec.json') as f:
        xs = json.load(f)
        
    with open('../pmap.json') as f:
        pmap = json.load(f)

    with open('../lumi.json') as f:
        lumis = json.load(f)
            
    indir = "../outfiles-test/"
    infiles = subprocess.getoutput("ls "+indir+year+"_dask_*.coffea").split()
    outsum = defaultdict()

    # Check if pickle exists, remove it if it does
    picklename = str(year)+'/templates.pkl'
    if os.path.isfile(picklename):
        os.remove(picklename)

    started = 0
    for filename in infiles:

        print("Loading "+filename)

        if os.path.isfile(filename):
            out = util.load(filename)

            for k in out:

                if started == 0:
                    outsum['templates'] = out[k]['templates']
                    outsum['sumw'] = out[k]['sumw']
                    started += 1
                else:
                    outsum['templates'] += out[k]['templates']
                    outsum['sumw'] = {m: outsum['sumw'].get(m, 0) + out[k]['sumw'].get(m, 0) for m in set(outsum['sumw']) | set(out[k]['sumw'])}

            del out

    scale_lumi = {k: xs[k] * 1000 * lumis[year] / w for k, w in outsum['sumw'].items()} 

    for i, name in enumerate(outsum['templates'].axes['dataset']):
        if not name in scale_lumi.keys():
            continue
        print(name)
        outsum['templates'].view(flow=True)[i] = outsum['templates'].view(flow=True)[i] * scale_lumi[name].compute()

    templates = group(outsum['templates'], 'dataset', 'process', pmap)

    del outsum
          
    outfile = open(picklename, 'wb')
    pickle.dump(templates, outfile, protocol=-1)
    outfile.close()

    return

if __name__ == "__main__":

    main()