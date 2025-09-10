from __future__ import print_function, division
import sys, os
import csv, json
import numpy as np
from scipy.interpolate import interp1d
import scipy.stats
import pickle
import ROOT
import pandas as pd
import argparse

import rhalphalib as rl
from rhalphalib import AffineMorphTemplate, MorphHistW2

rl.util.install_roofit_helpers()
rl.ParametericSample.PreferRooParametricHist = False

eps=0.001
do_systematics = True
do_muon_CR = False

def badtemp_ma(hvalues, mask=None):
    # Need minimum size & more than 1 non-zero bins           
    tot = np.sum(hvalues[mask])
    
    count_nonzeros = np.sum(hvalues[mask] > 0)
    if (tot < eps) or (count_nonzeros < 2):
        return True
    else:
        return False

def syst_variation(numerator,denominator):
    """
    Get systematic variation relative to nominal (denominator)
    """
    var = np.divide(numerator,denominator)
    var[np.where(numerator==0)] = 1
    var[np.where(denominator==0)] = 1

    return var

def smass(sName):
    if sName in ['ggF','VBF','WH','ZH','ttH']:
        _mass = 125.
    elif sName in ['Wjets','EWKW','ttbar','singlet','VV']:
        _mass = 80.379
    elif sName in ['Zjets','Zjetsbb','EWKZ','EWKZbb']:
        _mass = 91.
    else:
        raise ValueError("What is {}".format(sName))
    return _mass

def one_bin(sName, passed, ptbin, cat, obs, syst, muon=False):
    f = ROOT.TFile.Open(year+'/signalregion.root')
    if muon:
        f = ROOT.TFile.Open(year+'/muonCR.root')

    name = cat+'fail_'
    if passed:
        name = cat+'pass_'
    if cat == 'ggf_':
        name += 'pt'+str(ptbin)+'_'
    elif cat == 'vbf_':
        name += 'mjj'+str(ptbin)+'_'
    elif cat == 'vh_':
        name += 'pt'+str(ptbin)+'_'

    name += sName+'_'+syst
    # print("DEBUG: one_bin(): ", sName, name)

    h = f.Get(name)
    newh = h.Rebin(h.GetNbinsX())
    sumw = [newh.GetBinContent(1)]
    sumw2 = [newh.GetBinError(1)]

    return (np.array(sumw), np.array([0., 1.]), "onebin", np.array(sumw2))

def get_template(year, tag, tagger, sName, passed, ptbin, cat, obs, syst, muon=False):
    """
    Read msd template from root file
    """

    f = ROOT.TFile.Open(f"results/{tag}/{year}/{tagger}/signalregion_{tagger}.root")
    if muon:
        f = ROOT.TFile.Open(f"results/{tag}/{year}/{tagger}/muonCR_{tagger}.root")

    name = cat+'fail_'
    if passed:
        name = cat+'pass_'
    if cat == 'ggf_':
        name += 'pt'+str(ptbin)+'_'
    elif cat == 'vbf_':
        name += 'mjj'+str(ptbin)+'_'
    elif cat == 'vh_':
        name += 'pt'+str(ptbin)+'_'

    name += sName+'_'+syst
    print(name)

    h = f.Get(name)

    sumw = []
    sumw2 = []

    # print("DEBUG: get_template(): ", sName, name, cat)

    for i in range(1,h.GetNbinsX()+1):

        if h.GetBinContent(i) < 0:
#            print('negative bin',name)
            sumw += [0]
            sumw2 += [0]
        else:
            sumw += [h.GetBinContent(i)]
            sumw2 += [h.GetBinError(i)*h.GetBinError(i)]

    return (np.array(sumw), obs.binning, obs.name, np.array(sumw2))

def shape_to_num(var, nom, clip=1.5):
    nom_rate = np.sum(nom)
    var_rate = np.sum(var)

    if abs(var_rate/nom_rate) > clip:
        var_rate = clip*nom_rate

    if var_rate < 0:
        var_rate = 0

    return var_rate/nom_rate

def passfailSF(isPass, sName, ptbin, cat, obs, mask, SF=1, SF_unc_up=0.1, SF_unc_down=-0.1, muon=False):
    """
    Return (SF, SF_unc) for a pass/fail scale factor.
    """
    if isPass:
        return SF, 1. + SF_unc_up / SF, 1. + SF_unc_down / SF
    else:
        _pass = get_template(year, tag, tagger, sName, 1, ptbin+1, cat, obs=obs, syst='nominal', muon=muon)
        _pass_rate = np.sum(_pass[0]*mask)

        _fail = get_template(year, tag, tagger, sName, 0, ptbin+1, cat, obs=obs, syst='nominal', muon=muon)
        _fail_rate = np.sum(_fail[0]*mask)

        if _fail_rate > 0:
            _sf = 1 + (1 - SF) * _pass_rate / _fail_rate
            _sfunc_up = 1. - SF_unc_up * (_pass_rate / _fail_rate)
            _sfunc_down = 1. - SF_unc_down * (_pass_rate / _fail_rate)

            return _sf, _sfunc_up, _sfunc_down
        else:
            return 1, 1, 1

def plot_mctf(tf_MCtempl, msdbins, name,year,tag,tagger):
    """
    Plot the MC pass / fail TF as function of (pt,rho) and (pt,msd)
    """
    import matplotlib.pyplot as plt

    outdir = f"results/{tag}/{year}/{tagger}/plots/"
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    # arrays for plotting pt vs msd                    
    pts = np.linspace(450,1200,15)
    ptpts, msdpts = np.meshgrid(pts[:-1] + 0.5 * np.diff(pts), msdbins[:-1] + 0.5 * np.diff(msdbins), indexing='ij')
    ptpts_scaled = (ptpts - 450.) / (1200. - 450.)
    rhopts = 2*np.log(msdpts/ptpts)

    rhopts_scaled = (rhopts - (-6)) / ((-2.1) - (-6))
    validbins = (rhopts_scaled >= 0) & (rhopts_scaled <= 1)

    ptpts = ptpts[validbins]
    msdpts = msdpts[validbins]
    ptpts_scaled = ptpts_scaled[validbins]
    rhopts_scaled = rhopts_scaled[validbins]

    tf_MCtempl_vals = tf_MCtempl(ptpts_scaled, rhopts_scaled, nominal=True)
    df = pd.DataFrame([])
    df['msd'] = msdpts.reshape(-1)
    df['pt'] = ptpts.reshape(-1)
    df['MCTF'] = tf_MCtempl_vals.reshape(-1)

    fig, ax = plt.subplots()
    h = ax.hist2d(x=df["msd"],y=df["pt"],weights=df["MCTF"], bins=(msdbins,pts))
    plt.xlabel("$m_{sd}$ [GeV]")
    plt.ylabel("$p_{T}$ [GeV]")
    cb = fig.colorbar(h[3],ax=ax)
    cb.set_label("Ratio")
    fig.savefig(outdir + "MCTF_msdpt_"+name+".png",bbox_inches="tight")
    fig.savefig(outdir +"MCTF_msdpt_"+name+".pdf",bbox_inches="tight")
    plt.clf()

    # arrays for plotting pt vs rho                                          
    rhos = np.linspace(-6,-2.1,23)
    ptpts, rhopts = np.meshgrid(pts[:-1] + 0.5*np.diff(pts), rhos[:-1] + 0.5 * np.diff(rhos), indexing='ij')
    ptpts_scaled = (ptpts - 450.) / (1200. - 450.)
    rhopts_scaled = (rhopts - (-6)) / ((-2.1) - (-6))
    validbins = (rhopts_scaled >= 0) & (rhopts_scaled <= 1)

    ptpts = ptpts[validbins]
    rhopts = rhopts[validbins]
    ptpts_scaled = ptpts_scaled[validbins]
    rhopts_scaled = rhopts_scaled[validbins]

    tf_MCtempl_vals = tf_MCtempl(ptpts_scaled, rhopts_scaled, nominal=True)

    df = pd.DataFrame([])
    df['rho'] = rhopts.reshape(-1)
    df['pt'] = ptpts.reshape(-1)
    df['MCTF'] = tf_MCtempl_vals.reshape(-1)

    fig, ax = plt.subplots()
    h = ax.hist2d(x=df["rho"],y=df["pt"],weights=df["MCTF"],bins=(rhos,pts))
    plt.xlabel("rho")
    plt.ylabel("$p_{T}$ [GeV]")
    cb = fig.colorbar(h[3],ax=ax)
    cb.set_label("Ratio")
    fig.savefig(outdir+"MCTF_rhopt_"+name+".png",bbox_inches="tight")
    fig.savefig(outdir+"MCTF_rhopt_"+name+".pdf",bbox_inches="tight")

    return

def ggfvbf_rhalphabet(tmpdir,year,tag,tagger,
                    throwPoisson = True,
                    fast=0):
    """ 
    Create the data cards!
    """
    with open('sf.json') as f:
        SF = json.load(f)

    with open('../lumi.json') as f:
        lumi = json.load(f)

    # TT params
    tqqeffSF = rl.IndependentParameter('tqqeffSF_{}'.format(year), 1., -50, 50)
    tqqnormSF = rl.IndependentParameter('tqqnormSF_{}'.format(year), 1., -50, 50)



    # define bins    
    ptbins = {}
    ptbins['ggf'] = np.array([450, 500, 550, 600, 675, 800, 1200])
    ptbins['vh'] = np.array([450, 500, 550, 600, 675, 800, 1200])
    ptbins['vbflo'] = np.array([450,1200])
    ptbins['vbfhi'] = np.array([450,1200])

    mjjbins = {}
    mjjbins['ggf'] = np.array([0,13000])
    mjjbins['vh'] = np.array([0,13000])
    mjjbins['vbflo'] = np.array([1000,2000])
    mjjbins['vbfhi'] = np.array([2000,13000])

    npt = {}
    npt['ggf'] = len(ptbins['ggf']) - 1
    npt['vh'] = len(ptbins['vh']) - 1
    npt['vbflo'] = len(ptbins['vbflo']) - 1
    npt['vbfhi'] = len(ptbins['vbfhi']) - 1

    nmjj = {}
    nmjj['ggf'] = len(mjjbins['ggf']) - 1
    nmjj['vh'] = len(mjjbins['vh']) - 1
    nmjj['vbflo'] = len(mjjbins['vbflo']) - 1
    nmjj['vbfhi'] = len(mjjbins['vbfhi']) - 1

    msdbins = np.linspace(40, 201, 24)
    msd = rl.Observable('msd', msdbins)

    validbins = {}

    cats = ['ggf','vh','vbflo','vbfhi']
    ncat = len(cats)

    Nfail_qcd_MC = 0
    Nfail_data = 0

    # Build qcd MC pass+fail model and fit to polynomial
    tf_params = {}
    for cat in cats:

        fitfailed_qcd = 0

        # here we derive these all at once with 2D array                            
        ptpts, msdpts = np.meshgrid(ptbins[cat][:-1] + 0.3 * np.diff(ptbins[cat]), msdbins[:-1] + 0.5 * np.diff(msdbins), indexing='ij')
        rhopts = 2*np.log(msdpts/ptpts)
        ptscaled = (ptpts - 450.) / (1200. - 450.)
        rhoscaled = (rhopts - (-6)) / ((-2.1) - (-6))
        validbins[cat] = (rhoscaled >= 0) & (rhoscaled <= 1)
        rhoscaled[~validbins[cat]] = 1  # we will mask these out later   

        while fitfailed_qcd < 5:
        
            qcdmodel = rl.Model('qcdmodel_'+cat)
            qcdpass, qcdfail = 0., 0.

            for ptbin in range(npt[cat]):
                mjjbin = 0
                if 'hi' in cat:
                    mjjbin = 1

                failCh = rl.Channel('ptbin%d%s%s%s' % (ptbin, cat, 'fail',year))
                passCh = rl.Channel('ptbin%d%s%s%s' % (ptbin, cat, 'pass',year))
                qcdmodel.addChannel(failCh)
                qcdmodel.addChannel(passCh)

                binindex = ptbin
                if 'vbf' in cat:
                    binindex = mjjbin

                # QCD templates from file                           
                failTempl = get_template(year, tag, tagger, 'QCD', 0, binindex+1, cat[:3]+'_', obs=msd, syst='nominal')
                passTempl = get_template(year, tag, tagger, 'QCD', 1, binindex+1, cat[:3]+'_', obs=msd, syst='nominal')
                
                failCh.setObservation(failTempl, read_sumw2=True)
                passCh.setObservation(passTempl, read_sumw2=True)

                qcdfail += sum([val for val in failCh.getObservation()[0]])
                qcdpass += sum([val for val in passCh.getObservation()[0]])

            qcdeff = qcdpass / qcdfail
            print('Inclusive P/F from Monte Carlo = ' + str(qcdeff))

            Nfail_qcd_MC += qcdfail

            # initial values                                         
            initF = f"results/{tag}/{year}/{tagger}/initial_vals/initial_vals_{cat}.json"                       
            print('Initial fit values read from file initial_vals*')
            with open(initF) as f:
                initial_vals = np.array(json.load(f)['initial_vals'])
            print(initial_vals)

            print("TFpf order " + str(initial_vals.shape[0]-1) + " in pT, " + str(initial_vals.shape[1]-1) + " in rho")
            tf_MCtempl = rl.BasisPoly("tf_MCtempl_"+cat+year,
                                      (initial_vals.shape[0]-1,initial_vals.shape[1]-1),
                                      ['pt', 'rho'], 
                                      basis='Bernstein',
                                      init_params=initial_vals,
                                      limits=(-50, 50), coefficient_transform=None)
            
            tf_MCtempl_params = qcdeff * tf_MCtempl(ptscaled, rhoscaled)


            for ptbin in range(npt[cat]):
                mjjbin = 0
                if 'hi' in cat:
                    mjjbin = 1

                failCh = qcdmodel['ptbin%d%sfail%s' % (ptbin, cat, year)]
                passCh = qcdmodel['ptbin%d%spass%s' % (ptbin, cat, year)]
                failObs = failCh.getObservation()
                passObs = passCh.getObservation()
                
                qcdparams = np.array([rl.IndependentParameter('qcdparam_ptbin%d%s%s_%d' % (ptbin, cat, year, i), 0, -50, 50) for i in range(msd.nbins)])
                sigmascale = 10.
                scaledparams = failObs * (1 + sigmascale/np.maximum(1., np.sqrt(failObs)))**qcdparams
                
                fail_qcd = rl.ParametericSample('ptbin%d%sfail%s_qcd' % (ptbin, cat, year), rl.Sample.BACKGROUND, msd, scaledparams[0])
                failCh.addSample(fail_qcd)
                pass_qcd = rl.TransferFactorSample('ptbin%d%spass%s_qcd' % (ptbin, cat, year), rl.Sample.BACKGROUND, tf_MCtempl_params[ptbin, :], fail_qcd)
                passCh.addSample(pass_qcd)
                
                failCh.mask = validbins[cat][ptbin]
                passCh.mask = validbins[cat][ptbin]

            qcdfit_ws = ROOT.RooWorkspace('w')

            simpdf, obs = qcdmodel.renderRoofit(qcdfit_ws)
            qcdfit = simpdf.fitTo(obs,
                                  ROOT.RooFit.Extended(True),
                                  ROOT.RooFit.SumW2Error(True),
                                  ROOT.RooFit.Strategy(2),
                                  ROOT.RooFit.Save(),
                                  ROOT.RooFit.Minimizer('Minuit2', 'migrad'),
                                  ROOT.RooFit.PrintLevel(0),
                              )
            qcdfit_ws.add(qcdfit)
            qcdfit_ws.writeToFile(os.path.join(str(tmpdir), 'testModel_qcdfit_'+cat+'_'+year+'.root'))

            # Set parameters to fitted values  
            allparams = dict(zip(qcdfit.nameArray(), qcdfit.valueArray()))
            pvalues = []
            for i, p in enumerate(tf_MCtempl.parameters.reshape(-1)):
                p.value = allparams[p.name]
                pvalues += [p.value]
            
            if qcdfit.status() != 0:
                fitfailed_qcd += 1

                new_values = np.array(pvalues).reshape(tf_MCtempl.parameters.shape)
                print(f'Could not fit qcd, category: {cat}, new values: {new_values.tolist()}')
                with open(initF, "w") as outfile:
                    json.dump({"initial_vals":new_values.tolist()},outfile)

            else:
                break

        if fitfailed_qcd >=5:
            raise RuntimeError('Could not fit qcd after 5 tries')

        print("Fitted qcd for category " + cat)

        # Plot the MC P/F transfer factor                                                   
        plot_mctf(tf_MCtempl,msdbins, cat,year,tag,tagger)                           
        np.save('MCTF'+cat, pvalues)

        param_names = [p.name for p in tf_MCtempl.parameters.reshape(-1)]
        decoVector = rl.DecorrelatedNuisanceVector.fromRooFitResult(tf_MCtempl.name + '_deco', qcdfit, param_names)
        np.save('decoVector'+cat, decoVector._transform)
        tf_MCtempl.parameters = decoVector.correlated_params.reshape(tf_MCtempl.parameters.shape)
        tf_MCtempl_params_final = tf_MCtempl(ptscaled, rhoscaled)

        # initial values   
        initdF = f"results/{tag}/{year}/{tagger}/initial_vals/initial_vals_data_{cat}.json"                                                                                                                                       
        with open(initdF) as f:
            initial_vals_data = np.array(json.load(f)['initial_vals'])

        print("TFres order " + str(initial_vals_data.shape[0]-1)+ " in pT, " + str(initial_vals_data.shape[1]-1) + " in rho")
        tf_dataResidual = rl.BasisPoly("tf_dataResidual_"+year+cat,
                                       (initial_vals_data.shape[0]-1,initial_vals_data.shape[1]-1), 
                                       ['pt', 'rho'], 
                                       basis='Bernstein',
                                       init_params=initial_vals_data,
                                       limits=(-50,50), 
                                       coefficient_transform=None)

        tf_dataResidual_params = tf_dataResidual(ptscaled, rhoscaled)
        tf_params[cat] = qcdeff * tf_MCtempl_params_final * tf_dataResidual_params

    # build actual fit model now
    model = rl.Model('testModel_'+year)

    # exclude QCD from MC samps
    samps = ['ggF','VBF','WH','ZH','ttH','Wjets','Zjets','Zjetsbb','ttbar','singlet','VV','EWKV','EWKVbb',]#'Zgamma','Wgamma'] #'EWKW','EWKZ','EWKZbb',
    sigs = ['ggF','VBF','WH','ZH']

    for cat in cats:
        for ptbin in range(npt[cat]):
            mjjbin = 0
            if 'hi' in cat:
                mjjbin = 1

            for region in ['pass', 'fail']:

                binindex = ptbin
                if 'vbf' in cat:
                    binindex = mjjbin

                print("Bin: " + cat + " bin " + str(binindex) + " " + region)

                # drop bins outside rho validity                                                
                mask = validbins[cat][ptbin]
                failCh.mask = mask 
                # blind bins 9-13                                                                        
                mask[9:14] = True 
                passCh.mask = mask

                ch = rl.Channel('ptbin%d%s%s%s' % (ptbin, cat, region, year))
                model.addChannel(ch)

                isPass = region == 'pass'
                templates = {}
            
                for sName in samps:

                    templates[sName] = get_template(year, tag, tagger, sName, isPass, binindex+1, cat[:3]+'_', obs=msd, syst='nominal')
                    nominal = templates[sName][0]

                    if(badtemp_ma(nominal)):
                        print("Sample {} is too small, skipping".format(sName))
                        continue

                    # expectations
                    templ = templates[sName]
                        
                    if sName in sigs:
                        stype = rl.Sample.SIGNAL
                    else:
                        stype = rl.Sample.BACKGROUND
                    
                    sample = rl.TemplateSample(ch.name + '_' + sName, stype, templ)

                    if do_systematics:

                        sample.autoMCStats(lnN=True)    

                    ch.addSample(sample)
 
                # END loop over MC samples 

                data_obs = get_template(year, tag, tagger, 'Jetdata', isPass, binindex+1, cat[:3]+'_', obs=msd, syst='nominal')

                if not isPass:
                    Nfail_data += data_obs[0].sum()

                ch.setObservation(data_obs, read_sumw2=True)

    for cat in cats:
        for ptbin in range(npt[cat]):
            mjjbin = 0
            if 'hi' in cat:
                mjjbin = 1

            failCh = model['ptbin%d%sfail%s' % (ptbin, cat, year)]
            passCh = model['ptbin%d%spass%s' % (ptbin, cat, year)]

            qcdparams = np.array([rl.IndependentParameter('qcdparam_ptbin%d%s%s_%d' % (ptbin, cat, year, i), 0, -50, 50) for i in range(msd.nbins)])
            initial_qcd = failCh.getObservation()[0].astype(float)  # was integer, and numpy complained about subtracting float from it

            for sample in failCh:
                initial_qcd -= sample.getExpectation(nominal=True)

            if np.any(initial_qcd < 0.):
                initial_qcd[np.where(initial_qcd<0)] = 0
                #raise ValueError('initial_qcd negative for some bins..', initial_qcd)

            sigmascale = 10  # to scale the deviation from initial                      
            scaledparams = initial_qcd * (1 + sigmascale/np.maximum(1., np.sqrt(initial_qcd)))**qcdparams
            fail_qcd = rl.ParametericSample('ptbin%d%sfail%s_qcd' % (ptbin, cat, year), rl.Sample.BACKGROUND, msd, scaledparams)
            failCh.addSample(fail_qcd)
            pass_qcd = rl.TransferFactorSample('ptbin%d%spass%s_qcd' % (ptbin, cat, year), rl.Sample.BACKGROUND, tf_params[cat][ptbin, :], fail_qcd)
            passCh.addSample(pass_qcd)

            if do_muon_CR:
                
                tqqpass = passCh['ttbar']
                tqqfail = failCh['ttbar']
                sumPass = tqqpass.getExpectation(nominal=True).sum()
                sumFail = tqqfail.getExpectation(nominal=True).sum()

                if 'singlet' in passCh.samples:
                    stqqpass = passCh['singlet']
                    stqqfail = failCh['singlet']
                    
                    sumPass += stqqpass.getExpectation(nominal=True).sum()
                    sumFail += stqqfail.getExpectation(nominal=True).sum()
                    
                    tqqPF =  sumPass / sumFail
                    
                    stqqpass.setParamEffect(tqqeffSF, 1 * tqqeffSF)
                    stqqfail.setParamEffect(tqqeffSF, (1 - tqqeffSF) * tqqPF + 1)
                    stqqpass.setParamEffect(tqqnormSF, 1 * tqqnormSF)
                    stqqfail.setParamEffect(tqqnormSF, 1 * tqqnormSF)

                tqqPF =  sumPass / sumFail
                tqqpass.setParamEffect(tqqeffSF, 1 * tqqeffSF)
                tqqfail.setParamEffect(tqqeffSF, (1 - tqqeffSF) * tqqPF + 1)
                tqqpass.setParamEffect(tqqnormSF, 1 * tqqnormSF)
                tqqfail.setParamEffect(tqqnormSF, 1 * tqqnormSF)
                    
    kfactor_qcd = 1.0*Nfail_data/Nfail_qcd_MC



    with open(os.path.join(str(tmpdir), 'testModel_'+year+'.pkl'), 'wb') as fout:
        pickle.dump(model, fout)

    model.renderCombine(os.path.join(str(tmpdir), 'testModel_'+year))

if __name__ == '__main__':

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--year",
        help="year",
        type=str,
        required=True,
        choices=["2022", "2022EE", "2023", "2023BPix"],
    )
    parser.add_argument(
        "--tag",
        help="tag",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--tagger",
        help="bb or cc",
        type=str,
        required=True,
        choices=["bb","cc"],
    )

    args = parser.parse_args()
    year = args.year
    tag = args.tag
    tagger = args.tagger

    print("Running for "+year)

    datacard_dir = f"results/{tag}/{year}/{tagger}/datacards/"
    initvals_dir = f"results/{tag}/{year}/{tagger}/initial_vals/"

    if not os.path.exists(datacard_dir):
        os.makedirs(datacard_dir)

    if not os.path.exists(initvals_dir):
        os.popen(f'cp -r initial_vals/ {initvals_dir}')

    ggfvbf_rhalphabet(datacard_dir,year,tag,tagger)
