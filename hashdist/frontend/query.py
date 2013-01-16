from .parse_stack_spec import evaluate_dict_with_conditions
from ..core.utils import substitute

def normalize_cfg_vars(cfg):
    cfg = dict(cfg)
    if 'version' in cfg:
        cfg['version'] = str(cfg['version'])
    return cfg

def query_attrs(parsed_doc, cfg):
    attrs = evaluate_dict_with_conditions(parsed_doc, cfg)
    for key, value in attrs.items():
        if isinstance(value, basestring):
            attrs[key] = substitute(value, cfg)
    return attrs
