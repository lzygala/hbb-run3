#!/bin/bash

# remove old files
rm *.pkl
rm *.parquet

for t2_prefix in ${t2_prefixes}
do
    for folder in pickles parquet root githashes
    do
        xrdfs $${t2_prefix} mkdir -p "/${outdir}/$${folder}"
    done
done

# clone repository
# try 3 times in case of network errors
(
    r=3
    # shallow clone of single branch (keep repo size as small as possible)
    while ! git clone --single-branch --branch $branch --depth=1 https://github.com/DAZSLE/hbb-run3.git
    do
        ((--r)) || exit
        sleep 60
    done
)
cd hbb || exit

commithash=$$(git rev-parse HEAD)
echo "https://github.com/DAZSLE/hbb-run3/commit/$${commithash}" > commithash.txt

#move output to t2s
for t2_prefix in ${t2_prefixes}
do
    xrdcp -f commithash.txt $${t2_prefix}/${outdir}/githashes/commithash_${jobnum}.txt
done

pip install -e .

# run code (saving skim always)
python -u -W ignore $script --year $year --starti $starti --endi $endi --samples $sample --subsamples $subsample --nano-version ${nano_version} --save-skim

#move output to t2s
for t2_prefix in ${t2_prefixes}
do
    xrdcp -f *.pkl "$${t2_prefix}/${outdir}/pickles/out_${jobnum}.pkl"
    xrdcp -f *.parquet "$${t2_prefix}/${outdir}/parquet/out_${jobnum}.parquet"
done

rm *.parquet
rm *.pkl
rm commithash.txt
