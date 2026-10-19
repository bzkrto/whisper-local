"""One semantic inference extracts intent/entities and proposes validated tool calls."""
from .action_agent import TOOLS
from .structured import obj, string, array, validate

# The transport constrains each tool and its exact argument names. The executor's
# existing validate_plan additionally checks values, installed apps and permissions.
def argument(name):
    if name in ('hours','level'):return {'type':'integer'}
    if name=='value':return {'anyOf':[{'type':'null'},{'type':'integer'},{'type':'string'},{'type':'array','items':{'type':'integer'},'minItems':2,'maxItems':2}]}
    if name=='id':return {'anyOf':[{'type':'integer'},{'type':'string'}]}
    return {'type':'string'}

META=obj({'intent':string(1,80),'entities':array(obj({'type':string(1,50),'value':string(1,200)}),0,10),'missing_fields':array(string(1,100),0,6)})
STEP_SCHEMA={'anyOf':[
    obj({'tool':{'type':'string','enum':[tool]},'args':obj({name:argument(name) for name in sorted(fields)})})
    for tool,fields in TOOLS.items()]}
# Couple kind and steps at generation time. The application still validates the
# entire plan independently; a server ignoring this grammar grants no authority.
PLAN_SCHEMA={'oneOf':[obj({**META['properties'],
    'kind':{'type':'string','enum':[kind]},'message':string(0,400),
    'steps':{'type':'array','minItems':1 if kind=='action' else 0,
             'maxItems':5 if kind=='action' else 0,'items':STEP_SCHEMA}})
    for kind in ('action','chat','clarification')]}
PLAN_FIELDS=set(META['properties'])|{'kind','message','steps'}

def parse_semantic_plan(data):
    if not isinstance(data,dict) or set(data)!=PLAN_FIELDS:raise ValueError('Niyet planı alanları geçersiz.')
    meta={key:data[key] for key in META['properties']};validate(meta,META)
    return {key:data[key] for key in ('kind','message','steps')},meta
