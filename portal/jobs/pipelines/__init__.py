from portal.models import Case
from . import mra

registered = {Case.CaseType.MRA.label: mra.run}
