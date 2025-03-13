#!/usr/bin/python  

import os, sys
import json
import uproot
import hist
import pickle

with open('../lumi.json') as f:
    lumis = json.load(f)

ddbthr = 0.5j

# Main method
def main():

    if len(sys.argv) < 2:
        print("Enter year")
        return
    elif len(sys.argv) > 3:
        print("Incorrect number of arguments")
        return

    year = sys.argv[1]

    if os.path.isfile(year+'/signalregion.root'):
        os.remove(year+'/signalregion.root')
    fout = uproot.create(year+'/signalregion.root')

    samples = ['data','JetData','MuonData','QCD','ttbar','singlet','VV','ggF','VBF','WH','ZH','ttH']

    mjjbins = [1000j,2000j,13000j]
    ptbins = [450j, 500j, 550j, 600j, 675j, 800j, 1200j]

    # Check if pickle exists     
    picklename = year+'/templates.pkl'
    if not os.path.isfile(picklename):
        print("You need to create the pickle")
        return

    # Read the histogram from the pickle file
    vbf = pickle.load(open(picklename,'rb')).integrate('region','signal-vbf')
    ggf = pickle.load(open(picklename,'rb')).integrate('region','signal-ggf').integrate('mjj')
    vh = pickle.load(open(picklename,'rb')).integrate('region','signal-vh').integrate('mjj')
    
    fout['total_vbf'] = vbf[{'pt1': sum}][{'genflavor': sum}][{'mjj': sum}][{'ddb1': sum}][{'process': sum}][{'systematic': sum}]
    fout['total_ggf'] = ggf[{'pt1': sum}][{'genflavor': sum}][{'ddb1': sum}][{'process': sum}][{'systematic': sum}]
    fout['total_vh'] = vh[{'pt1': sum}][{'genflavor': sum}][{'ddb1': sum}][{'process': sum}][{'systematic': sum}]

    print(list(vbf.axes['process']))
    #MJJ BINS
    for i,b in enumerate(mjjbins[:-1]):

        for p in samples:
            if p in list(vbf.axes['process']):

                hpass = vbf[{'pt1': sum}][{'genflavor': sum}][{'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail = vbf[{'pt1': sum}][{'genflavor': sum}][{'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                for s in list(hfail.axes['systematic']):

                    fout["vbf_pass_mjj"+str(i+1)+"_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                    fout["vbf_fail_mjj"+str(i+1)+"_"+p+"_"+str(s)] = hfail[{'systematic': s}]

        for p in ['Wjets','Zjets','EWKW','EWKZ']:
            if p in list(vbf.axes['process']):

                hpass = vbf[{'pt1': sum}][{'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail = vbf[{'pt1': sum}][{'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                hpass_bb = vbf[{'pt1': sum}][{'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail_bb = vbf[{'pt1': sum}][{'mjj': slice(mjjbins[i], mjjbins[i+1], sum)}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                for s in list(hfail.axes['systematic']):

                    fout["vbf_pass_mjj"+str(i+1)+"_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                    fout["vbf_fail_mjj"+str(i+1)+"_"+p+"_"+str(s)] = hfail[{'systematic': s}]

                    fout["vbf_pass_mjj"+str(i+1)+"_"+p+"bb_"+str(s)] = hpass_bb[{'systematic': s}]
                    fout["vbf_fail_mjj"+str(i+1)+"_"+p+"bb_"+str(s)] = hfail_bb[{'systematic': s}]

    #PT BINS
    for i,b in enumerate(ptbins[:-1]):

        for p in samples:
            if p in list(ggf.axes['process']):

                hpass = ggf[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': sum}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail = ggf[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': sum}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                for s in list(hfail.axes['systematic']):
                    fout["ggf_pass_pt"+str(i+1)+"_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                    fout["ggf_fail_pt"+str(i+1)+"_"+p+"_"+str(s)] = hfail[{'systematic': s}]
            
            if p in list(vh.axes['process']):
                hpass = vh[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': sum}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail = vh[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': sum}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                for s in list(hfail.axes['systematic']):
                    fout["vh_pass_pt"+str(i+1)+"_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                    fout["vh_fail_pt"+str(i+1)+"_"+p+"_"+str(s)] = hfail[{'systematic': s}]

        for p in ['Wjets','Zjets','EWKW','EWKZ']:
            if p in list(ggf.axes['process']):

                hpass = ggf[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail = ggf[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                hpass_bb = ggf[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail_bb = ggf[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                for s in list(hfail.axes['systematic']):

                    fout["ggf_pass_pt"+str(i+1)+"_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                    fout["ggf_fail_pt"+str(i+1)+"_"+p+"_"+str(s)] = hfail[{'systematic': s}]

                    fout["ggf_pass_pt"+str(i+1)+"_"+p+"bb_"+str(s)] = hpass_bb[{'systematic': s}]
                    fout["ggf_fail_pt"+str(i+1)+"_"+p+"bb_"+str(s)] = hfail_bb[{'systematic': s}]

            if p in list(vh.axes['process']):

                hpass = vh[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail = vh[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                hpass_bb = vh[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
                hfail_bb = vh[{'pt1': slice(ptbins[i], ptbins[i+1], sum)}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

                for s in list(hfail.axes['systematic']):

                    fout["vh_pass_pt"+str(i+1)+"_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                    fout["vh_fail_pt"+str(i+1)+"_"+p+"_"+str(s)] = hfail[{'systematic': s}]

                    fout["vh_pass_pt"+str(i+1)+"_"+p+"bb_"+str(s)] = hpass_bb[{'systematic': s}]
                    fout["vh_fail_pt"+str(i+1)+"_"+p+"bb_"+str(s)] = hfail_bb[{'systematic': s}]


    fout.close()
    return

if __name__ == "__main__":
    main()