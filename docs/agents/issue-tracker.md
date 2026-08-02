# Issue tracker: GitHub

Issues, specifications, and implementation tickets live in GitHub Issues.
GitHub Projects provides roadmap, priority, milestone, dependency, and status
views; it does not replace the issue body.

Use the `gh` CLI from this repository:

- Create: `gh issue create`
- Read: `gh issue view <number> --comments`
- List: `gh issue list --state open`
- Comment: `gh issue comment <number> --body "..."`
- Label: `gh issue edit <number> --add-label "..."`
- Close: `gh issue close <number> --comment "..."`

Each issue should contain the problem, scope and non-goals, acceptance criteria,
dependencies, and verification requirements. Separate host-test acceptance from
physical hardware verification.

Pull requests are not a triage/request surface. Reference the originating issue
from branches and pull requests.

When a skill says “publish to the issue tracker,” create a GitHub issue. When it
says “fetch the relevant ticket,” use `gh issue view <number> --comments`.
