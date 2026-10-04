#!/usr/bin/env python3
"""Selected applications and their build dependencies; no implicit feature enabling."""
import argparse,json

def plan(board, network=False, tailscale=False, kvm=False, kiosk=False, receiver=False, print_server=False):
    if (kiosk or receiver) and board not in ('rock-5b','orangepi5-plus'):
        raise ValueError('F/G currently support rock-5b and orangepi5-plus only')
    return dict(board=board,network=network,tailscale=tailscale,kvm=kvm,
                kiosk=kiosk,receiver=receiver,print_server=print_server,usb_server=print_server or receiver,graphics=kiosk or receiver,
                cached_copy=kvm and (kiosk or receiver))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',required=True)
    for name in ['network','tailscale','kvm','kiosk','receiver','print-server']:p.add_argument('--'+name,choices=['true','false','yes','no'],default='no')
    a=vars(p.parse_args());print(json.dumps(plan(**{k.replace('-','_'):(v in ('yes','true') if k!='board' else v) for k,v in a.items()})))
