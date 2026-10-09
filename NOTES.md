# Notes: how this project works

Demo only, and live use on this PC. Neither connects to a real tenant. See DISCLAIMER.md.

Read this first. The window in Start-Here is the easy path. This file explains the job in plain language.

## The problem

HR sends IT an email when someone joins, moves team, or leaves. A technician then creates the account, guesses the groups, assigns a licence, and hopes the leaver email is not missed. Old groups stay on after a move. That is how people keep access they should not have.

This project turns that email into a file and a script.

## The three actions

Joiner means a new employee. The script checks the row, builds an account, gives the right groups and licence, and writes a log.

Mover means the person changed department, location, or role. The script takes off groups that no longer apply and adds the new ones. It also updates the job title and manager.

Leaver means the person is leaving. The script finds the account, blocks sign-in, marks sessions as revoked, removes every group, records the licence they had, and writes a report. It does not delete the account. You want the record.

## What each file is for

- `samples/joiners.csv` is the HR list of new people. One row is one employee.
- `samples/movers.csv` is the list of people changing department.
- `samples/leavers.csv` is the list of people leaving.
- `rules/department-rules.json` is the map. Finance gets finance groups. Corporate Office gets the site group. Manager gets the manager group. Change this file to fit another company. Do not put group names in the script.
- `config.example.json` is the company settings used in the demo: fake tenant name, email domain, default licence. Copy it to `config.json` if you want your own copy. `config.json` is not committed.
- `src/lifecycle.py` is the program that runs on any computer with Python 3.
- `src/Invoke-UserLifecycle.ps1` is the same demo for Windows PowerShell.
- `data/directory.json` is the fake staff directory created when you run it. It stands in for Entra ID. It is not committed, because a real export must never go on GitHub.
- `logs/` is the audit log. Every create, reject, move, and disable is a line with a time.
- `reports/` is the short ticket note in Markdown.

## What the CSV must contain

The first row is the column names. The names must match. One person is one row. A blank required field is rejected. The staff file is not changed for that row.

Joiner, copy this header:

```text
employee_id,first_name,last_name,department,job_title,location,role,manager_email,start_date
E2001,Nia,Cole,Sales,Account Executive,Corporate Office,Staff,maya.adebayo@example.com,2026-10-20
```

- `employee_id` is the HR number. It must be unique.
- `first_name` and `last_name` build the email. Ada Okoye becomes `ada.okoye@example.com`.
- `department` must be in the rules file: Finance, Sales, Infrastructure, or People. `UnknownDept` is rejected on purpose.
- `location` must be Corporate Office or Remote.
- `role` is Staff or Manager. Manager adds the managers group.
- `manager_email` must look like an email address.
- `job_title` and `start_date` are stored. They do not pick groups.

Mover, copy this header:

```text
employee_id,email,new_department,new_job_title,new_location,new_role,new_manager_email,effective_date
E1001,ada.okoye@example.com,Infrastructure,IT Support Analyst,Corporate Office,Staff,maya.adebayo@example.com,2026-11-01
```

`employee_id` and `email` find the person. Only fill the `new_` columns that changed.

Leaver, copy this header:

```text
employee_id,email,last_day,reason
E1002,sam.patel@example.com,2026-10-31,Resignation
```

`employee_id` and `email` find the person. `reason` is written on the ticket note.

The full files you can load in the window are `samples/joiners.csv`, `samples/movers.csv`, and `samples/leavers.csv`. The window also shows these samples. Copy joiner sample, Copy mover sample, and Copy leaver sample put that text in the box and set the action. You can then click Preview.

Blank templates, header only, are `samples/blank-joiner.csv`, `samples/blank-mover.csv`, and `samples/blank-leaver.csv`. The window links to them. Save the file, add rows in Excel, then choose that file in the window. Do not change the header names.

Excel on a UK PC may save semicolons instead of commas, or put a hidden mark at the start of the file. The reader accepts both, and it ignores a blank row at the bottom. The column names must still match.

`finance`, `Finance`, and ` finance ` are the same department. The same is true for location and role. The saved account uses the name from the rules file.

A start date must be a real date: `2026-10-20` or `20/10/2026`. It is stored as `2026-10-20`. `32/10/2026`, `31/02/2026`, and `tomorrow` are rejected, and that person is not created. The result says `start_date is not a date`. A mover `effective_date` and a leaver `last_day` use the same rule when those columns are filled. The result line shows the stored date and the department name from the rules file.

## What a joiner row must contain

`employee_id` is the HR number. It must be unique.

`first_name` and `last_name` build the email. Ada Okoye becomes `ada.okoye@example.com`. Spaces and odd characters are removed.

`department` must exist in the rules file. `UnknownDept` is rejected on purpose, so you can see a bad HR row fail instead of creating a wrong account.

`location` picks site access, such as the office printer group.

`role` is Staff or Manager. Manager adds the managers group.

`manager_email` must look like an email address.

`job_title` and `start_date` are stored on the account. They do not pick groups.

## What the script does, step by step

1. Read the config and the rules.
2. Open `data/directory.json` if it exists. If it does not, start an empty directory.
3. Read the CSV you passed in.
4. For each row, run joiner, mover, or leaver.
5. Save the directory, unless you used `--dry-run`.
6. Write a JSON log and a Markdown report.

Dry-run still checks the rows and writes the report. It does not change the directory. Use it when you want to see what would happen.

## What the sample run proves

Joiners: five people are created. Maya Adebayo is the manager row, so the managers group appears. E1005 is rejected because the department is not in the rules and the manager email is missing.

Mover: Ada moves from Finance to Infrastructure. Finance groups come off. Infrastructure groups go on. The shared Microsoft 365 group stays.

Leaver: Sam Patel is disabled, groups cleared, licence recorded. E9999 is not found, so the script says so and does nothing else.

The window says PASS when those counts match.

## What was added

- `Start-Here.bat` and `Start-Here.sh` open a browser window. No command to type.
- The window sets up folders, runs the sample, lists staff, finds one person, and shows the rules.
- Live use takes a CSV from a file, a path, or a paste. Preview does not write. Run writes. Dry run says would create and does not change the staff file.
- A missing column stops the run before the staff file is touched.
- The file used is copied to `inbox/` with the same time as the ticket note. `inbox/` is not uploaded.
- A second run of the same person is unchanged, not rejected. PowerShell does the same.
- The demo line says PASS when the sample counts match.
- Preview shows a bad date before Run. Nothing is written at that point.
- PowerShell matches the window: semicolon files, `finance` for Finance, and a UK date. A bad date is rejected.
- `examples/demo-pass.png` is the sample result, so it can be seen without running the window.

## How to use this app

Open `Start-Here.bat`. The page is five numbered parts. You do not type a command.

1. Try the sample. Prepare this computer creates the local folders. Run the sample adds five fake people, rejects one bad row, moves Ada Okoye from Finance to Infrastructure, blocks Sam Patel, and reports E9999 as not found. A good run says PASS. The staff list shows who can still sign in. The ticket note is the text for a ticket.
2. Look up one person. Type E1001 or ada.okoye@example.com. You see the team, manager, licence, groups, and whether sign-in is allowed or blocked.
3. What each team gets. The rules file chooses the groups, not the program. Finance gets finance groups. Corporate Office gets the site group. Manager gets the managers group. Clear the staff list removes only the local staff file.
4. Use your own spreadsheet. Copy a new starter, a team change, or a leaver. The first row must be the column names. Check first shows the rows and any bad date, and it does not save. Apply saves the staff list on this PC. A date must be 2026-10-20 or 20/10/2026. The team must be Finance, Sales, Infrastructure, or People.
5. Microsoft 365 is optional. Leave it blank unless an admin gave you the tenant name, tenant id, client id, email domain, and client secret. Save keeps the secret in .secret on this PC. That file is not uploaded. Test connection asks Entra for a token and does not create or block a person.

The sample uses fake people and does not change a real account.

## How to connect a real tenant

The live form is on the same page, under Connect a real tenant on this PC. It is the real-world path. It is not a second program. It asks for the details and keeps them on this PC.

You need, from Entra admin centre:

- The tenant name, such as `contoso.onmicrosoft.com`.
- The tenant id.
- An app registration, and its application client id.
- Application permissions User.ReadWrite.All and GroupMember.ReadWrite.All, with admin consent granted.
- A client secret. Paste it in the form once. It is saved only in `.secret` on this PC. `.secret` and `config.json` are not uploaded.

Click Save on this PC, then Test connection. A good test says Entra accepted the app. That test does not create or disable a user.

After the test succeeds, the same CSV and the same rules file are the input. The order stays validate, create, groups, licence, log. If a step fails, stop that person and write the error. Do not guess.

## What is done

This public repo is finished as a demo and as a live check on one PC.

- Joiner, mover, and leaver run on a local staff file. No tenant is contacted.
- The window opens from Start-Here. No command is required.
- Preview, run, dry run, find one person, rules, samples, and blank templates are on the page.
- A second run is unchanged. A disabled account cannot be moved. A bad department or a bad date is rejected.
- Excel files are accepted. Ten tests pass.
- Ownership, the demo disclaimer, and this file are in the repo.

## What is not done now, and what it will be

The demo path does not contact a tenant. The live form does, and only after you fill it on this PC.

The live form saves the tenant name, tenant id, client id, and email domain in `config.json`. It saves the secret in `.secret`. Both files are gitignored. A connection test asks Entra for a token and does not create a user.

Creating and disabling real accounts from the same CSV is the next step after a successful test. It uses the same validate, create, groups, licence, log order. It is not run by the sample demo.

## What it does not do

It does not talk to a real Microsoft tenant. That is deliberate. The demo has to run on any PC without a login.

It does not store passwords. A real Entra create would set a temporary password outside this repo, or use a tap-to-sign-in method.

It does not delete leavers. Disable first. Delete later, after the retention period, as a separate job.

It does not unlock accounts or change anyone else's machine.

## If you later connect a developer tenant

This is not built now. The explanation is here so the later step is clear.

Keep using the same CSV and the same rules file. Copy `config.example.json` to `config.json`. Put the tenant name in `config.json`. That file is not uploaded. Put any secret in an environment variable. Do not paste a secret into a file that git can see.

The Graph calls, when they are added, should follow the same order as the demo: validate, create, groups, licence, log. If a step fails, stop that person and write the error. Do not continue and guess.
