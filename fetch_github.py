import urllib.request, json

req = urllib.request.Request('https://api.github.com/users/DEBANJAN-KAKATI/repos?per_page=100', headers={'User-Agent': 'ResumeBuilderApp'})
with urllib.request.urlopen(req) as resp:
    repos = json.loads(resp.read().decode('utf-8'))

print(f"Total GitHub repos: {len(repos)}")
repo_data = []
for r in repos:
    item = {
        "name": r["name"],
        "url": r["html_url"],
        "description": r.get("description"),
        "language": r.get("language"),
        "stars": r.get("stargazers_count"),
        "forks": r.get("forks_count"),
        "topics": r.get("topics", []),
        "updated_at": r.get("updated_at")
    }
    repo_data.append(item)
    print(f"Repo: {item['name']} | Lang: {item['language']} | Desc: {item['description']}")

with open("github_repos.json", "w", encoding="utf-8") as f:
    json.dump(repo_data, f, indent=2)
print("Saved github_repos.json successfully")
