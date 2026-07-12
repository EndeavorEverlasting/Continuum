"""Read-only GitHub Actions completion-proof verification."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, os, re
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_RELATIVE_PATH = Path('.continuum/repository.json')
DEFAULT_GITHUB_API_URL = 'https://api.github.com'
PROOF_SCHEMA_PATH = 'schemas/github-actions-proof.schema.json'
_SHA = re.compile(r'^[0-9a-f]{40,64}$')
_SLUG = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
RETRYABLE_BLOCKERS = frozenset({'github_actions.run_missing','github_actions.run_pending'})

class GitHubActionsError(RuntimeError):
    def __init__(self, code: str, message: str): self.code=code; super().__init__(message)
    def to_dict(self): return {'schema_version':1,'command':'ci-proof','status':'blocked','blocker':{'code':self.code,'message':str(self)}}

@dataclass(frozen=True)
class GitHubActionsPolicy:
    repository: str; workflow: str; event: str; required_conclusion: str; branch: str
    def to_dict(self): return {'provider':'github_actions','repository':self.repository,'workflow':self.workflow,'event':self.event,'required_conclusion':self.required_conclusion,'branch':self.branch}

@dataclass(frozen=True)
class WorkflowRun:
    run_id:int; repository:str; name:str; path:str; event:str; status:str; conclusion:str|None; head_branch:str; head_sha:str; html_url:str; run_attempt:int
    def to_dict(self): return {'id':self.run_id,'repository':self.repository,'name':self.name,'path':self.path,'event':self.event,'status':self.status,'conclusion':self.conclusion,'head_branch':self.head_branch,'head_sha':self.head_sha,'html_url':self.html_url,'run_attempt':self.run_attempt}

@dataclass(frozen=True)
class GitHubActionsProof:
    proof_id:str; status:str; policy:GitHubActionsPolicy; commit_sha:str; source:str; run:WorkflowRun|None; evidence:dict[str,str]|None; blocker:dict[str,str]|None
    @property
    def passed(self): return self.status=='passed'
    def to_dict(self):
        return {'$schema':PROOF_SCHEMA_PATH,'schema_version':1,'kind':'continuum.github-actions-proof','proof_id':self.proof_id,'status':self.status,'repository':{'slug':self.policy.repository,'branch':self.policy.branch,'commit_sha':self.commit_sha},'policy':{'workflow':self.policy.workflow,'event':self.policy.event,'required_conclusion':self.policy.required_conclusion},'source':self.source,'run':self.run.to_dict() if self.run else None,'evidence':self.evidence,'blocker':self.blocker}
    def render_english(self):
        if self.passed and self.run: return f"Continuum independently verified GitHub Actions run {self.run.run_id} for {self.policy.repository}@{self.commit_sha}. The workflow {self.run.name!r} completed with conclusion {self.run.conclusion!r}."
        b=self.blocker or {'code':'github_actions.proof_blocked','message':'GitHub Actions completion proof is blocked.'}
        return f"Continuum could not verify GitHub Actions completion for {self.policy.repository}@{self.commit_sha}.\nBLOCKER [{b['code']}]: {b['message']}"

def _text(value:Any, code:str, label:str)->str:
    if not isinstance(value,str) or not value.strip(): raise GitHubActionsError(code,f'{label} must be a non-empty string.')
    return value.strip()

def _sha(value:Any)->str:
    value=_text(value,'github_actions.commit_invalid','Commit SHA').lower()
    if not _SHA.fullmatch(value): raise GitHubActionsError('github_actions.commit_invalid','Commit SHA must contain 40 to 64 lowercase hexadecimal characters.')
    return value

def load_github_actions_policy(root:Path)->GitHubActionsPolicy:
    path=root.expanduser().resolve()/CONTRACT_RELATIVE_PATH
    try: doc=json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc: raise GitHubActionsError('github_actions.contract_missing',f'The repository contract does not exist at {path}.') from exc
    except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise GitHubActionsError('github_actions.contract_parse',f'The repository contract could not be parsed: {exc}.') from exc
    repo=doc.get('repository') if isinstance(doc,dict) else None; proof=doc.get('completion_proof') if isinstance(doc,dict) else None
    if not isinstance(repo,dict) or not isinstance(proof,dict): raise GitHubActionsError('github_actions.policy_missing','The repository and completion_proof sections must be JSON objects.')
    provider=_text(proof.get('provider'),'github_actions.provider_invalid','Completion-proof provider')
    if provider!='github_actions': raise GitHubActionsError('github_actions.provider_invalid',"The completion-proof provider must be 'github_actions'.")
    slug=_text(proof.get('repository'),'github_actions.repository_invalid','GitHub repository slug')
    if not _SLUG.fullmatch(slug): raise GitHubActionsError('github_actions.repository_invalid','GitHub repository must use owner/name form.')
    workflow=_text(proof.get('workflow'),'github_actions.workflow_invalid','Workflow')
    event=_text(proof.get('event'),'github_actions.event_invalid','Workflow event')
    conclusion=_text(proof.get('required_conclusion'),'github_actions.conclusion_invalid','Required conclusion')
    branch=_text(repo.get('default_branch'),'github_actions.branch_invalid','Repository default branch')
    if event!='push': raise GitHubActionsError('github_actions.event_invalid',"Canonical completion proof requires the 'push' event.")
    if conclusion!='success': raise GitHubActionsError('github_actions.conclusion_invalid',"Canonical completion proof requires the 'success' conclusion.")
    return GitHubActionsPolicy(slug,workflow,event,conclusion,branch)

def _positive_integer(value:Any, label:str)->int:
    if isinstance(value,bool):
        raise GitHubActionsError('github_actions.run_invalid',f'{label} must be a positive integer.')
    try:
        parsed=int(value)
    except (TypeError,ValueError) as exc:
        raise GitHubActionsError('github_actions.run_invalid',f'{label} must be a positive integer.') from exc
    if parsed<=0:
        raise GitHubActionsError('github_actions.run_invalid',f'{label} must be a positive integer.')
    return parsed

def _run(raw:Mapping[str,Any])->WorkflowRun:
    repo=raw.get('repository'); repo=repo.get('full_name') if isinstance(repo,Mapping) else repo
    run_id=_positive_integer(raw.get('id'),'Workflow run id')
    attempt=_positive_integer(raw.get('run_attempt'),'Workflow run attempt')
    return WorkflowRun(run_id,_text(repo,'github_actions.run_invalid','Run repository'),_text(raw.get('name'),'github_actions.run_invalid','Run name'),_text(raw.get('path'),'github_actions.run_invalid','Run path'),_text(raw.get('event'),'github_actions.run_invalid','Run event'),_text(raw.get('status'),'github_actions.run_invalid','Run status'),raw.get('conclusion') if isinstance(raw.get('conclusion'),str) else None,_text(raw.get('head_branch'),'github_actions.run_invalid','Run head branch'),_sha(raw.get('head_sha')),_text(raw.get('html_url'),'github_actions.run_invalid','Run URL'),attempt)

def _proof(policy,sha,source,run=None,code=None,message=None):
    identity=json.dumps({'repository':policy.repository,'branch':policy.branch,'commit':sha,'workflow':policy.workflow,'event':policy.event,'run':run.run_id if run else None,'attempt':run.run_attempt if run else None,'status':run.status if run else None,'conclusion':run.conclusion if run else None,'source':source},sort_keys=True,separators=(',',':'))
    pid='proof-'+hashlib.sha256(identity.encode()).hexdigest()[:16]
    passed=run is not None and code is None
    evidence={'name':'github_actions','status':'passed' if passed else 'failed','reference':run.html_url if run else f'github-actions:{policy.repository}@{sha}','source':source} if run or code else None
    return GitHubActionsProof(pid,'passed' if passed else 'blocked',policy,sha,source,run,evidence,None if passed else {'code':code or 'github_actions.proof_blocked','message':message or 'GitHub Actions completion proof is blocked.'})

def evaluate_github_actions_runs(policy:GitHubActionsPolicy,commit_sha:str,runs:Iterable[Mapping[str,Any]],*,source:str)->GitHubActionsProof:
    sha=_sha(commit_sha); matches=[]
    for raw in runs:
        try: run=_run(raw)
        except GitHubActionsError: continue
        workflow_match=run.name==policy.workflow or run.path==policy.workflow or run.path.endswith('/'+policy.workflow)
        if run.repository==policy.repository and run.head_branch==policy.branch and run.head_sha==sha and run.event==policy.event and workflow_match: matches.append(run)
    if not matches: return _proof(policy,sha,source,code='github_actions.run_missing',message='No workflow run matched the exact repository, branch, commit, workflow, and event policy.')
    run=max(matches,key=lambda item:(item.run_attempt,item.run_id))
    if run.status!='completed': return _proof(policy,sha,source,run=run,code='github_actions.run_pending',message=f'Workflow run {run.run_id} is {run.status!r}, not completed.')
    if run.conclusion!=policy.required_conclusion: return _proof(policy,sha,source,run=run,code='github_actions.run_failed',message=f'Workflow run {run.run_id} concluded {run.conclusion!r}; required {policy.required_conclusion!r}.')
    return _proof(policy,sha,source,run=run)

def proof_from_workflow_run_event(policy,event_document):
    if not isinstance(event_document,Mapping) or not isinstance(event_document.get('workflow_run'),Mapping): raise GitHubActionsError('github_actions.event_document_invalid','The GitHub event document must contain a workflow_run object.')
    raw=event_document['workflow_run']
    _run(raw)
    return evaluate_github_actions_runs(policy,_sha(raw.get('head_sha')),[raw],source='github-workflow-run-event')

def load_workflow_run_event(path:Path):
    try: doc=json.loads(path.expanduser().resolve().read_text(encoding='utf-8'))
    except FileNotFoundError as exc: raise GitHubActionsError('github_actions.event_file_missing',f'The GitHub event file does not exist at {path.expanduser().resolve()}.') from exc
    except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise GitHubActionsError('github_actions.event_file_parse',f'The GitHub event file could not be parsed: {exc}.') from exc
    if not isinstance(doc,dict): raise GitHubActionsError('github_actions.event_document_invalid','The GitHub event document must be a JSON object.')
    return doc

def resolve_github_token(environment:Mapping[str,str]|None=None):
    env=os.environ if environment is None else environment
    for name in ('GH_TOKEN','GITHUB_TOKEN'):
        value=env.get(name)
        if isinstance(value,str) and value.strip(): return value.strip()
    return None

def fetch_github_actions_proof(*args,**kwargs):
    from .github_actions_api import fetch_github_actions_proof as impl
    return impl(*args,**kwargs)

def wait_for_github_actions_proof(*args,**kwargs):
    from .github_actions_api import wait_for_github_actions_proof as impl
    return impl(*args,**kwargs)
