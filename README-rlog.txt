The current code is based on rlog, as found in FreeBSD. It contains
a patch by phk@, which can be seen below. As dokuforge2 should run
on generic rcs we have to build a workaround. Nevertheless, we
document the patch FYI.

hilbert# cd /usr/src/gnu/usr.bin/rcs
hilbert# cvs diff -r1.5 -r1.2 rlog.c
Index: rlog.c
===================================================================
RCS file: /usr/ctm/cvs-cur/src/gnu/usr.bin/rcs/rlog/rlog.c,v
retrieving revision 1.5
retrieving revision 1.2
diff -r1.5 -r1.2
39,48d38
<  * Revision 1.4  1994/05/12  00:37:59  phk
<  * made -v produce tip-revision, which was what I wanted in the first place...
<  *
<  * Revision 1.3  1994/05/11  22:39:44  phk
<  * Added -v option to rlog.  This gives a quick way to get a list of versions.
<  *
<  * Revision 1.2  1993/08/06  16:47:16  nate
<  * Have rlog output be much easier to parse.  (Added one line which is not
<  * used by any CVS/RCS commands)
<  *
207c197
< mainProg(rlogId, "rlog", "$Id: rlog.c,v 1.4 1994/05/12 00:37:59 phk Exp $")
---
> mainProg(rlogId, "rlog", "$Id: rlog.c,v 1.1.1.1 1993/06/18 04:22:17 jkh Exp $")
210c200
<               "\nrlog usage: rlog -{bhLRt} [-v[string]] -ddates -l[lockers] -rrevs -sstates -w[logins] -Vn file ...";
---
>               "\nrlog usage: rlog -{bhLRt} -ddates -l[lockers] -rrevs -sstates -w[logins] -Vn file ...";
223,224d212
<       int versionlist;
<       char *vstring;
229,230c217
<       versionlist = onlylockflag = onlyRCSflag = false;
<       vstring=0;
---
>       onlylockflag = onlyRCSflag = false;
293,297d279
<               case 'v':
<                       versionlist = true;
<                       vstring = a;
<                       break;
< 
347,352d328
<           if ( versionlist ) {
<               gettree();
<               aprintf(out, "%s%s %s\n", vstring, workfilename, tiprev());
<               continue;
<           }
< 
hilbert#
