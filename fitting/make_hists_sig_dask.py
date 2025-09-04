#!/usr/bin/python  

import pickle
from dask import delayed
import subprocess

def make_task(eos_path, region, p, name, selection_dict):
    @delayed
    def _task():

        local_file = "./templates.pkl"
        eos_file = f"{eos_path}/templates_signal-{region}.pkl"
        cmd = ["xrdcp", "-f", eos_file, local_file]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
        with open(local_file, "rb") as f:
            h = pickle.load(f)

        if p not in h.axes["process"]:
            return None

        s = "nominal"
        filter_args = {
            "pt1": {'pt1': sum},
            "genflavor": {'genflavor': sum},
            "mjj": {'mjj': sum},
            "pnet1": {'pnet1': sum},
            "pnet2": {'pnet2': sum},
            "bbvcc": {'bbvcc': sum},
            "process": {'process': p},
            "systematic": {'systematic': s},
        }

        for key, val in selection_dict.items():
            if key not in filter_args:
                print(f"Missing key in hist: {key}")
                return None
            filter_args[key][key] = val

        try:
            sliced = h[
                filter_args["pt1"]][filter_args["genflavor"]][filter_args["mjj"]][
                filter_args["pnet1"]][filter_args["pnet2"]][filter_args["process"]][
                filter_args["systematic"]][filter_args["bbvcc"]
            ]
        except Exception as e:
            print(f"Failed slicing {name}: {e}")
            return None

        return f"{name}_{s}", sliced

    return _task()

# Main method
def main(infile, pmap, tagger):

    samples_all = pmap.keys()
    samples_2 = ['Wjets','Zjets','EWKW','EWKZ','EWKV']
    samples = [x for x in samples_all if x not in samples_2]

    mjjbins = [1000j,2000j,13000j]
    ptbins = [450j, 500j, 550j, 600j, 675j, 800j, 1200j]

    bbthr = 0.9j
    ccthr = 0.9j

    if tagger == 'bb':
        tagger_pass_set = {'pnet1': slice(bbthr, 1j, sum), 'bbvcc':slice(1j,2j,sum)}
        tagger_fail_set = {'pnet1': slice(0j,bbthr, sum), 'bbvcc':slice(1j,2j,sum)}
    elif tagger == 'cc':
        tagger_pass_set = {'pnet2': slice(ccthr, 1j, sum), 'bbvcc':slice(0j,1j,sum)}
        tagger_fail_set = {'pnet2': slice(0j,ccthr, sum), 'bbvcc':slice(0j,1j,sum)}
    else:
        print("NO VALID TAGGER SELECTED")
        return

    sample_2_set = {'genflavor': slice(1j, 3j, sum)}
    sample_bb_set = {'genflavor': slice(3j, 4j, sum)}

    tasks = []

    for region in ["vbf","ggf","vh"]:
        for p in samples:

            tasks.append(make_task(infile, region, p, f"total_{region}_pass_{p}", tagger_pass_set))
            tasks.append(make_task(infile, region, p, f"total_{region}_fail_{p}", tagger_fail_set))

    #MJJ BINS
    for i,b in enumerate(mjjbins[:-1]):

        mjj_set = {'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}

        mjj_pass_set = {**tagger_pass_set, **mjj_set}
        mjj_fail_set = {**tagger_fail_set, **mjj_set}

        mjj_pass_set_2 = {**mjj_pass_set, **sample_2_set}
        mjj_fail_set_2 = {**mjj_fail_set, **sample_2_set}

        mjj_pass_set_bb = {**mjj_pass_set, **sample_bb_set}
        mjj_fail_set_bb = {**mjj_fail_set, **sample_bb_set}

        for p in samples:

            tasks.append(make_task(infile, "vbf", p, f"vbf_pass_mjj{i+1}_{p}", mjj_pass_set))
            tasks.append(make_task(infile, "vbf", p, f"vbf_fail_mjj{i+1}_{p}", mjj_fail_set))

        for p in samples_2:

            tasks.append(make_task(infile, "vbf", p, f"vbf_pass_mjj{i+1}_{p}", mjj_pass_set_2))
            tasks.append(make_task(infile, "vbf", p, f"vbf_fail_mjj{i+1}_{p}", mjj_fail_set_2))

            tasks.append(make_task(infile, "vbf", p, f"vbf_pass_mjj{i+1}_{p}bb", mjj_pass_set_bb))
            tasks.append(make_task(infile, "vbf", p, f"vbf_fail_mjj{i+1}_{p}bb", mjj_fail_set_bb))

    #PT BINS
    for i,b in enumerate(ptbins[:-1]):

        pt_set = {'pt1': slice(ptbins[i], ptbins[i+1], sum)}

        pt_pass_set = {**tagger_pass_set, **pt_set}
        pt_fail_set = {**tagger_fail_set, **pt_set}

        pt_pass_set_2 = {**pt_pass_set, **sample_2_set}
        pt_fail_set_2 = {**pt_fail_set, **sample_2_set}

        pt_pass_set_bb = {**pt_pass_set, **sample_bb_set}
        pt_fail_set_bb = {**pt_fail_set, **sample_bb_set}

        for region in ["ggf","vh"]:

            for p in samples:

                tasks.append(make_task(infile, region, p,  f"{region}_pass_pt{i+1}_{p}", pt_pass_set))
                tasks.append(make_task(infile, region, p,  f"{region}_fail_pt{i+1}_{p}", pt_fail_set))

            for p in samples_2:

                tasks.append(make_task(infile, region, p,  f"{region}_pass_pt{i+1}_{p}", pt_pass_set_2))
                tasks.append(make_task(infile, region, p,  f"{region}_fail_pt{i+1}_{p}", pt_fail_set_2))

                tasks.append(make_task(infile, region, p,  f"{region}_pass_pt{i+1}_{p}bb", pt_pass_set_bb))
                tasks.append(make_task(infile, region, p,  f"{region}_fail_pt{i+1}_{p}bb", pt_fail_set_bb))
                
    return tasks

if __name__ == "__main__":
    main()