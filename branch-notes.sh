#!/bin/bash
for BRANCH in `git branch -r | grep -v HEAD`
do
        git notes show ` git log ${BRANCH}  | head -n1 | cut -d ' ' -f  2 ` &> /dev/null
        if [ $? -eq 0 ]; then
                printf "$BRANCH\n"
                git notes show ` git log ${BRANCH}  | head -n1 | cut -d ' ' -f  2 ` | cat
                printf -- "------------------------------------------------------------\n"
        fi
done
