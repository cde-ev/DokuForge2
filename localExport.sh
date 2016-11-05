#!/usr/bin/env bash

if [ $# != 2 ]; then
    echo "Usage: " $0 " <raw export .tar.gz file> <dokuforge-export-static directory>"
    exit 1
fi

RAWEXPORT=$1
EXPORTDIR=`dirname $1`
ACANAME=`basename $1 .tar.gz`
DFWORKDIR=work/example/df
DFACADIR=$DFWORKDIR/$ACANAME
EXPORTSTATICDIR=$2
EXPORTSTATICCLEANDIR=`mktemp -d --dry-run`
EXPORTEDACAFILENAME=texexport_$ACANAME.tar
EXPORTEDACADIR=$EXPORTDIR/texexport_$ACANAME

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
tar -C $DFWORKDIR -xvf $RAWEXPORT

# clean directory of dokuforge-export-static files (no local files, e.g., backups)
svn export $EXPORTSTATICDIR $EXPORTSTATICCLEANDIR

# perform actual export, this can take a few seconds without output
echo "Exporting ..."
python -m dokuforge.export $DFWORKDIR $EXPORTSTATICCLEANDIR $ACANAME
echo "Done."

# unpack export
tar -C $EXPORTDIR -xvf $EXPORTEDACAFILENAME

# clean up files created during exporting
rm -rf $DFACADIR $EXPORTEDACAFILENAME $EXPORTSTATICCLEANDIR
