# automated-user-lifecycle

Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.

Owner: Oluwatobiloba Benjamin Ogungbangbe (Benjamin Ogungbangbe), GitHub BCarter04.
This work is mine. It is not for sale. See [LICENSE](LICENSE) and [OWNERSHIP.md](OWNERSHIP.md).
Permission to copy, reuse, or sell it is valid only if I confirm it myself.

> **Demo only.** This does not talk to a real tenant. It writes a local file on your computer. It will not create or disable a real Microsoft 365 account. Read [DISCLAIMER.md](DISCLAIMER.md) before you run it.

A business asked IT to stop building accounts by hand.

HR emails IT when someone joins or leaves. A technician then creates the account, picks groups from memory, assigns a licence, and later disables the leaver if the email is not missed. Movers are worse: the person changes department and keeps the old access.

This project replaces that email chain with one workflow. Read `NOTES.md` for the plain-language walkthrough of every file and every step.

```
HR CSV
  -> validate employee
  -> create account
  -> assign department, location, and role groups
  -> assign licence
  -> write an audit log
```

Leaver:

```
leaver request
  -> find account
  -> disable sign-in
  -> revoke sessions
  -> remove groups
  -> record the licence
  -> write a report
```

Mover:

```
Sales -> Infrastructure
  -> remove Sales groups
  -> add Infrastructure groups
  -> update department, title, and manager
  -> record the change
```

It runs on any machine with Python 3. No tenant, password, certificate, or client secret is required. The directory is a local JSON file, so the same folder works on a home PC, a lab VM, or a laptop that is not joined to anything.

## Start here

Double-click `Start-Here.bat` on Windows, or `Start-Here.sh` on Mac or Linux.

A window opens in your browser. You do not type a command.

1. Click **Set up this computer**. It creates the local folders. Nothing is downloaded.
2. Click **Run the sample demo**.
3. Click **Show the staff list** or **Open the ticket note**.

Python 3 is the only requirement. If it is missing, the launcher tells you where to get it. Tick "Add python.exe to PATH" on Windows. No other package is installed, and no tenant is contacted.

The ticket note is `reports/demo-summary.md`.

The demo writes `reports/demo-summary.md`. That is the one ticket note for the whole run.

Run the same joiner file again and existing people are marked already provisioned, not rejected. A real problem, such as an unknown department, is still rejected and the row number is printed.

`--strict-manager` rejects a joiner whose manager is not already in the directory. It is off for the demo, because the sample managers are placeholders. Maya Adebayo is the manager row, so `list` shows the managers group.

To start the demo again:

```bash
python3 src/lifecycle.py reset
python3 src/lifecycle.py demo
```

You can still run the steps one at a time:

```bash
python3 src/lifecycle.py joiner --input samples/joiners.csv
python3 src/lifecycle.py mover --input samples/movers.csv
python3 src/lifecycle.py leaver --input samples/leavers.csv
```

What you should see:

| Command | Expected result |
| --- | --- |
| joiner | 5 created, 1 rejected. Maya Adebayo is the manager row. E1005 is rejected, and the reason includes the row number. |
| mover | Ada Okoye moves from Finance to Infrastructure. The report lists groups removed and groups added. |
| leaver | Sam Patel is disabled. E9999 is reported as not found. The script does not invent that person. |

A second Ada Okoye is rejected because the email already exists. A disabled account cannot be moved.

Add `--dry-run` if you only want the checks and the report. The staff file is left unchanged.

On Windows:

```powershell
.\src\Invoke-UserLifecycle.ps1 -Action demo
.\src\Invoke-UserLifecycle.ps1 -Action list
```

Check the sample rules with:

```bash
python3 -m unittest tests/test_lifecycle.py
```

Help, if you forget the flags:

```bash
python3 src/lifecycle.py --help
```

## What each command is for

- `demo` runs the three sample files in order. It clears the local staff file first.
- `list` shows each person, whether they can sign in, and their groups.
- `reset` deletes only `data/directory.json`.
- `joiner` is a new employee. Bad rows are rejected and are not created.
- `mover` is a department, location, or role change. Old groups come off. New groups go on.
- `leaver` blocks sign-in, clears groups, and keeps the account as a record. It does not delete the person.

## Run it

From this folder:

```bash
python3 src/lifecycle.py joiner --input samples/joiners.csv
python3 src/lifecycle.py mover --input samples/movers.csv
python3 src/lifecycle.py leaver --input samples/leavers.csv
```

On Windows, the PowerShell script does the same demo path:

```powershell
.\src\Invoke-UserLifecycle.ps1 -Action joiner -InputPath .\samples\joiners.csv
```

Add `--dry-run` to validate without writing the directory. The report is still written.

After a joiner run you should see four accounts created and one rejected. The bad row uses a department that is not in the rules file. That rejection is intentional.

Outputs:

- `data/directory.json` is the demo directory. It stands in for Entra ID. It is gitignored.
- `logs/` is the audit log for the run. Each line is one person and one result.
- `reports/` is a short Markdown report you can attach to a ticket.

## How a decision is made

The script does not choose groups itself. `rules/department-rules.json` does.

- Department Finance gets finance groups and a finance licence.
- Location Corporate Office gets the site group.
- Role Manager gets the managers group.

A Finance manager in the corporate office gets all three sets. Change the rules file and the same script fits another company.

## Security

The sample tenant is `tenant.example.onmicrosoft.com`. Users are fake. Do not commit:

- a real tenant id
- passwords
- certificates or private keys
- client secrets
- a real employee export

`config.json`, `.env`, and `data/directory.json` are gitignored. Copy `config.example.json` if you want a local config.

Graph mode is not turned on. Connecting this to a Microsoft 365 developer tenant is a later step, and the secret stays in an environment variable, not in the repo.

## How to apply it

1. Put new starters in a CSV with the same columns as `samples/joiners.csv`.
2. Put department, location, and role groups in `rules/department-rules.json`.
3. Run the joiner command. Rejected rows stay out of the directory.
4. When someone changes team, send a mover CSV. Old groups come off.
5. When someone leaves, send a leaver CSV. The account is disabled, not deleted.
6. Attach the file in `reports/` to the ticket.

Use the sample files first. When the report looks right, copy `config.example.json` to `config.json` and point a later version at a Microsoft 365 developer tenant. Keep secrets out of git.

## Who owns this

I wrote this. Oluwatobiloba Benjamin Ogungbangbe is the sole owner.
It is not for sale, and nobody else can authorise sale or reuse.
If you want permission, ask me. Only a confirmation from me counts.

## Checklist

1. Desk Partner, endpoint playbooks that run on any PC.
2. This repo, joiner, mover, and leaver.
3. Tenant health check.
4. Intune device baseline.
5. Repeat-ticket finder.
6. Lab rebuild guide.
