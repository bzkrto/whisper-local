"""Word error rate for a supplied reference sentence; not a confidence probability."""
import re
from whisper.common import fold

def word_error_rate(reference, heard):
    expected=re.findall(r'\w+',fold(reference))
    actual=re.findall(r'\w+',fold(heard))
    row=list(range(len(actual)+1))
    for i,word in enumerate(expected,1):
        previous=row;row=[i]
        for j,other in enumerate(actual,1):
            row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(word!=other)))
    return row[-1]/max(1,len(expected))
