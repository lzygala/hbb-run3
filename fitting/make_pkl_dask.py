#!/usr/bin/python  

import os
from coffea import util
from collections import defaultdict
import hist
from dask import delayed

def group(h: hist.Hist, oldname: str, newname: str, grouping: dict[str, list[str]], reg: str, syst: str):
    other_axes = [ax for ax in h.axes if ax.name != oldname]

    all_datasets = list(h.axes[oldname])
    print("Available dataset names in hist:", list(h.axes[oldname]))

    for dataset_full in all_datasets:
        dataset = dataset_full.split('_', 1)[1]
        inGroup = False
        for process in grouping:
            if dataset in grouping[process]:
                inGroup = True
            
        if not inGroup:
            print("-----WARNING-----")
            print(process, "is not included in the pmap. Ensure this isn't a mistake. Skipping process.")

    tmp_fix_grouping = {}
    for process in grouping:
        proc_inc = []
        for dataset_full in list(h.axes[oldname]):
            dataset = dataset_full.split('_', 1)[1]
            if dataset in grouping[process]:
                proc_inc.append(dataset_full)
            if proc_inc:
                tmp_fix_grouping[process] = proc_inc

    hnew = hist.Hist(
        hist.axis.StrCategory(list(tmp_fix_grouping.keys()), name=newname, growth=True),
        hist.axis.StrCategory([syst], growth=True, name="systematic", label="Systematic"),
        *other_axes,
        storage=h.storage_type,
    )
        
    for process, dataset_names in tmp_fix_grouping.items():

        matching = [ds_full for ds_full in all_datasets if ds_full in dataset_names]
        print("matching:", matching)

        if not matching:
            continue

        h_selected = h[{oldname: hist.loc(*matching)}]
        h_group = h_selected.project(*[ax.name for ax in h_selected.axes if ax.name != oldname])

        proc_idx = hnew.axes[newname].index(process)
        hnew.view(flow=True)[proc_idx] = h_group.view(flow=True)


    return hnew

def make_task(filename, region, s, pmap, xs):
    @delayed
    def _task():
        if not os.path.isfile(filename):
            return None

        out = util.load(filename)

        hist_total = None

        for k in out:
            if not (region in out[k]['templates'][{'systematic': s}].axes['region']) or not (s in out[k]['templates'][{'region': region}].axes['systematic']):
                continue
            h = out[k]['templates'][{'region': region}][{'systematic': s}]
            sumw = out[k]['sumw']

            # Normalize
            scale_lumi = {m: 1 / v for m, v in sumw.items()}
            for i, name in enumerate(h.axes['dataset']):
                if name in scale_lumi:
                    h.view(flow=True)[i] *= scale_lumi[name]

            if hist_total is None:
                hist_total = h
            else:
                hist_total += h

        del out
        # Group the per-file histogram
        if hist_total is None:
            return None
        hgrouped = group(hist_total, 'dataset', 'process', pmap, region, s)

        return hgrouped
    return _task()


def process_file(filename, region, pmap, xs):

    out = util.load(f"../outfiles/{filename}")
    for k in out:
        h = out[k]['templates']
        available_systs = list(h.axes['systematic'])
        break
    del out
    tasks_return = []

    for s in available_systs:
        tasks_return.append(make_task(filename, region, s, pmap, xs))

    return tasks_return