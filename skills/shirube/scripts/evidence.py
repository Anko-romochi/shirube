"""SHIRUBE: offline, deterministic evidence-map checks (Python 3.10+ stdlib).
Formal consistency is not semantic entailment, independence, or historical truth.
"""
import argparse
import datetime
import hashlib
import html
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
from urllib.parse import urlsplit

MAX_LEDGER = 5_000_000
MAX_SOURCE = 10_000_000
STATUSES = ('unverified', 'partial', 'supported', 'contested')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


def safe_file(root, name):
    """Saved-copy paths are relative POSIX paths, including on Windows."""
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or '\x00' in name or Path(name).is_absolute() or PureWindowsPath(name).drive
            or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('unsafe_path')
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('missing_or_outside_source')
    return target


class Shape:
    """Validate structure before any graph, sets, URL parsing or file reads."""
    def __init__(self):
        self.errors = []

    def error(self, path, code):
        self.errors.append({'path': path, 'code': code})

    def obj(self, value, path):
        if not isinstance(value, dict):
            self.error(path, 'expected_object'); return False
        return True

    def text(self, value, path):
        if not isinstance(value, str) or not value.strip() or len(value) > 100_000:
            self.error(path, 'expected_nonempty_bounded_string'); return
        try: value.encode('utf-8')
        except UnicodeError: self.error(path, 'invalid_unicode')

    def choice(self, value, path, choices):
        if not isinstance(value, str) or value not in choices:
            self.error(path, 'invalid_choice')

    def strings(self, value, path, nonempty=False):
        if not isinstance(value, list) or len(value) > 10_000:
            self.error(path, 'expected_bounded_array'); return
        if nonempty and not value:
            self.error(path, 'empty_array')
        for i, v in enumerate(value): self.text(v, f'{path}/{i}')

    def array(self, value, path, nonempty=False):
        if not isinstance(value, list) or len(value) > 10_000:
            self.error(path, 'expected_bounded_array'); return []
        if nonempty and not value: self.error(path, 'empty_array')
        return value

    def review(self, value, path):
        if not self.obj(value, path): return
        self.choice(value.get('state'), path+'/state', ('unreviewed', 'accepted', 'rejected'))
        if value.get('state') in ('accepted', 'rejected'):
            for k in ('reviewer', 'note'): self.text(value.get(k), path+'/'+k)

    def validate(self, d):
        pending=[d]; count=0
        while pending:
            value=pending.pop();count+=1
            if count>200_000: self.error('','too_many_values');return self.errors
            if isinstance(value,str):
                try: value.encode('utf-8')
                except UnicodeError: self.error('','invalid_unicode');return self.errors
            elif isinstance(value,float) and not math.isfinite(value): self.error('','nonfinite_number');return self.errors
            elif isinstance(value,dict): pending.extend(value.keys());pending.extend(value.values())
            elif isinstance(value,list): pending.extend(value)
        if not self.obj(d, ''): return self.errors
        if type(d.get('schema')) is not int or d.get('schema') != 2: self.error('/schema', 'expected_schema_2')
        for k in ('title', 'question', 'stopped'): self.text(d.get(k), '/'+k)
        self.strings(d.get('log'), '/log', True)
        b = d.get('baseline')
        if self.obj(b, '/baseline'):
            self.choice(b.get('status'), '/baseline/status', ('unread', 'partial', 'read'))
            for k in ('sources', 'claims'): self.strings(b.get(k), '/baseline/'+k)
            for i, c in enumerate(self.array(b.get('claim_states', []), '/baseline/claim_states')):
                p=f'/baseline/claim_states/{i}'
                if self.obj(c,p):
                    for k in ('id','conclusion'): self.text(c.get(k),p+'/'+k)
                    self.choice(c.get('status'),p+'/status',STATUSES)
                    self.strings(c.get('source_keys'),p+'/source_keys')
                    if 'review_states' in c: self.strings(c['review_states'],p+'/review_states')
        for i, s in enumerate(self.array(d.get('sources'),'/sources',True)):
            p=f'/sources/{i}'
            if not self.obj(s,p): continue
            for k in ('id','key','title','url','accessed','edition','period','limitation'): self.text(s.get(k),p+'/'+k)
            self.choice(s.get('kind'),p+'/kind',('catalog','index','body'))
            self.choice(s.get('scope'),p+'/scope',('metadata','partial','full'))
            self.choice(s.get('access'),p+'/access',('ok','blocked','unavailable'))
            self.strings(s.get('lineage'),p+'/lineage')
            self.strings(s.get('derived_from',[]),p+'/derived_from')
            self.strings(s.get('read_ranges'),p+'/read_ranges',True)
            if ('file' in s) != ('sha256' in s): self.error(p,'file_hash_pair_required')
            if 'file' in s:
                self.text(s['file'],p+'/file')
                if not isinstance(s.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',s['sha256']): self.error(p+'/sha256','expected_sha256')
        for i,c in enumerate(self.array(d.get('claims'),'/claims',True)):
            p=f'/claims/{i}'
            if not self.obj(c,p): continue
            for k in ('id','text'): self.text(c.get(k),p+'/'+k)
            for k in ('conclusion','change_reason'):
                if k in c: self.text(c[k],p+'/'+k)
            self.choice(c.get('status'),p+'/status',STATUSES)
            self.choice(c.get('novelty'),p+'/novelty',('none','candidate','added-to-reviewed-baseline'))
            self.choice(c.get('counterevidence_search','not_recorded'),p+'/counterevidence_search',('not_recorded','incomplete','completed'))
            self.strings(c.get('conflicts'),p+'/conflicts')
            for j,check in enumerate(self.array(c.get('next_checks',[]),p+'/next_checks')):
                cp=p+f'/next_checks/{j}'
                if self.obj(check,cp):
                    for k in ('target','question','reason'): self.text(check.get(k),cp+'/'+k)
            for j,q in enumerate(self.array(c.get('evidence'),p+'/evidence')):
                qp=p+f'/evidence/{j}'
                if not self.obj(q,qp): continue
                for k in ('source','quote'): self.text(q.get(k),qp+'/'+k)
                for k in ('start','end'):
                    if type(q.get(k)) is not int or q[k]<1: self.error(qp+'/'+k,'expected_positive_integer')
                self.choice(q.get('role'),qp+'/role',('support','refute','context'))
                self.choice(q.get('use'),qp+'/use',('metadata','body'))
                if 'review' in q: self.review(q['review'],qp+'/review')
        return self.errors


def failure(errors):
    return {'valid':False,'formal_valid':False,'meaning':'Formal checks only; no semantic guarantee.', 'errors':sorted(errors,key=lambda x:(x['path'],x['code'])),'claims':[],'delta':None}


def inspect(d, root):
    shape=Shape(); errors=shape.validate(d)
    if errors: return failure(errors)
    def err(path,code): errors.append({'path':path,'code':code})
    sources={}; lines={}; claim_ids=set(); prior_ids=set(); keys=set()
    for i,s in enumerate(d['sources']):
        p=f'/sources/{i}'; sid=s['id']
        if sid in sources: err(p+'/id','duplicate_id')
        if s['key'] in keys: err(p+'/key','duplicate_source_key')
        keys.add(s['key']); sources[sid]=s
        try:
            u=urlsplit(s['url'])
            remote=u.scheme in ('http','https') and bool(u.hostname) and not u.username and not u.password
            local=u.scheme=='file' and u.netloc in ('','localhost') and u.path.startswith('/') and not u.query and not u.fragment and 'file' in s
            portable=u.scheme=='local' and not u.netloc and s.get('file')==u.path
            if portable: safe_file(root,u.path)
            if not (remote or local or portable): err(p+'/url','invalid_origin')
        except (ValueError,OSError): err(p+'/url','invalid_origin')
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s['accessed']): raise ValueError('date_format')
            datetime.date.fromisoformat(s['accessed'])
        except ValueError: err(p+'/accessed','invalid_date')
        if s['kind']!='body' and s['scope']!='metadata': err(p+'/scope','metadata_is_not_body_read')
        if 'file' in s:
            try:
                f=safe_file(root,s['file'])
                if f.stat().st_size>MAX_SOURCE: raise ValueError('source_too_large')
                raw=f.read_bytes()
                if digest(raw)!=s['sha256']: err(p+'/sha256','hash_mismatch')
                lines[sid]=raw.decode('utf-8').replace('\r\n','\n').split('\n')
            except ValueError as ex: err(p+'/file',str(ex) if str(ex) in ('unsafe_path','missing_or_outside_source','source_too_large') else 'invalid_source')
            except (OSError,UnicodeError): err(p+'/file','unreadable_utf8_source')
    # Iterative dependency graph walk: never recurse on untrusted graph depth.
    parents={sid:set(s.get('derived_from',[])) for sid,s in sources.items()}
    for sid,ps in parents.items():
        if any(x not in sources for x in ps): err('/sources/'+sid+'/derived_from','unknown_source')
        if ps and sources[sid]['lineage']: err('/sources/'+sid+'/lineage','derived_source_must_inherit_roots')
    origins={}; pending=set(sources)
    while pending:
        ready=sorted(x for x in pending if parents[x].issubset(origins))
        if not ready: err('/sources/derived_from','cycle_or_unknown_dependency'); break
        for sid in ready:
            roots=set(sources[sid]['lineage']) if not parents[sid] else set().union(*(origins[x] for x in parents[sid]))
            origins[sid]=roots; pending.remove(sid)
    for i,c in enumerate(d['claims']):
        if c['id'] in claim_ids: err(f'/claims/{i}/id','duplicate_id')
        claim_ids.add(c['id'])
    for i,c in enumerate(d['baseline'].get('claim_states',[])):
        if c['id'] in prior_ids: err(f'/baseline/claim_states/{i}/id','duplicate_id')
        prior_ids.add(c['id'])
    if errors: return failure(errors)
    results=[]
    for i,c in enumerate(d['claims']):
        p=f'/claims/{i}'; roots=set(); uncertain=set(); support=0; reviewed=0; refutes=0; reviews=[]
        for j,q in enumerate(c['evidence']):
            qp=p+f'/evidence/{j}'; sid=q['source']; s=sources.get(sid)
            if s is None: err(qp+'/source','unknown_source'); continue
            if s['access']!='ok': err(qp,'unavailable_evidence')
            if q['use']=='body' and not(s['kind']=='body' and s['scope'] in ('partial','full')): err(qp+'/use','metadata_is_not_body_evidence')
            a,b=q['start'],q['end']; ls=lines.get(sid,[])
            match=1<=a<=b<=len(ls) and q['quote']=='\n'.join(ls[a-1:b])
            if not match: err(qp,'quote_range_or_text_mismatch')
            state=q.get('review',{}).get('state','unreviewed'); reviews.append(state)
            if q['role']=='support':
                support+=1
                if state=='accepted':
                    reviewed+=1
                    if len(origins[sid])==1: roots.update(origins[sid])
                    else: uncertain.add(sid)
            if q['role']=='refute': refutes+=1
        if c['status']=='supported' and not support: err(p+'/status','supported_without_support_link')
        if (refutes or c['conflicts']) and c['status']!='contested': err(p+'/status','unresolved_conflict_must_be_contested')
        incoming=any(c['id'] in other['conflicts'] for other in d['claims'])
        if any(x not in claim_ids or x==c['id'] for x in c['conflicts']): err(p+'/conflicts','unknown_or_self_conflict')
        if (incoming or c['status']=='contested') and (c['status']!='contested' or not c.get('next_checks')): err(p,'contested_requires_next_check')
        if c['novelty']=='added-to-reviewed-baseline' and (d['baseline']['status']!='read' or not reviewed or c['text'] in d['baseline']['claims']): err(p+'/novelty','invalid_reviewed_baseline_addition')
        pending_review=any(x=='unreviewed' for x in reviews)
        label='not_reviewed' if pending_review or not reviews else 'review_recorded'
        if 'rejected' in reviews: label='contains_rejected_links'
        if c['status']=='supported' and not reviewed: label='no_reviewed_support'
        results.append({'id':c['id'],'declared_status':c['status'],'link_review_state':label,'formal_support_links':support,'recorded_accepted_support_links':reviewed,'recorded_origin_groups':sorted(roots),'recorded_origin_group_count':len(roots),'uncertain_origin_sources':sorted(uncertain),'counterevidence_search':c.get('counterevidence_search','not_recorded'),'semantic_guarantee':False})
    if errors: return failure(errors)
    baseline=d['baseline']; current_keys=set(s['key'] for s in sources.values()); old_keys=set(baseline['sources'])
    texts=set(c['text'] for c in d['claims']); old_texts=set(baseline['claims']); prior={c['id']:c for c in baseline.get('claim_states',[])}; changes=[]
    for c in sorted(d['claims'],key=lambda c:c['id']):
        if c['id'] not in prior: continue
        prev=prior[c['id']]
        before={'id':prev['id'],'status':prev['status'],'conclusion':prev['conclusion'],'source_keys':sorted(set(prev['source_keys']))}
        after={'id':c['id'],'status':c['status'],'conclusion':c.get('conclusion',c['text']),'source_keys':sorted({sources[q['source']]['key'] for q in c['evidence']})}
        fields=[k for k in ('status','conclusion','source_keys') if before[k]!=after[k]]
        current_reviews=sorted({q.get('review',{}).get('state','unreviewed') for q in c['evidence']})
        if 'review_states' in prev and sorted(set(prev['review_states']))!=current_reviews:
            fields.append('review_states');before['review_states']=sorted(set(prev['review_states']));after['review_states']=current_reviews
        if fields: changes.append({'id':c['id'],'changed_fields':fields,'before':before,'after':after,'new_source_keys':sorted(set(after['source_keys'])-set(before['source_keys'])),'reason':c.get('change_reason','not_recorded')})
    delta={'comparison_status':baseline['status'],'source_candidates_not_in_baseline':sorted(current_keys-old_keys),'baseline_sources_not_in_current':sorted(old_keys-current_keys),'claim_text_candidates_not_in_baseline':sorted(texts-old_texts),'baseline_claim_texts_not_in_current':sorted(old_texts-texts),'conclusion_changes':changes,'meaning':'Recorded string/set changes only; not discovery, retraction, semantic or causal inference.'}
    return {'valid':True,'formal_valid':True,'meaning':'Formal consistency only. Review states are human/agent declarations, not machine semantic guarantees.','errors':[],'claims':results,'delta':delta}


def load_ledger(path):
    if path.stat().st_size>MAX_LEDGER: raise ValueError('ledger_too_large')
    # Duplicate JSON keys could silently replace evidence or status; reject them.
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('duplicate_json_key')
            result[key]=value
        return result
    def nonfinite(_): raise ValueError('nonfinite_json_number')
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=nonfinite)


def run(ledger,output):
    if output.exists(): raise ValueError('output_must_be_new')
    try: d=load_ledger(ledger); result=inspect(d,ledger.parent)
    except (ValueError,OSError,UnicodeError,RecursionError):
        d=None;result=failure([{'path':'','code':'invalid_or_unreadable_ledger_json'}])
    output.mkdir(parents=True,exist_ok=False)
    (output/'verification.json').write_text(canonical(result),encoding='utf-8',newline='\n')
    if not result['formal_valid']: return 1
    byid={r['id']:r for r in result['claims']}; rows=[]
    for c in d['claims']:
        r=byid[c['id']]
        refs='; '.join(q['source']+':'+str(q['start'])+'-'+str(q['end'])+' '+q['role']+' / '+q.get('review',{}).get('state','unreviewed') for q in c['evidence'])
        todo='; '.join(x['target']+' / '+x['question']+' / '+x['reason'] for x in c.get('next_checks',[]))
        cells=(c['id'],c['text'],'申告: '+c['status'],r['link_review_state'],refs,todo)
        rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in cells)+'</tr>')
    page='<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SHIRUBE evidence map</title><style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:.5rem;vertical-align:top;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>SHIRUBE — 主張と根拠の地図</h1><p>原文・形式の照合済み。意味的な支持・真偽・原典の独立性は自動保証しません。申告状態と引用リンクのレビュー記録を分けて表示します。反証の未登録・系列の誤分類は自動発見できません。</p><table><tr><th>ID</th><th>主張</th><th>申告状態</th><th>リンクのレビュー記録</th><th>引用</th><th>次の確認</th></tr>'+''.join(rows)+'</table><h2>結論差分（文字列・集合）</h2><pre>'+html.escape(canonical(result['delta']))+'</pre><h2>全記録（非公開の絶対パス等を含みうるため、共有前に確認）</h2><pre>'+html.escape(canonical({'ledger':d,'verification':result}))+'</pre></html>\n'
    (output/'report.html').write_text(page,encoding='utf-8',newline='\n')
    (output/'delta.json').write_text(canonical(result['delta']),encoding='utf-8',newline='\n')
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    try: return run(args.ledger,args.output)
    except (ValueError,OSError):
        print('Output unavailable or already exists; choose a new writable directory.',file=sys.stderr);return 2


if __name__=='__main__': sys.exit(main())
