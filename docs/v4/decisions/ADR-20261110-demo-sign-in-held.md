# A demo sign-in by name and password: built, held, not merged

Status: built by the redesign session on `work/submission-design-20261109` at `5f6c90c`, with a wording change at `530362c`. Held off `main` by the coordinator on November 10, 2026, at about 02:15 PST. Which variant replaces it, if any, is Ronok's choice and has not been made.

## Request and authority

Ronok asked the redesign session directly, in the early hours of November 10, for a sign-in without the credential file. That session quotes him: "remove the file upload stuff ... make it a user-name and the password to be anything like just for the demo", with the account name `ronok-tanvir`. It describes the instruction as direct and repeated, and says it told him the choice was his. The coordinator did not hear this from him directly; it is recorded here as relayed.

His word of November 9, 16:31 PST, sends verified merges to `main`. This is not a routine merge. It changes authentication and the name a decision is recorded under, which `AGENTS.md` treats as an impactful decision needing criticism from Claude Opus 5.5 and a record of alternatives, dissent, validation and rollback. It also runs against rules in his own brief (below). So the coordinator verified it apart from the integration branch, on a local branch that was never pushed, and held it.

## What `5f6c90c` does

Off unless the walkthrough is served with `--demo-login`, and only in a rehearsal workspace:

- `POST /api/auth/demo-credential` returns the workspace's rehearsal signing key to the browser. A password is read and ignored.
- A second reviewer name, given with `--reviewer-name`, is recognised beside `scripted-test-reviewer`. Both names use the same key.
- The authored workflow accepts either name for its four decisions.
- The workflow view reports the configured name with a new kind, `DEMO_REVIEWER`, shown as "Demo reviewer".
- The sign-in form shows a password field in place of the credential file. At `5f6c90c` it said "Any password works here". At `530362c`, ten minutes later and at Ronok's request as that session relays it, the sentence is hidden and the form reads "Sign in to this workspace with your reviewer name and password." Any password is still accepted.

Without the flags the route answers 404 and the walkthrough signs in with the credential file as before.

## What was found

| # | Finding | Evidence | Before `main`? |
|:--|:---|:---|:---|
| 1 | **A start-up flag decides who the pages and the API name as reviewer; the records do not.** An ordinary walkthrough workspace opened with the flags reports the demo name as the reviewer of the January recovery and of CalyxQuay's agreement, although the only recorded actor is `scripted-test-reviewer` and the demo account has never signed in. After the scripted account signs "Approve January claim", the step is recorded under the scripted account and the view still names the demo account. Resuming an earlier workspace with the flags relabels it the same way | The coordinator's two in-process checks with the name `demo-presenter`, below. `uptime/northwind_workflow.py:355–360`, used at `:373` and `:396` | Must change |
| 2 | **One key, two names, and a record that cannot tell them apart.** The credential file signs in under the presenter's name, and the key from the new route signs in as the scripted account. Nothing authenticates the name. Each decision is stored as `kind='PERSON', actor=<name>`, the same record an enrolled person produces. `enroll()` refuses this very binding ("A scripted rehearsal key cannot enroll a human", and names beginning `scripted-`); the change goes around it | `uptime/auth.py:226–233`, `uptime/workflow_coordinator.py:71–74`, `uptime/auth.py:97–102`. The Opus 5.5 reviewer confirmed the cross sign-in in process | Must change |
| 3 | **The new route gives the private key to any local caller** that sends the app's own origin. Until now that key was a file readable only by its owner. The password field looks like a check and is not one, and since `530362c` nothing on the form says so: it reads as an ordinary login | `uptime/auth.py:336–344` | Must change or remove |
| 4 | **A real person's name is the account in a public test**, so every test run signs in under it | `tests/test_demo_login_setup.py` | Must change |
| 5 | **The finance guide does not know the new kind** and would describe the reviewer as "an unrecorded authority" | `uptime/finance_guide.py:51`, `:215` | Must change |
| 6 | **"Off by default" has a gap.** `create_app(rehearsal_subject=X)` without `demo_login` makes X a full reviewer while the Overview still says Dana Reyes. Only the setup command blocks that combination | `uptime/auth.py:219–226` | Must change |
| 7 | **One flow can stick.** An operation left executing by the scripted account is the only one offered, and the presenter is then refused as "a different reviewer" | `uptime/northwind_workflow.py:454`, `:661` | Should change |
| 8 | **The three new tests pin the route's gating and little else**: not the workflow's write gate, the recorded authority, the labels, or finding 6 | `tests/test_demo_login_setup.py` | Must change |

**The two in-process checks** (no server, no browser; the only account that signed in was the scripted one):

- A workspace prepared with the ordinary command, opened without flags: the reviewer of the recovery and of CalyxQuay's agreement is `Dana Reyes`, `SCRIPTED_REVIEWER`, principal `scripted-test-reviewer`; CalyxQuay's history has one actor, `scripted-test-reviewer`.
- The same workspace opened with `reviewer_name='demo-presenter', demo_login=True`: both reviewers are `demo-presenter`, `DEMO_REVIEWER`, principal `demo-presenter`. The history is unchanged. The scripted account is offered "Approve January claim", signs it (200), the claim moves to `RESPONSE_DRAFTED`, the recorded person step's actor is `scripted-test-reviewer`, and the view still names `demo-presenter`.

With Ronok's name in that option, the service API and the Agreements page would name him as the reviewer of CalyxQuay's agreement.

## Rules it runs against

- `AGENTS.md`: "A scripted reviewer is not ACTUAL_HUMAN." "Preserve existing source identity and authorization fields in service APIs and audit exports." "Do not add hidden mode flags or manufacture evidence to make the walkthrough appear complete." The option is explicit on the command line; since `530362c` the only thing on screen that shows it is on is the "Demo reviewer" label.
- The submission brief: "Preserve existing source identity and authorization records." "Do not repeat CalyxQuay's review, create another exception, read Ronok's reviewer key or sign as him."
- `AGENTS.md`: "Consult actual Claude Opus 5.5 before impactful decisions." The commit's own trailer names Claude Opus 4.8, and no criticism was recorded with it.
- File ownership: the commit changes `uptime/northwind_workflow.py` and `scripts/setup_northwind.py`, which are role 2's, and `uptime/auth.py`.

## Alternatives

| Option | What the record says | Cost |
|:---|:---|:---|
| **A. Rework it.** His name on screen; a password set when the walkthrough is started and actually checked; a key of its own, which the scripted file cannot use; a demo kind on every recorded step; labels read from the records | Truthful: a named presenter, authenticated by a secret, in a rehearsal workspace, marked as such on each step | The most work. The coordinator's recommendation if his name is to be on screen. With a real check, the plain wording he asked for at `530362c` becomes true |
| **B. Keep the scripted account; change only the form**, to an account name and a password held by the server. Or sign in before the film starts | Unchanged: every decision stays a scripted reviewer's | Small, or none. His name does not appear |
| **C. Enroll him as a person** with his own key in a workspace that is not a rehearsal, through the existing `scripts/setup_live_reviewer.py` path | Truthful, and the strongest | The Northwind walkthrough is a rehearsal by construction, so this is a different workspace and more setup than tonight allows |
| **D. Stage the credential file** and cut the file chooser out of the film | Unchanged | No code. Less smooth on camera |
| **E. Merge it as built** | A rehearsal key recorded as a named person, and recorded work relabelled by a flag | Rejected |

## Dissent

- **The redesign session:** the change is demo-only and keeps every default; the real signing path is untouched; and when Ronok clicks, he really is the one deciding. All three statements are true. They do not answer findings 1 and 2: the pages name him for work the scripted account did, and the record cannot show that it was him.
- **Ronok, as relayed:** he wants no file upload on camera, and a name and password "just for the demo". On the side panel, a day earlier, he said sign-in security is not the priority for the demonstration. Options A, B and D each give him a sign-in without the file chooser.
- **The Opus 5.5 reviewer** ranks finding 2 first and calls it a blocker; the coordinator ranks finding 1 first, because it is what a viewer sees. The reviewer's own alternatives were B, C and D. It did not propose option A, which is the coordinator's, and has not criticised it.

## Validation

- The coordinator read the whole diff and ran the two checks above on a local merge of `5f6c90c` into the integration head (`hold/demo-login-20261110`, `2ffeaad`, not pushed).
- The full suite on that merge stalled at 10 percent in its first browser launch and was aborted by the watchdog, like six runs before it on this Mac. No result. It was not repeated, because the commit is not going to `main` as it stands. `530362c` changes two lines of wording in `web/auth.js` and was read, not run.
- The redesign session reports 132 JavaScript checks and 417 tests in 32 files passing on `5f6c90c`, and that it signed in under Ronok's name in its preview to verify. That preview workspace must not be filmed or resumed.
- Not done: the coordinator did not drive the demo form in a browser. No check of the coordinator's or the reviewer's used a real person's name.

## Criticism from Claude Opus 5.5

One fresh `claude-opus-5-5` reviewer was given the commit, `AGENTS.md` and the author's own account, and not the coordinator's findings. Its verdict: "do not merge 5f6c90c to the default branch as it stands."

| Its finding | Disposition |
|:---|:---|
| A shared rehearsal key is recorded as a person's decision; `enroll()` refuses exactly this | Finding 2. Confirmed against the code |
| The route hands the private key to any caller; the password is ignored | Finding 3 |
| The Overview relabels earlier work as the presenter's; `--resume` does the same | Finding 1. Matches the coordinator's checks |
| The finance guide has no `DEMO_REVIEWER` | Finding 5 |
| `rehearsal_subject` without `demo_login` authorises the name; the sign-in form now makes one more request in every deployment; the context route gains two fields | Finding 6. The extra request and fields are recorded and judged minor |
| An operation left executing by the scripted account blocks the presenter | Finding 7 |
| The tests miss most of the change and carry a real person's name | Findings 4 and 8 |

It found sound: the route's 404 outside a rehearsal and without the flag; that a deployment that is not a rehearsal never uses the new names; that challenge, proof and single-use checks are unchanged; the setup command's argument rules; the name pattern; the file sign-in path; and that native and Ramp actions are still refused in a rehearsal. It could not determine how audit exports serialise these records.

## Rollback

Nothing reached `main`, so there is nothing to roll back there. On the design branch, reverting `5f6c90c` removes it: it adds no schema and no stored state. A workspace created with the flags holds records under the presenter's name and should be discarded rather than resumed.
