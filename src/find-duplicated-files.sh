#!/bin/env bash
#
# List duplicate files 
# Filse with the same size and same MD5 sum are grouped
# also files are sorted by size
#

# multiple folder are suuported as argoments, but you have to provide at leats one
# the output has to be redirected to a log file, so you can review it after that
# E.g. 
# find-duplicated-files.sh video photo music public | tee find_duplicated.log.txt
export SEARCH_PATH="$@"

echo Search in $SEARCH_PATH >&2


# files with size smaller than MIN_SIZE will be ignored
export MIN_SIZE=500k

echo Running find... >&2
find $SEARCH_PATH -type f -size +$MIN_SIZE  -printf "%-25s %p\n" |
   sort -n | uniq -D -w 25  > /tmp/dupsizes.$$


echo Calculating $(wc -l < /tmp/dupsizes.$$) check sums from file /tmp/dupsizes.$$ ... >&2
cat /tmp/dupsizes.$$ |
    sed -E 's/([^ ]*) +(.*)/printf "%-25d" \1 ; md5sum "\2" /eg' |
    sort -n | uniq -w57 --all-repeated=separate  > /tmp/dups.$$

echo Found $(grep -c . /tmp/dups.$$) duplicated files

while read size md5 filename
do
   if [[ ! -z "$filename" ]]; then
      ls -l "$filename"
   else
      echo
   fi
done < /tmp/dups.$$
