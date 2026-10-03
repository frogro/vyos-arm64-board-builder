#!/usr/bin/env python3
"""Selected applications and their build dependencies; no implicit feature enabling."""
import argparse,json

def plan(board, network=False, tailscale=False, kvm=False, kiosk=False, receiver=False):
    if board == 'radxa-e52c' and kvm:
        raise ValueError('E52C supports A-C only; KVM profile D is not supported')
    if (kiosk or receiver) and board not in ('rock-5b','orangepi5-plus','raspberry-pi-5'):
        raise ValueError('F/G require rock-5b, orangepi5-plus or raspberry-pi-5')
    return dict(board=board,network=network,tailscale=tailscale,kvm=kvm,
                kiosk=kiosk,receiver=receiver,graphics=kiosk or receiver,
                cached_copy=kvm and (kiosk or receiver))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',required=True)
    for name in ['network','tailscale','kvm','kiosk','receiver']:p.add_argument('--'+name,choices=['true','false','yes','no'],default='no')
    a=vars(p.parse_args());print(json.dumps(plan(**{k:(v in ('yes','true') if k!='board' else v) for k,v in a.items()})))
