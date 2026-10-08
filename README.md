# automated-user-lifecycle

Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.

Owner: Oluwatobiloba Benjamin Ogungbangbe (Benjamin Ogungbangbe), GitHub BCarter04.
This work is mine. It is not for sale. See [LICENSE](LICENSE) and [OWNERSHIP.md](OWNERSHIP.md).
Permission to copy, reuse, or sell it is valid only if I confirm it myself.

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
