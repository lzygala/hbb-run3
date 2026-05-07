

import os, subprocess
from coffea import processor, util
import pandas as pd
import pickle
from common import common_mc, data_by_year


def build_inverse_map(common_mc, year, data=False):
    if data:
        
        return {
            datasets: "data"
            for datasets in common_mc[year]
        }

    return {
        dataset: process
        for process, datasets in common_mc[year].items()
        for dataset in datasets
    }


year = '2024'
region = 'signal-wwh'
pp_category = 'signal_region'
tag = '26May6'
coffeadir_prefix = '/eos/uscms/store/group/lpchbbrun3/lzygala/hvv_26May6/merged_2lep_1FJ_r3_2lep_1FJ_20260430155132/'
procs = subprocess.getoutput(f"ls {coffeadir_prefix}/{year}").split()


repickle = True
# Check if pickle exists, don't recreate it if it does
picklename ='cutflow.pkl'
#if os.path.isfile(picklename):
#    repickle = False
cutflow = None
cutflow_pp = None

if repickle:

    #LOADING PROCESSOR CUTFLOW
    for proc in procs:
    
        filename = f"{coffeadir_prefix}/{year}/{proc}/pickles/out_0.pkl"
        
        print(filename)
        if os.path.isfile(filename):
            with open(filename, 'rb') as openfile:
                data = pickle.load(openfile)
                
            print(proc)
            # print(data['2024_files']['nominal']['cutflow'])
            if cutflow is None:
                cutflow = data['2024_files']['nominal']['cutflow']
            else:
                cutflow += data['2024_files']['nominal']['cutflow']
                
        else:
            print(f'Missing file: {proc}')
            #print("File " + filename + " is missing")
            # 
    #LOADING POSTPROCESSOR CUTFLOW

        filename = f"{coffeadir_prefix}/{year}/{proc}/pickles/postprocessing_cutflow.pkl" 

        if os.path.isfile(filename):
            with open(filename, 'rb') as openfile:
                data = pickle.load(openfile)
                
            print(proc)
            # print(data['2024_files']['nominal']['cutflow'])
            if cutflow_pp is None:
                cutflow_pp = data
            else:
                cutflow_pp += data
                
        else:
            print(f'Missing post processing file: {proc}')
        
    
    outfile = open(picklename, 'wb')
    pickle.dump(cutflow, outfile, protocol=-1)
    outfile.close()



h = cutflow.integrate('h_pt').integrate('region',[region])
h_pp = cutflow_pp.integrate('h_pt').integrate('region',[region])
# print(h)

h_dict = {}
hpp_dict = {}
inverse_map = build_inverse_map(common_mc, year)
inverse_map_data = build_inverse_map(data_by_year, year, data=True)
total_map = {**inverse_map, **inverse_map_data}

for i, proc in enumerate(h.axes["dataset"]):

    if not total_map[proc] in h_dict:
        h_dict[total_map[proc]] = h[{"dataset": proc}]
    else:
        h_dict[total_map[proc]] += h[{"dataset": proc}]

# print(h_dict)

for i, proc in enumerate(h_pp.axes["dataset"]):

    if not total_map[proc] in hpp_dict:
        hpp_dict[total_map[proc]] = h_pp[{"dataset": proc}][{"category": pp_category}]
    else:
        hpp_dict[total_map[proc]] += h_pp[{"dataset": proc}][{"category": pp_category}]



sigs = ["vbs-hvv-c2v-1p0-c3-10p0", "vbs-hvv-c2v-1p0-c3-1p0", "vbs-hvv-c2v-1p5-c3-1p0"]

cut_index = [   "RDF",
                "twoleptons",
                "oppsign",
                "lepdR",
                "notZpeak",
                "onegoodAK8",
                "antiak4btagMedium",
                "2ak4s"
                ]

cut_pp_index = [
    "preselection",
    "hbb_score_0p1", 
    "vbf_deta_2p5", 
    "vbf_mjj_250"
]

df_pre_tot = pd.DataFrame([])
df_sig = pd.DataFrame([])
df_bkg = pd.DataFrame([])

df_pp_tot = pd.DataFrame([])

for proc in h_dict:
    df_pre_tot[proc] = h_dict[proc].values()
    df_pp_tot[proc] = hpp_dict[proc].values()
    if proc in sigs:
        df_sig[proc] = hpp_dict[proc].values()
    else:
        df_bkg[proc] = hpp_dict[proc].values()


df_pre_tot = df_pre_tot[:-(15 - len(cut_index))].astype('float')
df_pre_tot.index = cut_index
# df_pre_tot.to_latex(buf='cutflow_preprocessing.tex')
df_pre_tot.to_string(buf=f'plots/{tag}/cutflow_preprocessing.txt')

df_pp_tot = df_pp_tot[:-(15 - len(cut_pp_index))].astype('float')
df_pp_tot.index = cut_pp_index

df_finalregion = pd.concat([df_pre_tot, df_pp_tot])
# df_finalregion.to_latex(buf='cutflow-signalregion.tex')
df_finalregion.to_string(buf=f'plots/{tag}/cutflow-signalregion.txt')

df_sig = df_sig[:-7].astype('float')
df_sig.index = cut_index
# df_sig.to_latex(buf='cutflow-sig.tex')
df_sig.to_string(buf=f'plots/{tag}/cutflow-sig.txt')

df_bkg = df_bkg[:-7].astype('float')
df_bkg.index = cut_index
# df_bkg.to_latex(buf='cutflow-bkg.tex')
df_bkg.to_string(buf=f'plots/{tag}/cutflow-bkg.txt')
