#!/bin/sh
for BRANCH in `git branch -r | grep -v HEAD`
do
        git notes show ` git --no-pager log -1 --format=%H ${BRANCH} ` &> /dev/null
        if [ $? -eq 0 ]; then
                printf "$BRANCH\n"
                git --no-pager notes show ` git --no-pager log -1 --format=%H ${BRANCH} `
                printf -- "------------------------------------------------------------\n"
        fi
done
