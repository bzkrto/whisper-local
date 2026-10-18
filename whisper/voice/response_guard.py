"""Prevent unexecuted model action claims from reaching speech."""
import re
from ..common import fold
WARNING='Bu işlemi çalıştırmadım. Komutu desteklenen araçlarla eşleştiremedim.'

def unexecuted_action_claim(text):
    t=fold(text)
    return bool(re.search(r'\b(?:aciyorum|actim|baslatiyorum|baslattim|calistiriyorum|calistirdim|siliyorum|sildim|yukluyorum|yukledim|kaydediyorum|kaydettim|not aldim|hafizama aldim|gonderiyorum|gonderdim)\b',t))
