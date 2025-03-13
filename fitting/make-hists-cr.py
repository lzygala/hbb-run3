#!/usr/bin/python  

import os, sys
import json
import uproot
import pickle

with open('../lumi.json') as f:
    lumis = json.load(f)

ddbthr = 0.64j

# Main method
def main():

    if len(sys.argv) < 2:
        print("Enter year")
        return 
    elif len(sys.argv) > 3:
        print("Incorrect number of arguments")
        return

    year = sys.argv[1]

    samples = ['data','JetData','MuonData','QCD','ttbar','singlet','VV','ggF','VBF','WH','ZH','ttH']

    print("MUON CR")
    if os.path.isfile(year+'/muonCR.root'):
        os.remove(year+'/muonCR.root')
    fout = uproot.create(year+'/muonCR.root')

    # Check if pickle exists                                                                         
    picklename = year+'/templates.pkl'
    if not os.path.isfile(picklename):
        print("You need to create the pickle")
        return

    # Read the histogram from the pickle file
    mucr = pickle.load(open(picklename,'rb')).integrate('region','muoncontrol').integrate('mjj')

    for p in samples:
        if p in list(mucr.axes['process']):

            hpass = mucr[{'pt1': sum}][{'genflavor': sum}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
            hfail = mucr[{'pt1': sum}][{'genflavor': sum}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

            for s in list(hfail.axes['systematic']):

                fout["pass_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                fout["fail_"+p+"_"+str(s)] = hfail[{'systematic': s}]

    for p in ['Wjets','Zjets','EWKW','EWKZ']:
        if p in list(mucr.axes['process']):

            hpass = mucr[{'pt1': sum}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
            hfail = mucr[{'pt1': sum}][{'genflavor': slice(1j, 3j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]

            hpass_bb = mucr[{'pt1': sum}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(ddbthr, 1j, sum)}][{'process': p}]
            hfail_bb = mucr[{'pt1': sum}][{'genflavor': slice(3j, 4j, sum)}][{'ddb1': slice(0j,ddbthr, sum)}][{'process': p}]


            for s in list(hfail.axes['systematic']):

                fout["pass_"+p+"_"+str(s)] = hpass[{'systematic': s}]
                fout["fail_"+p+"_"+str(s)] = hfail[{'systematic': s}]

                fout["pass_"+p+"bb_"+str(s)] = hpass_bb[{'systematic': s}]
                fout["fail_"+p+"bb_"+str(s)] = hfail_bb[{'systematic': s}]
        
    fout.close()

    return

if __name__ == "__main__":

    main()