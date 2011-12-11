\NeedsTeXFormat{LaTeX2e}[1995/12/01]

\ProvidesClass{cover}[2003/10/29 LaTeX2e JGW cover class]

%% Basisklasse: scrbook
\LoadClass[oneside]{scrbook}

\RequirePackage[latin9]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[ngerman]{babel}

\RequirePackage{graphicx}

%% Brotschrift: Palatino
\RequirePackage[osf,sc]{mathpazo}

\usepackage{pst-all}

\def\EV{e.\kern-0.1em V.}

\setlength{\oddsidemargin}{-1in}

\setlength{\topmargin}{-1in}
\setlength{\headheight}{0pt}
\setlength{\headsep}{0pt}

\setlength{\textwidth}{21cm}
\setlength{\textheight}{29.7cm}

\setlength{\parindent}{0pt}

\pagestyle{empty}

\newcommand{\cover}[4]{
~\vskip-1.8\baselineskip
\psset{xunit=1cm,yunit=1cm,dimen=middle}
%
% Schnittmarken
\rput[l]{90}(10,-29.7){%
\ifx\true#4%
\rput[l]{0}(0,+#1){\psline(0,0)(1,1)\psline(29.7,0)(28.7,1)}
\rput[l]{0}(0,-#1){\psline(0,0)(1,-1)\psline(29.7,0)(28.7,-1)}
% Ränder
\rput[l]{0}(0,+#1){\psline(0,0)(29.7,0)}
\rput[l]{0}(0,-#1){\psline(0,0)(29.7,0)}
\fi
% Eule
\rput[c]{270}(2.6,-0.05){\includegraphics[width=4mm]{logo}}
% Text
\rput[l]{0}( 4.0,-0.05){#2}
\rput[l]{0}(20.0,-0.05){#3}
%
}
\newpage
}
