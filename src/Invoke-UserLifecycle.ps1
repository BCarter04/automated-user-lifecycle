<#
.SYNOPSIS
  Joiner, mover, and leaver workflow for a systems administrator portfolio.

  Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
  Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
  Permission is valid only if the owner confirms it himself.

.DESCRIPTION
  This is the Windows copy of src/lifecycle.py. Same CSV files, same rules file,
  same local directory. Read NOTES.md for the plain-language walkthrough.

  Demo mode is the default. It updates data/directory.json and writes an audit log.
  It does not connect to a tenant and it does not read secrets.

  What each parameter does
  - Action: joiner creates accounts, mover changes department, leaver disables them.
  - InputPath: the HR CSV for that action.
  - ConfigPath: fake tenant name and email domain.
  - RulesPath: which department, location, and role get which groups.
  - DirectoryPath: the staff file this script creates. Stand-in for Entra ID.
  - DryRun: check and log, but do not write the staff file.

.EXAMPLE
  .\src\Invoke-UserLifecycle.ps1 -Action joiner -InputPath .\samples\joiners.csv
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("joiner", "mover", "leaver")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$ConfigPath = (Join-Path $PSScriptRoot "..\config.example.json"),
    [string]$RulesPath = (Join-Path $PSScriptRoot "..\rules\department-rules.json"),
    [string]$DirectoryPath = (Join-Path $PSScriptRoot "..\data\directory.json"),
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-JsonFile {
    param([string]$Path)
    # Config, rules, and the saved directory are all JSON.
    Get-Content -Raw -Path $Path | ConvertFrom-Json
}

function Get-EmailSlug {
    param([string]$First, [string]$Last)
    # "Ada Okoye" becomes "ada.okoye" for the mailbox name.
    return (("{0}.{1}" -f $First, $Last).ToLower() -replace "[^a-z0-9.]", "")
}

function Get-Groups {
    param($Rules, [string]$Department, [string]$Location, [string]$Role)
    # Groups come from the rules file: department, then site, then role.
    $groups = @()
    $groups += @($Rules.departments.$Department.groups)
    if ($Rules.locations.PSObject.Properties.Name -contains $Location) {
        $groups += @($Rules.locations.$Location.groups)
    }
    if ($Rules.roles.PSObject.Properties.Name -contains $Role) {
        $groups += @($Rules.roles.$Role.groups)
    }
    return @($groups | Where-Object { $_ } | Select-Object -Unique | Sort-Object)
}

# Load the company settings and the group map. Start an empty directory on first run.
$config = Read-JsonFile -Path $ConfigPath
$rules = Read-JsonFile -Path $RulesPath
if (Test-Path $DirectoryPath) {
    $directory = Read-JsonFile -Path $DirectoryPath
} else {
    $directory = [pscustomobject]@{ tenant = $config.tenant; users = @() }
}
if (-not $directory.users) { $directory | Add-Member -NotePropertyName users -NotePropertyValue @() -Force }

$rows = Import-Csv -Path $InputPath
$events = @()
$users = @($directory.users)

foreach ($row in $rows) {
    if ($Action -eq "joiner") {
        # Reject a blank field or a department that is not in the rules file.
        $errors = @()
        foreach ($field in @("employee_id", "first_name", "last_name", "department", "job_title", "location", "role", "manager_email", "start_date")) {
            if (-not $row.$field) { $errors += "missing $field" }
        }
        if ($row.department -and $rules.departments.PSObject.Properties.Name -notcontains $row.department) {
            $errors += "unknown department '$($row.department)'"
        }
        if ($errors.Count -gt 0) {
            $events += [pscustomobject]@{ time = (Get-Date).ToUniversalTime().ToString("o"); action = "joiner"; status = "rejected"; employee_id = $row.employee_id; errors = $errors }
            continue
        }
        $slug = Get-EmailSlug -First $row.first_name -Last $row.last_name
        $groups = Get-Groups -Rules $rules -Department $row.department -Location $row.location -Role $row.role
        $user = [pscustomobject]@{
            employee_id = $row.employee_id
            first_name  = $row.first_name
            last_name   = $row.last_name
            email       = "$slug@$($config.default_domain)"
            upn         = "$slug@$($config.tenant)"
            department  = $row.department
            job_title   = $row.job_title
            location    = $row.location
            role        = $row.role
            manager_email = $row.manager_email
            enabled     = $true
            groups      = $groups
            licence     = $rules.departments.($row.department).licence
            created_at  = (Get-Date).ToUniversalTime().ToString("o")
        }
        $users += $user
        $events += [pscustomobject]@{ time = (Get-Date).ToUniversalTime().ToString("o"); action = "joiner"; status = "created"; employee_id = $user.employee_id; email = $user.email }
    }
    elseif ($Action -eq "leaver") {
        # Block sign-in, clear groups, keep the account as a record.
        $user = $users | Where-Object { $_.employee_id -eq $row.employee_id -or $_.email -eq $row.email } | Select-Object -First 1
        if (-not $user) {
            $events += [pscustomobject]@{ time = (Get-Date).ToUniversalTime().ToString("o"); action = "leaver"; status = "not_found"; employee_id = $row.employee_id }
            continue
        }
        $user.enabled = $false
        $user.sessions_revoked = $true
        $user.licence_at_leave = $user.licence
        $user.licence = $null
        $user.groups = @()
        $events += [pscustomobject]@{ time = (Get-Date).ToUniversalTime().ToString("o"); action = "leaver"; status = "disabled"; employee_id = $user.employee_id; email = $user.email }
    }
    else {
        # Rebuild groups from the new department. Old-only groups come off.
        $user = $users | Where-Object { $_.employee_id -eq $row.employee_id -or $_.email -eq $row.email } | Select-Object -First 1
        if (-not $user) {
            $events += [pscustomobject]@{ time = (Get-Date).ToUniversalTime().ToString("o"); action = "mover"; status = "not_found"; employee_id = $row.employee_id }
            continue
        }
        $department = if ($row.new_department) { $row.new_department } else { $user.department }
        $location = if ($row.new_location) { $row.new_location } else { $user.location }
        $role = if ($row.new_role) { $row.new_role } else { $user.role }
        $user.department = $department
        $user.location = $location
        $user.role = $role
        if ($row.new_job_title) { $user.job_title = $row.new_job_title }
        if ($row.new_manager_email) { $user.manager_email = $row.new_manager_email }
        $user.groups = @(Get-Groups -Rules $rules -Department $department -Location $location -Role $role)
        $events += [pscustomobject]@{ time = (Get-Date).ToUniversalTime().ToString("o"); action = "mover"; status = "moved"; employee_id = $user.employee_id; email = $user.email; department = $department }
    }
}

$directory.users = @($users)
if (-not $DryRun) {
    $directory | ConvertTo-Json -Depth 6 | Set-Content -Path $DirectoryPath -Encoding utf8
}

# Audit log. One file per run, named with the action and the time.
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$logDir = Join-Path $PSScriptRoot "..\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "$Action-$stamp.json"
[pscustomobject]@{ tenant = $config.tenant; action = $Action; events = $events } |
    ConvertTo-Json -Depth 6 |
    Set-Content -Path $logPath -Encoding utf8

$events | Format-Table status, employee_id, email -AutoSize
Write-Host "audit log: $logPath"
if ($config.mode -eq "graph") {
    Write-Warning "Graph mode is not implemented in this portfolio build. Use demo mode unless you add Graph calls locally and keep secrets out of git."
}
