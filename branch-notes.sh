#!/bin/sh
for BRANCH in `git branch -r --no-merged origin/master`
do
        git notes show ${BRANCH} >/dev/null 2>&1
        if [ $? -eq 0 ]; then
                printf "$BRANCH\n"
                git --no-pager notes show ${BRANCH}
                printf -- "------------------------------------------------------------\n"
        fi
done
