from portal.models import Case
from . import mra
from . import view

registered = {Case.CaseType.MRA: mra.run,
              Case.CaseType.SVIEW: view.run}
