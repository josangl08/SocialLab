# GitHub Feedback Workflow for Issue #$ARGUMENT$

## Setup Phase
1. Fetch latest branches: `git fetch origin`
2. Get issue details
   - Fetch issue title: `gh issue view $ARGUMENT$ --json title -q .title`

## Analysis Phase
1. Read the full issue content and ALL comments using: `gh issue view $ARGUMENT$ --comments`
2. Analyze the requirements, context, and feedback thoroughly

## Implementation Phase
1. Implement a plan to apply the changes needed for the feedback in the PR
2. Execute the plan step by step, remember to build test before the implementation and run the test suite constantly to get quick feedback
3. Create always unit tests
4. Ensure consistency with existing code in the branch
5. Run local builds and tests suite before git commit & push
6. Never implement the manual tests
7. Update the PR with the new changes that covers the feedback
8. Report status of completeness:

<results>

  # Summary of the requirements implemented:
	- req 1
	- req 2
	- ...

  # Requirements pending
	- req 1
	- req 2
	- ...

  # Tests implemented and their run status (Backend)
     PASSED backend/tests/test_caption_generator.py::test_generate_caption
     PASSED backend/tests/test_scheduler.py::test_schedule_post

  # Tests implemented and their run status (Frontend)
     PASSED frontend/src/__tests__/PostGenerator.test.tsx
     PASSED frontend/src/__tests__/Calendar.test.tsx

  # Proof that all builds pass
     Backend build: ✅ OK
     Frontend build: ✅ OK

  # Overall status: [Needs More Work/All Completed]
  # PR: github-pr-url
</result>

9. Stay tuned to the PR until the deploy is done successfully using `gh pr view {pr_number} --json statusCheckRollup,state,mergeable,url)`
10. If some verification fails check the problems and implement the fixes updating the PR and try again in loop until have all verifications in success

## Important Notes
- The "All completed" is the desired status and we can only arrive if we have implemented all the requirements and all the test suite are implemented and green otherwise we need more work until that happens
- Always use `gh` CLI for GitHub operations
- Keep detailed records of all actions as PR/issue comments
- Wait for explicit confirmation before proceeding with major changes

## Final checks
- After create the PR review that the validations in the pipeline are success, if they are pending wait until they are success checking using `gh pr view {pr_number} --json statusCheckRollup,state,mergeable,url)`
- If the validations are failed, review the issues or ask for them to me
- After have the issues, implement the fixes and push again to the PR until all the validations are success, continue in loop until have them all in green
- Once all is green, update the issue with a comment of what is implemented and your labour is finished
