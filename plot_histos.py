import pickle
import numpy as np
import matplotlib.pyplot as plt
import hist
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import mplhep as hep

formatter = mticker.ScalarFormatter(useMathText=True)
formatter.set_powerlimits((-3, 3))
plt.rcParams.update({"font.size": 12})
plt.rcParams["lines.linewidth"] = 2
plt.rcParams["grid.color"] = "#CCCCCC"
plt.rcParams["grid.linewidth"] = 0.5
plt.rcParams["figure.edgecolor"] = "none"

# Load the histograms
with open("histograms_2023.pkl", "rb") as f:
    histograms = pickle.load(f)


print("Histograms loaded successfully!")

# HIGGS

from hist.intervals import ratio_uncertainty

def plot_stack(hists, type, pt):

    processes = ["Zto2Q", "Wto2Q", "Diboson", "TT", "VBF", "ggH", "WH", "ZH", "ttH"]

    h_t = [hists[sample][type][pt] for sample in processes]
    legends = [sample for sample in processes]
    colors = ['blue', 'green', 'red', 'purple', 'orange', 'magenta', 'cyan', 'teal' , 'brown'] # , 'pink', 'mediumslateblue'


    h_data = hists['data'][type][pt]


    # Calculate yields for each histogram (dynamically from the h_scaled list)
    yields = {legend: hist.values().sum() for legend, hist in zip(legends, h_t)}

    # Sort histograms by yield, keeping track of indices
    sorted_indices = sorted(range(len(h_t)), key=lambda i: yields[legends[i]], reverse=False)

    # Sort histograms, legends, and colors
    sorted_histograms = [h_t[i] for i in sorted_indices]
    sorted_legends = [legends[i] for i in sorted_indices]
    sorted_colors = [colors[i] for i in sorted_indices]

    # Add QCD histogram with scaling to the plot setup
    h_qcd = hists['QCD'][type][pt]
    h = [h_qcd] + sorted_histograms
    colors = ['gray'] + sorted_colors
    legends = [r"QCD"] + sorted_legends

    # Set up the figure
    fig, (ax, rax) = plt.subplots(
        2, 1, figsize=(12, 12), gridspec_kw={"height_ratios": [3.5, 1], "hspace": 0.18}, sharex=True
    )

    # Step 1: Identify the bin indices for 115 to 135 GeV range
    edges = h_data.axes[0].edges  # Assuming the first axis corresponds to mass/energy
    mask = (edges[:-1] >= 115) & (edges[:-1] < 130)  # Mask for bins in the specified range

    # Step 2: Set the values to zero for these bins in both data and total background
    data_val = h_data.values()
    data_val[mask] = 0  # Set bins to zero in the data histogram


    # Update the data histogram for plotting with masked values set to zero
    h_data.values()[:] = data_val  # Update h_data with modified values

    # First panel: Plot histograms with stacking
    ax.set_ylabel("Events")
    hep.histplot(h, ax=ax, stack=True, label=legends, color=colors, density=False, histtype="fill", edgecolor="black", linewidth=1)

    # Plot data as error bars
    hep.histplot(h_data, ax=ax, histtype="errorbar", color="black", label="Data")
    ax.legend(title=f"ptbin {pt}")
    ax.xaxis.grid(True, which="major")
    ax.yaxis.grid(True, which="major")
    ax.set_xlim(40, 200)
    ax.set_xlabel("mSD [GeV]")

    # Add legend
    hep.cms.label(
                    "Work in Progress",
                    fontsize=24,
                    data=True,
                    lumi="17.65",
                    year="2023",
                    ax=ax,
                    com="13.6",
                )

    # 2nd panel
    bg_total = sum(h_t, h_qcd) ## , h_qcd, h_diboson, h_tt
    tot_val = bg_total.values()
    tot_val[mask] = 0  # Set bins to zero in the background total
    tot_val_zero_mask = tot_val == 0
    bg_total.values()[:] = tot_val  # Update bg_total with modified values
    tot_val[tot_val_zero_mask] = 1
    data_val = h_data.values()
    data_val[tot_val_zero_mask] = 1
    yerr = ratio_uncertainty(data_val, tot_val, "poisson")
    yvalue = data_val / tot_val

    hep.histplot(yvalue, bg_total.axes[0].edges, yerr=yerr, ax=rax, histtype="errorbar", color="black")
    rax.set_ylabel("Data/MC")
    rax.set_ylim(0, 2.5)
    rax.set_xlabel("mSD [GeV]")
    rax.set_xlim(40, 200)
    rax.grid(axis="y")
    
    rax.axhline(1, color="black", linestyle="--")

    # Save individual histograms
    for name, histo in zip(["QCD"] + sorted_legends, [h_qcd] + sorted_histograms):
        fig_indiv, ax_indiv = plt.subplots(figsize=(8, 6))
        hep.histplot(histo, ax=ax_indiv, histtype="step", color="black")
        ax_indiv.set_title(f"{name} - {type} - ptbin {pt}")
        ax_indiv.set_xlabel("mSD [GeV]")
        ax_indiv.set_ylabel("Events")
        ax_indiv.set_xlim(40, 200)
        ax_indiv.grid(True)
        plt.savefig(f"hist_{name}_{type}_pt{pt}.jpg", dpi=300, bbox_inches='tight')
        plt.close(fig_indiv)

    # Save the plot before showing
    plt.savefig(f"stack_{type}_pt{pt}.jpg", dpi=300, bbox_inches='tight')

    #plt.show()

if __name__ == "__main__":

    ptbins = np.array([450,  500, 550, 600, 675, 800, 1200]) # 

    for pt in ptbins[:-1]:
        plot_stack(histograms, 'pass', pt)
        plot_stack(histograms, 'fail', pt) 
