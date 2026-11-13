"""Fixed corpus, exhaustive algebra checks, fresh embedder and receiver processes."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image
import protocol as pr
import wire

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
D = BASE/'evidence'


def save(name, obj):
    with (D/name).open('x') as f:
        json.dump(obj, f, indent=2)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rejection(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    raise AssertionError('expected rejection')


def run(args, log):
    start = time.perf_counter()
    cp = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                        env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
    with log.open('x') as f:
        f.write(cp.stdout+cp.stderr)
    if cp.returncode:
        raise RuntimeError(cp.stdout+cp.stderr)
    return time.perf_counter()-start


def main():
    D.mkdir(exist_ok=False)
    save('protocol_identity.json', dict(protocol_sha256=sha(BASE/'PROTOCOL.md'),
                                      checkpoint_sha256=sha(ROOT/'models/v4_patch3.pth'),
                                      source_sha256={p.name:sha(p) for p in [BASE/'protocol.py',BASE/'wire.py',BASE/'run_gate.py']}))
    old = pr.shared()
    assert all(wire.allocation(e) == old._compute_bpp_and_range(e) for e in range(256))
    failures = 0
    pairs = words = 0
    for p in range(256):
        for x in range(256):
            n, lo, hi = wire.allocation(abs(x-p))
            pairs += 1
            words += 1 << n
            if not n:
                continue
            modulus = 1 << (8-n)
            cs = [v for v in range(x % modulus, 256, modulus) if lo <= abs(v-p) <= hi]
            failures += cs != [x]
    assert failures == 0
    save('algebra.json', dict(pairs=pairs, all_payload_words_covered=words,
                             failures=failures, codebook=wire.BOOK.tolist(),
                             proof='Candidate set depends only on retained residue; all 2^n MSB words leave it unchanged.',
                             production_mapping_identical=True))
    import torch
    model = old.model()
    initial_state = {k:v.clone() for k,v in model.state_dict().items()}
    master = bytes(range(32))  # Public reproducible test key, not a deployed secret.
    rng = np.random.default_rng(20261022)
    sources = sorted((ROOT.parent/'data/kodak_gray').glob('*.png'))
    assert len(sources) == 6
    corpus = [(p.name, np.array(Image.open(p).convert('L')), str(p), sha(p)) for p in sources]
    corpus += [('constant128', np.full((128,128),128,np.uint8), 'synthetic', None),
               ('random256', rng.integers(0,256,(256,256),dtype=np.uint8), 'synthetic', None),
               ('tiny8', np.full((8,8),128,np.uint8), 'synthetic', None)]
    capacities, results, negative = [], [], []
    save('corpus.json', [dict(name=n, source=s, file_sha256=h, shape=list(a.shape),
                              pixels_sha256=hashlib.sha256(a.tobytes()).hexdigest()) for n,a,s,h in corpus])
    sequence = 0
    for name, original, source, source_sha in corpus:
        start = time.perf_counter()
        try:
            q = pr.prepare(original)
        except ValueError as e:
            row = dict(image=name, accepted=False, reason=str(e), prepare_seconds=time.perf_counter()-start)
            capacities.append(row)
            print('REJECT', row, flush=True)
            continue
        row = dict(image=name, shape=list(original.shape), source=source,
                   prepare_seconds=time.perf_counter()-start, **q['stats'])
        capacities.append(row)
        print('CAPACITY', row, flush=True)
        if not row['accepted']:
            reason = rejection(lambda: pr.reserve(original,master,999,prepared=q))
            negative.append(dict(image=name, budget_rejection=reason))
            continue
        # Assert arbitrary candidate modifications preserve masked patches and predictions.
        y,x = q['ys'],q['xs']
        changed = original.copy()
        changed[y,x] = rng.integers(0,256,len(y),dtype=np.uint8)
        assert np.array_equal(old.predict(changed,y,x), q['floats'])
        for case, plen in [('empty',0),('short',37),('partial',q['net']//2),('full',q['net'])]:
            sequence += 1
            nonce = 202610220000+sequence
            start = time.perf_counter()
            reserved, capability = pr.reserve(original, master, nonce, prepared=q)
            reserve_seconds = time.perf_counter()-start
            # Payload is created strictly after reservation and encryption.
            payload = rng.integers(0,2,plen,dtype=np.uint8)
            stem = name.replace('.','_')+'_'+case
            reserved_file = D/(stem+'_reserved.png')
            input_payload = D/(stem+'_input.npy')
            cipher_file = D/(stem+'_cipher.png')
            recovered_file = D/(stem+'_recovered.npy')
            extracted_file = D/(stem+'_extracted.npy')
            embed_audit = D/(stem+'_embed.json')
            receive_audit = D/(stem+'_receive.json')
            Image.fromarray(reserved).save(reserved_file)
            np.save(input_payload,payload,allow_pickle=False)
            embed_wall = run([BASE/'wire.py',reserved_file,input_payload,
                              capability['directory'].hex(),capability['payload'].hex(),
                              capability['auth'].hex(),cipher_file,embed_audit],D/(stem+'_embed.log'))
            final = np.array(Image.open(cipher_file))
            fq = wire.inspect(final,capability)
            # Embedder may change only U plus header and tag, never backup or context.
            allow = np.zeros_like(final)
            u = tuple(v[q['backup']:] for v in q['positions'])
            wire.writebits(allow,u,np.ones(q['net'],np.uint8))
            allow[y[:20],x[:20]]=255
            allow[y[20+len(q['meta']):q['h']],x[20+len(q['meta']):q['h']]]=255
            assert not np.any((final ^ reserved) & (255 ^ allow))
            assert np.array_equal(wire.readbits(final,tuple(v[:q['backup']] for v in q['positions'])),
                                  wire.readbits(reserved,tuple(v[:q['backup']] for v in q['positions'])))
            receive_wall = run([BASE/'protocol.py','receive',cipher_file,master.hex(),nonce,
                                recovered_file,extracted_file,receive_audit],D/(stem+'_receive.log'))
            image_ok = bool(np.array_equal(np.load(recovered_file,allow_pickle=False),original))
            payload_ok = bool(np.array_equal(np.load(extracted_file,allow_pickle=False),payload))
            assert image_ok and payload_ok
            rx = json.loads(receive_audit.read_text())
            emb = json.loads(embed_audit.read_text())
            assert not emb['model_imported'] and not emb['image_key_received']
            # No sender arrays, payload inputs, or any other evidence file may be read.
            evidence_reads = [p for p in rx['read_paths'] if str(D)+os.sep in p]
            assert evidence_reads == [str(cipher_file)], evidence_reads
            result = dict(image=name,case=case,payload_bits=plen,nonce=nonce,
                          image_exact=image_ok,payload_exact=payload_ok,
                          reserve_encrypt_seconds=reserve_seconds,embed_seconds=emb['seconds'],
                          embed_process_seconds=embed_wall,receiver_seconds=rx['receiver_seconds'],
                          receiver_process_seconds=receive_wall,receiver_evidence_reads=evidence_reads,
                          net_bits=q['net'],within_pixel_backup_boundary=bool(q['backup'] and
                          q['positions'][0][q['backup']-1]==q['positions'][0][q['backup']]),
                          encrypted_payload_changed_bits=int(wire.readbits(final ^ reserved,u).sum()))
            results.append(result)
            print('PASS',result,flush=True)
            # Persist after each check so failures cannot erase prior observations.
            save(stem+'_result.json',result)
            if case == 'short':
                corrupt = final.copy(); corrupt[0,0] ^= 1
                badcap = {**capability,'auth':bytes(32)}
                negative.append(dict(image=name,
                    oversized=rejection(lambda: wire.embed(reserved,np.zeros(q['net']+1,np.uint8),capability)),
                    nonbinary=rejection(lambda: wire.embed(reserved,np.array([2]),capability)),
                    corrupted_ciphertext=rejection(lambda: pr.receive(corrupt,master,nonce)),
                    wrong_nonce=rejection(lambda: pr.receive(final,master,nonce+10**9)),
                    wrong_key=rejection(lambda: pr.receive(final,bytes(32),nonce)),
                    wrong_embed_key=rejection(lambda: wire.inspect(final,badcap))))
    save('capacities.json',capacities)
    save('roundtrips.json',results)
    save('negative_checks.json',negative)
    state_ok=all(torch.equal(initial_state[k],v) for k,v in model.state_dict().items())
    assert state_ok
    save('integrity.json',dict(state_unchanged=state_ok,training=False,
                               checkpoint_sha256=sha(old.CHECKPOINT)))
    assert sum(r.get('accepted',False) for r in capacities if r['image'].endswith('.png')) >= 3
    print('ALL CHECKS PASSED',flush=True)


if __name__ == '__main__':
    main()
