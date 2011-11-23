#!/usr/bin/env python
from dokuforge.academy import Academy
from dokuforge.exporter import Exporter

aca = Academy("work/example/df/za2011-1", lambda: {'cde': "CdE-Akademien"})
exporter = Exporter(aca)
exporter.export()
