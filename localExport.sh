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
COMMITID=`git show -s --format=%H`
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
tar -C $DFWORKDIR -xvf $RAWEXPORT

# clean directory of dokuforge-export-static files (no local files, e.g., backups)
svn export $EXPORTSTATICDIR $EXPORTSTATICCLEANDIR

# perform actual export, this can take a few seconds without output
echo "Exporting ..."
python -m dokuforge.export $DFWORKDIR $EXPORTSTATICCLEANDIR $ACANAME
echo "Done."

# unpack export
tar -C $EXPORTDIR -xvf $EXPORTEDACAFILENAME

# add input to export
# for i in `find $DFACADIR -name "blob*,v"` `find $DFACADIR -name "Index,v"` `find $DFACADIR -name "isDeleted,v"` `find $DFACADIR -name "nextpage,v"` `find $DFACADIR -name "nextblob,v"`
# do
#     rm $i
# done

cd $DFACADIR
rm *,v
for d in *
do
    echo $d
    cd $d
    for i in *,v
    do
        echo $i
        co $i
        rm -f $i
    done
    shopt -s nullglob
    for i in title page* blob*.filename blob*.comment
    do
        echo $i >> input.txt
        cat $i >> input.txt
        echo >> input.txt
        rm -f $i
    done
    cd ..
done

for d in *
do
    cd $d
    if [ ! -d $EXPORTEDACADIR/$d ]; then
        mkdir $EXPORTEDACADIR/$d
    fi
    cp input.txt $EXPORTEDACADIR/$d/
    cd ..
done

cd $CURRENTDIR

# clean up files created during exporting
rm -rf $DFACADIR $EXPORTEDACAFILENAME $EXPORTSTATICCLEANDIR

# add warning about exporter version
echo "The precise semantics of the exporter is still"              >  $EXPORTEDACADIR/WARNING
echo "subject to discussion and may change in future versions."    >> $EXPORTEDACADIR/WARNING
echo "If you think you might need to reproduce an export with the" >> $EXPORTEDACADIR/WARNING
echo "same exporter semantics, keep the following version string"  >> $EXPORTEDACADIR/WARNING
echo "for your reference."                                         >> $EXPORTEDACADIR/WARNING
echo >> $EXPORTEDACADIR/WARNING
echo $COMMITID >> $EXPORTEDACADIR/WARNING
