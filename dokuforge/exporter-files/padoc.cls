%% 
%% LaTeX2e-Dokumentenklasse f�r die Dokumentation der
%% JGW-PfingstAkademie
%% 
%% Marco Kuhlmann <kuhlmann@jgw-ev.de>
%% 
%% Copyright: Jugendbildung in Gesellschaft und Wissenschaft e.V.
%% 
%% $Id: padoc.cls,v 1.1 2003/05/21 21:32:45 kuhlmann Exp $
%% 

%%
%% Ver�ndert 2003/07/14 von Marc Sch�fer
%%
%% siehe Kommentare bei der Definition von \course und alles,
%% was mit "-- marc" markiert (ha ha. ein Wortspiel.) ist.
%%

\NeedsTeXFormat{LaTeX2e}[1995/12/01]

\ProvidesClass{padoc}[2007/01/03 LaTeX2e JGW document class]

%% Konfiguration: Dateinamen. #1 ist die Kursnummer -- marc 2003/08/06

%\newcommand*{\@photoname}[1]{kurs#1/fig_#1_kursfoto_web}
\newcommand*{\@photoname}[1]{images/fig_#1_kursfoto.jpg}
\newcommand*{\@membername}[1]{kurs#1/teilnehmer_#1}

%% Basisklasse: scrreprt

\LoadClass[headsepline,smallheadings]{scrbook}

%% Ver�nderungen gegen�ber der Basisklasse:

\raggedbottom

%% (1) Die �berschriften sollen in der Schrift f�r den Brottext
%% erscheinen.

\renewcommand*{\sectfont}{%
  \normalfont\normalcolor\rmfamily\bfseries}

%% (2) Formatierung der Fu�noten

\deffootnote{1.5em}{1.5em}{%
  \textsuperscript{\normalfont\thefootnotemark\ }}

%% (3) Das \cleardoublepage-Makro von KOMA-Script l�sst leere
%% Seiten zwischen Kapiteln nicht wirklich leer.

\def\cleardoublepage{%
  \clearpage%
  \if@twoside%
    \thispagestyle{empty}%
    \ifodd\c@page \else
      \null\newpage\if@twocolumn \null\newpage \fi
    \fi
  \fi}

%% Spiegelstriche in Aufzaehlungen
\renewcommand{\labelitemi}{--}

% Kursphotos sollen auf geraden Seiten beginnen, was dieses Makro
% f�r uns �bernimmt. -- marc 2003/08/06

\def\clearoneandahalfpage%
  {\clearpage
   \if@twoside
     \markboth{}{}
     \ifodd\c@page
       \null\newpage
       \if@twocolumn \null\newpage \fi
     \fi
   \fi}

%% Standardm��ig geladene Pakete

\RequirePackage[latin9]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[ngerman]{babel}

\RequirePackage{graphicx}
\RequirePackage{relsize}
\RequirePackage{booktabs}
\RequirePackage{setspace}
\RequirePackage{titlesec}

\RequirePackage{ae}

\RequirePackage{itemize}
\RequirePackage{parallel}
\RequirePackage{pmhalign}

%% Typewriter: Lucida Typewriter
%\RequirePackage[seriftt]{lucidabr}
%\RequirePackage{lucidabr}

%% Serifenlose (Optima; Zapf Humanist):
%\RequirePackage[scaled=0.9]{boptima}

\renewcommand{\sfdefault}{uop}

%% Brotschrift: Palatino
\RequirePackage[osf,sc]{mathpazo}

%% Use the microtype package (if available)
\IfFileExists{microtype.sty}{%
  \RequirePackage[tracking=true]{microtype}%
  \UseMicrotypeSet[tracking]{smallcaps}%
  \SetTracking{encoding=*,shape=sc}{30}
}{}

%% Einige Layout-Ma�e beziehen sich auf die im Folgenden
%% definierte Einheit \padoc@hunit, die Breite eines M in
%% normalgro�er Brotschrift.

\newdimen\padoc@hunit
\setbox\@tempboxa\hbox{\normalfont\normalsize M}%
\padoc@hunit=\wd\@tempboxa

%% Die Palatino sollte mit einem leicht h�heren Zeilenabstand
%% gesetzt werden als die Computer Modern:

\setstretch{1.1}

%% Seitenspiegel

\RequirePackage
  [a4paper, left=3.3cm, right=2.8cm,
            top=2.5cm,  bottom=4.2cm,
	    twoside]%
  {geometry}

%% Nur Kurse im Inhaltsverzeichnis
\setcounter{tocdepth}{0}

% Das Inhaltsverzeichnis soll auf eine Seite passen - also stauchen
% wir etwas. Ausserdem soll das ganze Layout anders werden.

\RequirePackage{titletoc}

\titlecontents{chapter}
  [2.3em]
  {\vspace{1em}}
  {\contentslabel[\hfill\thecontentslabel\quad]{2.3em}}
  {\hspace*{-2.3em}}
  {\enskip$\cdot$\enskip\thecontentspage}


%% �berschriften

%% Die Abschnitts�berschriften werden in einem eigenen, mageren Font
%% nummeriert, eine Gr��enstufe kleiner als die �berschrift selbst (hier
%% sind die Gr��en von smallheadings aus scrreprt.cls zu Grunde gelegt):

\newcommand*{\sectnumfont}%
  {\normalfont\normalcolor}

\let\size@chapternum\large
\let\size@sectionnum\normalsize
\let\size@subsectionnum\normalsize
\let\size@subsubsectionnum\normalsize
\let\size@paragraphnum\normalsize
\let\size@subparagraphnum\normalsize

\titleformat{\chapter}%
  {\size@chapter\sectfont}%
  {\size@chapternum\sectnumfont\thechapter}%
  {1em}{}

\titlespacing*{\chapter}%
  {0pt}{2\baselineskip}{1\baselineskip}

\titleformat{\section}%
  {\size@section\sectfont}%
  {\size@sectionnum\sectnumfont\thesection}%
  {1em}{}

\titlespacing*{\section}%
  {0pt}{1\baselineskip}{1\baselineskip}

\titleformat{\subsection}%
  {\size@subsection\sectfont}%
  {\size@subsectionnum\sectnumfont\thesubsection}%
  {1em}{}

\titlespacing*{\subsection}%
  {0pt}{1\baselineskip}{0pt}

\titleformat{\subsubsection}%
  {\size@subsubsection\sectfont}%
  {\size@subsubsectionnum\sectnumfont\thesubsubsection}%
  {1em}{}

\titlespacing*{\subsubsection}%
  {0pt}{1\baselineskip}{0pt}

%% Die Breite der �berschriftennummerierung soll sich dynamisch
%% der Breite der breitesten �berschriftennummerierung anpassen.
%% Dazu wird das titlesec-Makro \ttlh@hang aufgebohrt, das die an
%% der Nummerierung "h�ngenden" �berschriften generiert.  Die
%% �nderungen sind minimal: Statt den h�ngenden Text (#2) direkt
%% einzuf�gen, wird er zun�chst durch das Makro
%% \padoc@adjusthangwidth geschleust, welches ggf. die global
%% g�ltige maximale Breite �ndert.

\newdimen\padoc@sectionhangwidth
\padoc@sectionhangwidth=0pt

\newdimen\padoc@maxsectionhangwidth
\padoc@maxsectionhangwidth=0pt

\def\padoc@adjusthangwidth#1{%
  \setbox\@tempboxa\hbox{#1}%
  \@tempdima=\wd\@tempboxa
  \ifdim\@tempdima>\padoc@maxsectionhangwidth
    \global\padoc@maxsectionhangwidth=\@tempdima
  \fi
  \ifdim\padoc@sectionhangwidth>0pt
    \makebox[\padoc@sectionhangwidth]{\unhbox\@tempboxa\hfill}%
  \else%
    \unhbox\@tempboxa
  \fi}

\def\ttlh@hang#1#2#3#4#5#6#7#8{%
  \gdef\ttl@makeline##1{\hspace{#6}##1\hspace{#7}}%
  \setlength\leftskip{#6}%
  \setlength\rightskip{#7}%
  \interlinepenalty\@M
  \ttl@beginlongest
  #1{%
      \ttl@glcmds
      \parindent\z@
      \leavevmode
      \begingroup
        \ifttl@label
          \sbox\z@{\padoc@adjusthangwidth{#2}\strut\hspace{\padoc@hunit}}%
          \advance\leftskip\wd\z@
          \llap{\box\z@}%
        \fi
        #4{#8}\kern\z@\strut\@@par
      \endgroup
      \nobreak\ttl@midlongest#5\@@par}%
  \ttl@endlongest}

%% Die jeweils letzte maximale �berschriftennummerierungsbreite
%% wird am Ende eines LaTeX-Laufes in die *.aux-Datei
%% geschrieben, sodass sie beim n�chsten Mal als Default
%% verf�gbar ist.

\AtEndDocument{%
  \if@filesw\immediate\write\expandafter\@mainaux\fi%
  {\string\global\string\padoc@sectionhangwidth=\the\padoc@maxsectionhangwidth}}

%% Autorennamen

\newcommand*{\authorfont}{\normalfont\normalcolor\scshape}

\let\auth@chapter\chapter       \def\chapter{\def\auth@lastsectype{1}\auth@chapter}
\let\auth@section\section       \def\section{\def\auth@lastsectype{2}\auth@section}
\let\auth@subsection\subsection \def\subsection{\def\auth@lastsectype{3}\auth@subsection}

\def\authors%
  {\@ifstar\authors@star\authors@nostar}
\def\authors@nostar#1%
  {\par\nobreak
  \ifnum\auth@lastsectype<3
  \vskip-\baselineskip
  \fi
  \smallskip
  \@hangfrom%
  {\hskip\padoc@sectionhangwidth\hspace{\padoc@hunit}}%
  {{\smaller\authorfont #1}}%
  \par\nobreak
  \ifnum\auth@lastsectype<3
    \vskip\baselineskip
  \else
  \smallskip
  \fi
  \@afterheading}
\def\authors@star#1%
  {\par\nobreak
  \addvspace{-\baselineskip}%
  \smallskip
{\smaller\authorfont #1}%
  \par\nobreak
  \ifnum\auth@lastsectype<3
    \vskip\baselineskip
  \else
  \smallskip
  \fi
  \@afterheading}


%% Kurs�berschrift

%
% Die Kapitelnummer jeder Kursdokumentation soll mit der Kursnummer
% �bereinstimmen. Dies wurde bis dato durch manuelles �ndern des
% chapter-Counters mittels \addtocounter{chapter} erreicht, was mir
% a) nicht gef�llt und b) den Export erschwert. Daher nimmt \course
% ab sofort die Kursnummer als Argument vor dem Kurstitel und setzt
% die Kapitelnummer auf die Kursnummer _herauf_ - m��te heruntergesetzt
% werden, wird die Nummer wie gehabt um eins erh�ht. -- marc 2003/07/14
%

%
% Kursphotos werden auf geraden Seiten gesetzt, ihr Name ist hardgecoded
% (siehe Konfiguration). Dabei wird die openany-Option ignoriert.

\newcommand{\course}[1]{% -- marc 2003/08/06
  % { marc 2003/08/06 
  \clearoneandahalfpage
  \thispagestyle{plain}%
  \c@ursephoto{#1}%
  \vfil\newpage
  % }
  \thispagestyle{\chapterpagestyle}%
  \global\@topnum\z@
  % { marc 2003/08/06
  %\ifx#1\@empty\else
  %  \@hangfrom{\hskip\padoc@sectionhangwidth\hspace{\padoc@hunit}}%
  %  {\includegraphics[height=50mm]{#1}}%
  %  \par\nobreak
  %  \addvspace{-.5\baselineskip}%
  %\fi
  %\@afterindentfalse
  % }
  % { marc 2003/07/14
  \count@#1\relax % -- marc 2003/08/06
  \advance\count@\m@ne
  \ifnum\value{chapter}<\count@
    \setcounter{chapter}{\the\count@}%
  \fi
  % }
  \secdef\@chapter\@schapter}

\def\c@ursephoto#1% -- marc 2003/08/06, changed 2004/12/06
  {\openin\@inputcheck=\@photoname{#1} %
   \ifeof\@inputcheck
     \closein\@inputcheck
   \else
     \closein\@inputcheck
     \bgroup
       \noindent\includegraphics[width=\hsize]{\@photoname{#1}}\par
       \small\cp@readmember{\@membername{#1}}%
     \egroup
   \fi}

\newread\@memberlist

\def\cp@readmember#1%
  {\bgroup
   \setbox0=\hbox{}% f�r den Fall, da� die Memberlist leer ist -- marc 2004/12/06
   \openin\@memberlist#1 %
   \global\let\cp@separator\cp@theseparator
   \raggedright\small\sloppypar
   \ifeof\@memberlist\else
     \expandafter\cp@processline
   \fi
   \unhbox0\par
   \closein\@memberlist
   \egroup}

\bgroup
  \catcode`\[=\active
  \catcode`\*=\active
  \gdef\cp@activatespecials%
    {\catcode`\[=\active
     \catcode`\*=\active
     \def[##1]{\strut\gdef\cp@dospecial{\cp@doheadline{##1}}}%
     \def*{\strut\global\let\cp@dospecial\cp@doleiter}}
\egroup

\def\cp@theseparator%
  {\discretionary{}{}{\hbox{$\;\cdot\;$}}}
\def\cp@disablenextseparator%
  {\gdef\cp@separator{\global\let\cp@separator\cp@theseparator}}
\let\cp@separator\cp@theseparator

\def\cp@doheadline#1%
  {\par\bigskip\noindent
   \hbox{\bf\strut\ignorespaces #1\unskip\quad}\nobreak
   \cp@disablenextseparator}
\def\cp@doleiter%
  {\setbox0=\hbox{\it\ignorespaces\curline\unskip}\cp@domember}
\def\cp@domember%
  {\cp@separator\strut\box0}

\def\cp@processline%
  {\bgroup
     \cp@activatespecials
     \read\@memberlist to\curline
     \let\cp@dospecial\cp@domember
     \setbox0=\hbox{\ignorespaces\curline\unskip}% this might redefine cp@dospecial
     \ifdim\ht0>2pt%
       \cp@dospecial
     \fi
   \egroup
   \ifeof\@memberlist\else
     \expandafter\cp@processline
   \fi}

%% Einstellungen f�r Gleitobjekte

\setcounter{topnumber}{1}
\setcounter{bottomnumber}{1}

\renewcommand*{\capfont}{\normalfont\small}
\renewcommand*{\caplabelfont}{\normalfont\small\bfseries}

\setcaphanging
\setcapindent{0ex}

%% Hurenkinder verbieten

\widowpenalty=\@M

%% Extra-Kerning f�r Guillemets

\DeclareTextCommand{\glqq}{T1}{\guillemotright\kern.1ex}
\DeclareTextCommand{\grqq}{T1}{\kern.1ex\guillemotleft}

\endinput