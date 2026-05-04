
#!/bin/bash

# remove old files
rm -r local_hvv/
mkdir local_hvv/

tag="hvv_26May4"
process_tag="merged_2lep_1FJ_r3_2lep_1FJ_20260430155132"
basedir="/eos/user/r/rband/HVV2LRDF/2lep_1FJ_r3_2lep_1FJ/"
indir="${basedir}/merged_2lep_1FJ_r3_2lep_1FJ_20260430155132_2lep_1FJ/"
outdir="/store/group/lpchbbrun3/lzygala/${tag}/${process_tag}"

xrdcp "root://eosuser.cern.ch///${basedir}/${process_tag}.json" .

count=0
for process in $(jq -r '.samples | keys[]' "${process_tag}.json")
do
    echo "Processing sample: $process"
    # ((count++))
    # if [[ $count -ge 2 ]]; then
    #     echo "Stopping after 2 samples (test mode)"
    #     break
    # fi
    for folder in pickles parquet
    do
        xrdfs root://cmseos.fnal.gov// mkdir -p "/${outdir}/${process}/${folder}"
    done

    xrdfs root://eosuser.cern.ch ls "${indir}/${process}" | while IFS= read -r infile 
    do
        echo "Processing: $infile"

        base=$(basename "$infile") 
        jobnum=${base#output_}
        jobnum=${jobnum%.root} 

        # Example: pass to your command
        python src/run.py --year 2024 --nano-version v15 --save-skim  --files root://eosuser.cern.ch//${infile}


        # Move final output to EOS
        # This new logic recursively copies the region directories created by the processor

        # --- FINAL COPY LOGIC ---
        # This logic creates the nested structure and partN.parquet names

        xrdfs root://cmseos.fnal.gov// mkdir -p "/${outdir}/${process}/pickles"
        xrdcp -f *.pkl "root://cmseos.fnal.gov///${outdir}/${process}/pickles/out_${jobnum}.pkl"

        # 2. Next, handle the combined parquet files
        for file in local_hvv/*.parquet; do
            # Extract the region name from the local filename (e.g., gets "control-tt" from "control-tt.parquet")
            base_file=$(basename "${file}" ".parquet")
            region_name="${base_file##*_}"
            jer_name="${base_file%_*}"

            # Create the region-specific subdirectory on EOS
            xrdfs root://cmseos.fnal.gov// mkdir -p "/${outdir}/${process}/parquet/${jer_name}/${region_name}"

            # Define the final filename using the job number for uniqueness
            final_filename="part${jobnum}.parquet"

            # Copy the file to its final, nested destination with the new name
            xrdcp -f "$file" "root://cmseos.fnal.gov///${outdir}/${process}/parquet/${jer_name}/${region_name}/${final_filename}"
        done


        rm local_hvv/*.parquet
        rm local_hvv/*.pkl


    done
    


done
