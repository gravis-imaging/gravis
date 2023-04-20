from portal.models import Case
from . import mra
from . import onco
from . import view

registered = { Case.CaseType.ONCO:   onco.run,
               Case.CaseType.MRA:    mra.run,
               Case.CaseType.SVIEW:  view.run }