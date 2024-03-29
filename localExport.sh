#!/usr/bin/env bash

if which python3 >/dev/null 2>&1
then
    PYTHON3=python3
else
    PYTHON3=python
fi

if [ $# != 2 ]; then
    echo "Usage: " $0 " <raw export .tar.gz file> <dokuforge-export-static working copy>"
    exit 1
fi

RAWEXPORT=$1
EXPORTDIR=`dirname $1`
ACANAME=`basename $1 .tar.gz`
DFWORKDIR=work/example/df
DFACADIR=$DFWORKDIR/$ACANAME
EXPORTSTATICDIR=$2
EXPORTSTATICCLEANDIR=`mktemp -d`
EXPORTEDACAFILENAME=texexport_$ACANAME.tar
EXPORTEDACADIR=$EXPORTDIR/texexport_$ACANAME
CURRENTDIR=`pwd`

echo $EXPORTDIR
echo $ACANAME
echo $TMPDIR
echo $DFACADIR

if [ -d $DFACADIR ]; then
    echo $DFACADIR " exists, please remove and retry."
    exit 1
fi

if [ -e $EXPORTEDACAFILENAME ]; then
    echo $EXPORTEDACAFILENAME " exists, please remove and retry."
    exit 1
fi

if [ -d $EXPORTEDACADIR ]; then
    echo $EXPORTEDACADIR "exists, please remove and retry."
    exit 1
fi

# unpack raw export so that local df2 finds it
mkdir -p work/example/df
tar -C $DFWORKDIR -xvf $RAWEXPORT

# clean directory of dokuforge-export-static files (no local files, e.g., backups)
rmdir $EXPORTSTATICCLEANDIR
svn export $EXPORTSTATICDIR $EXPORTSTATICCLEANDIR

# perform actual export, this can take a few seconds without output
echo "Exporting ..."
printf 'commitid = "%s"' `git show -s --format=%H` > dokuforge/versioninfo.py \
    || rm dokuforge/versioninfo.py
$PYTHON3 -m dokuforge.export $DFWORKDIR $EXPORTSTATICCLEANDIR $ACANAME
echo "Done."
rm dokuforge/versioninfo.py

# unpack export
tar -C $EXPORTDIR -xvf $EXPORTEDACAFILENAME

# clean up files created during exporting
rm -rf $DFACADIR $EXPORTEDACAFILENAME $EXPORTSTATICCLEANDIR
