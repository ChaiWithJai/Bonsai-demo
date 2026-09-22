"""Generation shape only; proposal.py remains the source-aware authority."""

def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}

def array(items, minimum=1, maximum=30):
    return {'type':'array','items':items,'minItems':minimum,'maxItems':maximum}

TEXT={'type':'string','minLength':1,'maxLength':2000}
FIELD={'type':'string','minLength':1,'maxLength':100}
SCALAR={'type':['string','number','boolean','null'],'maxLength':4000}
EVIDENCE=obj({'record_id':FIELD,'field':FIELD,'quote':TEXT})
STRUCTURE=obj({'rationale':TEXT,'records':array(obj({
    'values':{'type':'object','additionalProperties':SCALAR,'minProperties':1,'maxProperties':20},
    'evidence':array(EVIDENCE,1,5)
}))})
VIEW={'anyOf':[
    obj({'component':{'const':'RecordTable'},'columns':array(FIELD,1,20)}),
    obj({'component':{'const':'ForceDirectedGraph'},'groupBy':array(FIELD,1,3)}),
    *[obj({'component':{'const':name},'x':FIELD,'y':FIELD,'color':{'type':['string','null']}})
      for name in ('Scatterplot','LineChart')]
]}
PROPOSAL_SCHEMA=obj({
    'interpretation':obj({'findings':array(obj({'text':TEXT,'record_ids':array(FIELD,1,5)}),1,5),
                          'rationale':TEXT,'uncertainties':array(TEXT,0,8),'questions':array(TEXT,1,3)}),
    'structure':{'anyOf':[STRUCTURE,{'type':'null'}]},
    'plan':obj({'title':{'type':'string','minLength':1,'maxLength':1000},'summary':{'type':'string','minLength':1,'maxLength':1000},'fields':array(obj({'name':FIELD,'type':{'enum':['text','number','date','boolean']}}),1,100),
                'view':VIEW})
})


def generation_schema(schema):
    """Avoid native grammar repetition expansion; validators retain all bounds."""
    if isinstance(schema, dict):
        return {key:generation_schema(value) for key,value in schema.items()
                if key not in ('maxLength','maxItems','maxProperties','minProperties')}
    if isinstance(schema, list):
        return [generation_schema(value) for value in schema]
    return schema

GENERATION_SCHEMA = generation_schema(PROPOSAL_SCHEMA)
