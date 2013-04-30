#!/bin/sh
for BRANCH in `git branch -r | grep -v HEAD`
do
        git notes show ${BRANCH} &> /dev/null
        if [ $? -eq 0 ]; then
                printf "$BRANCH\n"
                git --no-pager notes show ${BRANCH}
                printf -- "------------------------------------------------------------\n"
        fi
done
