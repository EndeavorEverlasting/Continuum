"""Read-only GitHub Actions API transport."""
from __future__ import annotations
import json,time
from typing import Any,Callable,Mapping
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from .github_actions import GitHubActionsError,GitHubActionsPolicy,GitHubActionsProof,RETRYABLE_BLOCKERS,evaluate_github_actions_runs,_proof,_sha

DEFAULT_GITHUB_API_URL='https://api.github.com'
JsonFetcher=Callable[[str,Mapping[str,str],float],Mapping[str,Any]]

def _fetch(url,headers,timeout):
    try:
        with urlopen(Request(url,headers=dict(headers),method='GET'),timeout=timeout) as response: raw=response.read()
    except HTTPError as exc: raise GitHubActionsError('github_actions.http_error',f'GitHub Actions API returned HTTP {exc.code}.') from exc
    except (URLError,OSError) as exc: raise GitHubActionsError('github_actions.network_error',f'GitHub Actions API could not be reached: {getattr(exc,"reason",exc)}.') from exc
    try: doc=json.loads(raw.decode('utf-8'))
    except (UnicodeError,json.JSONDecodeError) as exc: raise GitHubActionsError('github_actions.response_invalid',f'GitHub Actions API returned invalid JSON: {exc}.') from exc
    if not isinstance(doc,dict): raise GitHubActionsError('github_actions.response_invalid','GitHub Actions API response must be a JSON object.')
    return doc

def _api_base(api_url:str,token:str|None)->str:
    if not isinstance(api_url,str) or not api_url.strip():
        raise GitHubActionsError('github_actions.api_url_invalid','GitHub API URL must be a non-empty HTTPS URL.')
    candidate=api_url.strip().rstrip('/')
    parsed=urlsplit(candidate)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GitHubActionsError('github_actions.api_url_invalid','GitHub API URL must be a credential-free HTTPS URL without query or fragment data.')
    if token and candidate!=DEFAULT_GITHUB_API_URL:
        raise GitHubActionsError('github_actions.api_url_untrusted','Authenticated GitHub API requests must use https://api.github.com.')
    return candidate

def fetch_github_actions_proof(policy:GitHubActionsPolicy,commit_sha:str,*,token:str|None=None,api_url:str=DEFAULT_GITHUB_API_URL,timeout_seconds:float=15.0,fetch_json:JsonFetcher=_fetch)->GitHubActionsProof:
    sha=_sha(commit_sha)
    if timeout_seconds<=0: raise GitHubActionsError('github_actions.timeout_invalid','HTTP timeout must be greater than zero seconds.')
    base=_api_base(api_url,token)
    query=urlencode({'head_sha':sha,'branch':policy.branch,'event':policy.event,'per_page':100})
    url=f'{base}/repos/{policy.repository}/actions/runs?{query}'
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'continuum-orchestrator'}
    if token: headers['Authorization']=f'Bearer {token}'
    doc=fetch_json(url,headers,timeout_seconds); runs=doc.get('workflow_runs')
    if not isinstance(runs,list): raise GitHubActionsError('github_actions.response_invalid','GitHub Actions API response must contain a workflow_runs array.')
    return evaluate_github_actions_runs(policy,sha,runs,source='github-api')

def wait_for_github_actions_proof(policy,commit_sha,*,wait_seconds=0.0,poll_seconds=5.0,token=None,api_url=DEFAULT_GITHUB_API_URL,http_timeout_seconds=15.0,fetch_json=_fetch,monotonic=time.monotonic,sleeper=time.sleep):
    if wait_seconds<0: raise GitHubActionsError('github_actions.wait_invalid','Wait duration must be zero or greater.')
    if poll_seconds<=0: raise GitHubActionsError('github_actions.poll_invalid','Poll interval must be greater than zero seconds.')
    deadline=monotonic()+wait_seconds
    latest=fetch_github_actions_proof(policy,commit_sha,token=token,api_url=api_url,timeout_seconds=http_timeout_seconds,fetch_json=fetch_json)
    while not latest.passed and latest.blocker and latest.blocker.get('code') in RETRYABLE_BLOCKERS and monotonic()<deadline:
        sleeper(min(poll_seconds,max(0.0,deadline-monotonic())))
        latest=fetch_github_actions_proof(policy,commit_sha,token=token,api_url=api_url,timeout_seconds=http_timeout_seconds,fetch_json=fetch_json)
    if not latest.passed and wait_seconds>0 and latest.blocker and latest.blocker.get('code') in RETRYABLE_BLOCKERS and monotonic()>=deadline:
        return _proof(policy,_sha(commit_sha),'github-api',run=latest.run,code='github_actions.wait_timeout',message=f'GitHub Actions completion proof did not become final within {wait_seconds:g} seconds; last state was {latest.blocker["code"]}.')
    return latest
