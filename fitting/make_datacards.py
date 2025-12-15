from __future__ import print_function, division
import os
import json
import numpy as np
import pickle
import ROOT
import pandas as pd
import argparse

import rhalphalib as rl

from hbb.common_vars import LUMI

rl.util.install_roofit_helpers()

eps=0.001 
do_systematics = True
do_muon_CR = True

lumi_err = {
    "2022": 1.01,
    "2023": 1.02
}

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

def one_bin(year, tag, sName, region, cat, syst):
    f = ROOT.TFile.Open(f"results/{tag}/{year}/signalregion.root")

    name += sName+'_'+syst

    h = f.Get(name)
    newh = h.Rebin(h.GetNbinsX())
    sumw = [newh.GetBinContent(1)]
    sumw2 = [newh.GetBinError(1)]

    return (np.array(sumw), np.array([0., 1.]), "onebin", np.array(sumw2))

def get_template(year, tag, sName, region, cat, obs, syst):
    """
    Read msd template from root file
    """

    f = ROOT.TFile.Open(f"results/{tag}/{year}/signalregion.root")

    name = cat+region
    name += sName+'_'+syst

    h = f.Get(name)

    sumw = []
    sumw2 = []

    for i in range(1,h.GetNbinsX()+1):

        if h.GetBinContent(i) < 0:
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

def ggfvbf_rhalphabet(args):
    """ 
    Create the data cards!
    """

    year = args.year
    tag = args.tag

    print("Running for "+year)

    working_dir = f"results/{tag}/{year}/"
    datacard_dir = f"results/{tag}/{year}/datacards/"

    if not os.path.exists(datacard_dir):
        os.makedirs(datacard_dir)

    with open(os.path.join(working_dir, 'setup.json')) as f:
        setup = json.load(f)
        cats_cfg = setup["categories"]

    total_model_bins = []

    # TT params
    tqqeffSF = rl.IndependentParameter(f'tqqeffSF_{year}', 1., -50, 50)
    tqqeffBCSF = rl.IndependentParameter(f'tqqeffBCSF_{year}', 1., -50, 50)
    tqqnormSF = rl.IndependentParameter(f'tqqnormSF_{year}', 1., -50, 50)

    sys_lumi_uncor = rl.NuisanceParameter(f'CMS_lumi_13p6TeV_{year[:4]}', 'lnN')

    #Systematics 
    sys_dict = {}
    sys_dict['pileup'] = rl.NuisanceParameter(f'CMS_PU_{year}', 'lnN')

    sys_dict['JES'] = rl.NuisanceParameter(f'CMS_scale_j_{year}', 'lnN')
    sys_dict['JER'] = rl.NuisanceParameter(f'CMS_res_j_{year}', 'lnN')
    sys_dict['UES'] = rl.NuisanceParameter(f'CMS_ues_j_{year}', 'lnN')

    sys_dict['MuonPTScale'] = rl.NuisanceParameter(f'CMS_scale_m_{year}', 'lnN')
    sys_dict['MuonPTRes'] = rl.NuisanceParameter(f'CMS_res_m_{year}', 'lnN')

    sys_dict[f'btagSFb_{year}'] = rl.NuisanceParameter(f'CMS_btagSFb_{year}', 'lnN')
    sys_dict[f'btagSFc_{year}'] = rl.NuisanceParameter(f'CMS_btagSFc_{year}', 'lnN')
    sys_dict[f'btagSFlight_{year}'] = rl.NuisanceParameter(f'CMS_btagSFlight_{year}', 'lnN')
    sys_dict['btagSFb_correlated'] = rl.NuisanceParameter(f'CMS_btagSFb_correlated_{year}', 'lnN')
    sys_dict['btagSFc_correlated'] = rl.NuisanceParameter(f'CMS_btagSFc_correlated_{year}', 'lnN')
    sys_dict['btagSFlight_correlated'] = rl.NuisanceParameter(f'CMS_btagSFlight_correlated_{year}', 'lnN')

    exp_systs = [
        'pileup', 
        'JES', 'JER', 'JER',
        f'btagSFb_{year}',
        f'btagSFc_{year}',
        f'btagSFlight_{year}'
        'btagSFb_correlated',
        'btagSFc_correlated',
        'btagSFlight_correlated',
        'MuonPTScale', 'MuonPTRes'
    ]

    pdf_Higgs_ggF = rl.NuisanceParameter('pdf_Higgs_ggF','lnN')
    pdf_Higgs_VBF = rl.NuisanceParameter('pdf_Higgs_VBF','lnN')
    pdf_Higgs_VH  = rl.NuisanceParameter('pdf_Higgs_VH','lnN')
    pdf_Higgs_ttH = rl.NuisanceParameter('pdf_Higgs_ttH','lnN')

    scale_ggF = rl.NuisanceParameter('QCDscale_ggF', 'lnN')
    scale_VBF = rl.NuisanceParameter('QCDscale_VBF', 'lnN')
    scale_VH = rl.NuisanceParameter('QCDscale_VH', 'lnN')
    scale_ttH = rl.NuisanceParameter('QCDscale_ttH', 'lnN')

    isr_ggF = rl.NuisanceParameter('ISRPartonShower_ggF', 'lnN')
    isr_VBF = rl.NuisanceParameter('ISRPartonShower_VBF', 'lnN')
    isr_VH = rl.NuisanceParameter('ISRPartonShower_VH', 'lnN')
    isr_ttH = rl.NuisanceParameter('ISRPartonShower_ttH', 'lnN')

    fsr_ggF = rl.NuisanceParameter('FSRPartonShower_ggF', 'lnN')
    fsr_VBF = rl.NuisanceParameter('FSRPartonShower_VBF', 'lnN')
    fsr_VH = rl.NuisanceParameter('FSRPartonShower_VH', 'lnN')
    fsr_ttH = rl.NuisanceParameter('FSRPartonShower_ttH', 'lnN')

    validbins = {}

    msd_cfg = setup["observable"]
    msdbins = np.linspace(msd_cfg["min"], msd_cfg["max"], msd_cfg["nbins"]+1)
    msd = rl.Observable(msd_cfg["name"], msdbins)

    cats = [
        'wwh',
        'zzh-1FJ',
        'wzh-zzh-2FJ' 
        ]

    # build actual fit model now
    model = rl.Model('testModel_'+year)

    # exclude QCD from MC samps
    samps = ['ggF','VBF','WH','ZH','ttH','Wjets','Zjetsc','Zjetslight','Zjetsbb','ttbar','singlet','VV','EWKW','EWKZc','EWKZlight','EWKZbb','QCD']
    sigs = ['ggF','VBF','WH','ZH']

    for cat in cats:

        for region in ['pass_A_', 'pass_B_', 'pass_C_', 'pass_D_']:

            ch_name = 'region%s%s%s' % (cat, region.replace("_", ""), year)
            total_model_bins.append(ch_name)

            ch = rl.Channel(ch_name)
            model.addChannel(ch)

            templates = {}
        
            for sName in samps:

                templates[sName] = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='nominal')
                nominal = templates[sName][0]

                if(badtemp_ma(nominal)):
                    print("Sample {} is too small, skipping".format(ch.name + '_' + sName))
                    continue

                # expectations
                templ = templates[sName]

                if sName in sigs:
                    stype = rl.Sample.SIGNAL
                else:
                    stype = rl.Sample.BACKGROUND
                
                sample = rl.TemplateSample(
                                ch.name + '_' + sName, 
                                stype, 
                                templ, 
                                force_positive=True
                            )

                sample.setParamEffect(sys_lumi_uncor, lumi_err[year[:4]] ** (LUMI[year[:4]] / LUMI["2022-2023"]))
                if do_systematics:

                    sample.autoMCStats(lnN=True)    

                    for sys in exp_systs:
                        syst_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst=sys+'Up')[0]
                        syst_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst=sys+'Down')[0]

                        eff_up = shape_to_num(syst_up,nominal)
                        eff_do = shape_to_num(syst_do,nominal)

                        sample.setParamEffect(sys_dict[sys], eff_up, eff_do)

                    if "EWKZ" in sName:

                        scale_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_7ptUp')[0]
                        scale_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_7ptDown')[0]

                        eff_scale_up = np.sum(scale_up)/np.sum(nominal)
                        eff_scale_do = np.sum(scale_do)/np.sum(nominal)

                        sample.setParamEffect(scale_VBF,eff_scale_up,eff_scale_do)


                    # QCD scale and PDF uncertainties on Higgs signal    
                    elif sName in ['ggF','VBF','WH','ZH','ggZH','ttH']:
                        
                        fsr_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='FSRPartonShowerUp')[0]
                        fsr_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='FSRPartonShowerDown')[0]
                        eff_fsr_up = np.sum(fsr_up)/np.sum(nominal)
                        eff_fsr_do = np.sum(fsr_do)/np.sum(nominal)

                        isr_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='ISRPartonShowerUp')[0]
                        isr_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='ISRPartonShowerDown')[0]
                        eff_isr_up = np.sum(isr_up)/np.sum(nominal)
                        eff_isr_do = np.sum(isr_do)/np.sum(nominal)

                        pdf_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='PDF_weightUp')[0]
                        pdf_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='PDF_weightDown')[0]
                        eff_pdf_up = np.sum(pdf_up)/np.sum(nominal)
                        eff_pdf_do = np.sum(pdf_do)/np.sum(nominal)
                        
                        if sName == 'ggF':
                            scale_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_7ptUp')[0]
                            scale_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_7ptDown')[0]
                            
                            eff_scale_up = np.sum(scale_up)/np.sum(nominal)
                            eff_scale_do = np.sum(scale_do)/np.sum(nominal)

                            sample.setParamEffect(scale_ggF,eff_scale_up,eff_scale_do)
                            sample.setParamEffect(pdf_Higgs_ggF,eff_pdf_up,eff_pdf_do)
                            sample.setParamEffect(fsr_ggF,eff_fsr_up,eff_fsr_do)
                            sample.setParamEffect(isr_ggF,eff_isr_up,eff_isr_do)

                        elif sName == 'VBF':
                            scale_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_3ptUp')[0]
                            scale_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_3ptDown')[0]

                            eff_scale_up = np.sum(scale_up)/np.sum(nominal)
                            eff_scale_do = np.sum(scale_do)/np.sum(nominal)

                            sample.setParamEffect(scale_VBF,eff_scale_up,eff_scale_do)
                            sample.setParamEffect(pdf_Higgs_VBF,eff_pdf_up,eff_pdf_do)
                            sample.setParamEffect(fsr_VBF,eff_fsr_up,eff_fsr_do)
                            sample.setParamEffect(isr_VBF,eff_isr_up,eff_isr_do)
                                
                        elif sName in ['WH','ZH','ggZH']:
                            scale_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_3ptUp')[0]
                            scale_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_3ptDown')[0]

                            eff_scale_up = np.sum(scale_up)/np.sum(nominal)
                            eff_scale_do = np.sum(scale_do)/np.sum(nominal)

                            if eff_scale_do < 0:
                                eff_scale_do = eff_scale_up

                            sample.setParamEffect(scale_VH,eff_scale_up,eff_scale_do)
                            sample.setParamEffect(pdf_Higgs_VH,eff_pdf_up,eff_pdf_do)
                            sample.setParamEffect(fsr_VH,eff_fsr_up,eff_fsr_do)
                            sample.setParamEffect(isr_VH,eff_isr_up,eff_isr_do)
                            
                        elif sName == 'ttH':
                            scale_up = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_7ptUp')[0]
                            scale_do = get_template(year, tag, sName, region, cat+'_', obs=msd, syst='scalevar_7ptDown')[0]

                            eff_scale_up = np.sum(scale_up)/np.sum(nominal)
                            eff_scale_do = np.sum(scale_do)/np.sum(nominal)

                            sample.setParamEffect(scale_ttH,eff_scale_up,eff_scale_do)
                            sample.setParamEffect(pdf_Higgs_ttH,eff_pdf_up,eff_pdf_do)
                            sample.setParamEffect(fsr_ttH,eff_fsr_up,eff_fsr_do)
                            sample.setParamEffect(isr_ttH,eff_isr_up,eff_isr_do)

                ch.addSample(sample)

            # END loop over MC samples 

            data_obs = get_template(year, tag, 'Jetdata', region, cat+'_', obs=msd, syst='nominal')

            ch.setObservation(data_obs[0:3])
                
    with open(os.path.join(str(datacard_dir), 'testModel_'+year+'.pkl'), 'wb') as fout:
        pickle.dump(model, fout)

    modeldir = os.path.join(str(datacard_dir), 'testModel_'+year)
    model.renderCombine(modeldir)

    out_cards = ""
    for card in total_model_bins:
        out_cards += f"{card}={card}.txt " 
    
    build_sh = os.path.join(modeldir, 'build.sh')
    with open(build_sh, "w") as f:
        f.write(f"combineCards.py {out_cards} > model_combined.txt\n")
        f.write(f"text2workspace.py {t2w_cfg} model_combined.txt")

if __name__ == '__main__':

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--year",
        help="year",
        type=str,
        required=True,
        choices=["2022", "2022EE", "2023", "2023BPix", "Run3"],
    )
    parser.add_argument(
        "--tag",
        help="tag",
        type=str,
        required=True,
    )

    args = parser.parse_args()

    ggfvbf_rhalphabet(args)
