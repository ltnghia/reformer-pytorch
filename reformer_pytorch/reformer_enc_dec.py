import re
import torch
from torch import nn
from reformer_pytorch.reformer_pytorch import ReformerLM
from reformer_pytorch.autopadder import Autopadder
from reformer_pytorch.generative_tools import TrainingWrapper

ENC_PREFIX = 'enc_'
DEC_PREFIX = 'dec_'

def group_dict_by_key(cond, d):
    return_val = [dict(),dict()]
    for key in d.keys():
        match = bool(cond(key))
        ind = int(not match)
        return_val[ind][key] = d[key]
    return (*return_val,)

def string_begins_with(prefix, str):
    return bool(re.match(f'^{prefix}', str))

def group_by_key_prefix(prefix, d):
    return group_dict_by_key(lambda x: string_begins_with(prefix, x), d)

def group_by_key_prefix_and_remove_prefix(prefix, d):
    kwargs_with_prefix, kwargs = group_dict_by_key(lambda x: string_begins_with(prefix, x), d)
    kwargs_without_prefix = dict(map(lambda x: (x[0][len(prefix):], x[1]), tuple(kwargs_with_prefix.items())))
    return kwargs_without_prefix, kwargs

def extract_enc_dec_kwargs(kwargs):
    enc_kwargs, kwargs = group_by_key_prefix_and_remove_prefix(ENC_PREFIX, kwargs)
    dec_kwargs, kwargs = group_by_key_prefix_and_remove_prefix(DEC_PREFIX, kwargs)
    return enc_kwargs, dec_kwargs, kwargs

class ReformerEncDec(nn.Module):
    def __init__(self, **kwargs):
        super().__init__()
        enc_kwargs, dec_kwargs, kwargs = extract_enc_dec_kwargs(kwargs)
        
        assert 'return_embedding' not in enc_kwargs, 'you cannot manually set the return embeddings flag for the encoder'
        assert 'dim' not in dec_kwargs and 'dim' not in enc_kwargs, 'you must set the dim for both encoder and decoder'

        enc_kwargs['return_embeddings'] = True
        enc_kwargs['dim'] = kwargs['dim']
        enc_kwargs.setdefault('bucket_size', 64)

        dec_kwargs['dim'] = kwargs['dim']
        dec_kwargs.setdefault('bucket_size', enc_kwargs['bucket_size'] * 2)

        enc = ReformerLM(**enc_kwargs)
        dec = ReformerLM(**dec_kwargs)

        self.enc = Autopadder(enc)
        self.dec = TrainingWrapper(dec)

    def generate(self, seq_in, seq_out_start, seq_len, **kwargs):
        enc_kwargs, dec_kwargs, kwargs = extract_enc_dec_kwargs(kwargs)
        enc_keys = self.enc(seq_in, **enc_kwargs)
        return self.dec.generate(seq_out_start, seq_len, keys = enc_keys, **{**dec_kwargs, **kwargs})

    def forward(self, seq_in, seq_out, return_loss = False, **kwargs):
        enc_kwargs, dec_kwargs, kwargs = extract_enc_dec_kwargs(kwargs)
        enc_keys = self.enc(seq_in, **enc_kwargs)
        dec_kwargs.setdefault('context_mask', enc_kwargs['input_mask'])
        return self.dec(seq_out, return_loss = return_loss, keys = enc_keys, **dec_kwargs)
