#!/usr/bin/env python3
"""Fetch profile stats via GitHub GraphQL and write stats.json.
Env: ACCESS_TOKEN (PAT with read:user; add `repo` to count private contributions), USER_NAME."""
import json, os, sys, urllib.request

QUERY = """query($login:String!){user(login:$login){
  followers{totalCount}
  repositories(ownerAffiliations:OWNER,isFork:false,first:100){totalCount nodes{stargazerCount}}
  contributionsCollection{totalCommitContributions restrictedContributionsCount}
  pullRequests{totalCount} issues{totalCount}}}"""

def main():
    token, login = os.environ["ACCESS_TOKEN"], os.environ["USER_NAME"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        sys.exit(f"GraphQL error: {payload.get('errors')}")  # keep previous stats.json
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]
    stats = {
        "repos": u["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "followers": u["followers"]["totalCount"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
    }
    json.dump(stats, open("stats.json", "w"), indent=2)
    print(stats)

main()
