
import hist


column_to_axis = {
    "HiggsAK8_pt": "pt1",
    "HiggsAK8_msdmatched": "msd1",
    "VAK8_pt": "pt2",
    "VAK8_msd": "msd2",
    "VBFPair_mjj": "mjj",
    "VBFPair_deta": "deta",
    "MET": "met",
    "LeadingLep_pt": "pt3",
    "SubLeadingLep_pt": "pt4",
    "LepPair_mass": "lepmass",
}

# Define the histogram axes
axis_to_histaxis = {
    "pt1": hist.axis.Regular(25, 250, 2500, name="pt1", label=r"Higgs AK8 $p_{T}$ [GeV]"),
    "pt2": hist.axis.Regular(25, 250, 2500, name="pt2", label=r"V AK8 $p_{T}$ [GeV]"),
    "pt3": hist.axis.Regular(25, 0, 1500, name="pt3", label=r"Leading Lepton $p_{T}$ [GeV]"),
    "pt4": hist.axis.Regular(25, 0, 200, name="pt4", label=r"Subleading Lepton $p_{T}$ [GeV]"),
    "msd1": hist.axis.Regular(23, 40, 201, name="msd1", label="Higgs AK8 $m_{sd}$ [GeV]"),
    "msd2": hist.axis.Regular(23, 40, 201, name="msd2", label="V AK8 $m_{sd}$ [GeV]"),
    "mass1": hist.axis.Regular(30, 0, 200, name="mass1", label="Higgs AK8 PNet mass [GeV]"),
    "category": hist.axis.StrCategory([], name="category", label="Category", growth=True),
    "genflavor": hist.axis.IntCategory([0, 1, 2, 3], name="genflavor", label="Gen Flavor"),
    "mjj": hist.axis.Regular(25, 0, 10000 , name="mjj", label="$m_{jj}$ [GeV]"),
    "deta": hist.axis.Regular(20, 2, 10 , name="deta", label="$d\eta_{jj}$ [GeV]"),
    "met": hist.axis.Regular(25, 0, 1000, name="met", label=r"Puppi MET [GeV]"),
    "lepmass": hist.axis.Regular(25, 0, 200, name="lepmass", label="$m_{ll}$ [GeV]"),
}