# Contributing

> **Rule 0:** Be polite, respectful and supportive.

At present, contributions are limited to members of Scottish COVID-19 Response Consortium (SCRC).

## Working with git and GitHub

The process for implementing changes is:
- An **issue** is raised in the [SCRC issue tracking repository](https://github.com/ScottishCovidResponse/SCRCIssueTracking), tagged "Simple Network Sim"
> *How to write a good issue:* Check for duplicate issues - don't raise the same issue twice! Be specific - whoever works on this needs to know where it ends. Not too big - if the issue could be multiple issues, it probably should be.
- The **issue** is assigned (ideally self assigned with the agreement of the team) to a team member (assignee)
- The assignee creates a **branch** to work on the issue
- The assignee makes a series of **commits** to the branch, implementing changes that address the issue
- The assignee makes a **pull request**, requesting a **review** (a review is required to merge, and a request lets the team member know to do a review)
> *How to do a good pull request:* Tie it to usually one or sometimes more issues - e.g. write 'resolves ScottishCovidResponse/SCRCIssueTracking#1'. This will automatically mark the issue as closed when the pull request is merged. Summarise what you've done to resolve the issue(s).
**For the time being, all pull requests should be reviewed by a repository admin.**
- The assignee (or reviewer) merges the pull request into the `master` branch.

## Coding style

Our preferred coding style is [PEP8](https://www.python.org/dev/peps/pep-0008/), although this is not currently mandated.

## Docstrings

It is preferred that docstrings are in [sphinx format](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html). [pydocstyle](https://pypi.org/project/pydocstyle/) may be a helpful tool for checking that documentation coverage is complete.

## Licensing

By contributing to this project (e.g. by submitting a pull request or providing advice on code), you agree - unless simultaneously and expressly stated otherwise - that your contribution may be included in the source code of the project and published under the [2-Clause BSD License](license.txt) and that the contribution was created in whole or in part by you and you have the right to submit it under the open source license indicated above.
