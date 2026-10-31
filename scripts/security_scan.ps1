
---

## 2. `scripts/security_scan.ps1`

```powershell
<#
.SYNOPSIS
    DCAP Security Scan — SAST/SCA/DAST/secrets/containers (53.5, v3.14.16).

.DESCRIPTION
    Запускает: Bandit, Semgrep, Gitleaks, pip-audit, Trivy (image/config), ZAP (WebUI/API).
    Собирает единый JSON (reports/security_summary.json) + HTML (reports/security_summary.html).
    Поддерживает allowlist (security_allowlist.yml) для FP/принятых рисков.

.PARAMETER ProjectRoot
    Корень проекта (по умолчанию — текущая директория).

.PARAMETER ReportsDir
    Куда складывать отчёты (по умолчанию — reports).

.PARAMETER SkipDast
    Пропустить DAST (ZAP — медленный, требует стенд :18000/:18001).

.PARAMETER SkipContainer
    Пропустить Trivy image/config (медленный, требует Docker-образы).

.PARAMETER FailOnHigh
    Exit 1, если HIGH/CRITICAL > 0 (для CI gate).

.PARAMETER Ci
    CI-режим (без интерактива, без цветного вывода).

.PARAMETER Format
    text (по умолчанию) / json / html.

.EXAMPLE
    .\scripts\security_scan.ps1 -SkipDast -SkipContainer
    .\scripts\security_scan.ps1 -Ci -SkipDast -SkipContainer -FailOnHigh
#>

param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$ReportsDir = "reports",
    [switch]$SkipDast = $false,
    [switch]$SkipContainer = $false,
    [switch]$FailOnHigh = $false,
    [switch]$Ci = $false,
    [ValidateSet("text","json","html")]
    [string]$Format = "text"
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# --- helpers ---------------------------------------------------------------

function Write-Step([string]$msg, [string]$color = "Cyan") {
    if (-not $Ci) { Write-Host "[STEP] $msg" -ForegroundColor $color }
}

function Write-Ok([string]$msg) { if (-not $Ci) { Write-Host "[ OK ] $msg" -ForegroundColor Green } }
function Write-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Ensure-Dir([string]$path) {
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Has-Cmd([string]$name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Has-Docker() {
    if (-not (Has-Cmd "docker")) { return $false }
    try { docker info *> $null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

$script:Findings = New-Object System.Collections.Generic.List[object]
$script:ToolStatus = [ordered]@{}

function Add-Finding {
    param(
        [string]$Tool, [string]$Severity, [string]$Category,
        [string]$RuleId, [string]$File, [string]$Line, [string]$Message,
        $Raw
    )
    $script:Findings.Add([pscustomobject]@{
        tool      = $Tool
        severity  = $Severity.ToLower()
        category  = $Category
        rule_id   = $RuleId
        file      = $File
        line      = $Line
        message   = $Message
        raw       = $Raw
    })
}

function Set-ToolStatus([string]$Tool, [string]$Status, [int]$Count = 0, [int]$DurationMs = 0) {
    $script:ToolStatus[$Tool] = [pscustomobject]@{
        status      = $Status
        findings    = $Count
        duration_ms = $DurationMs
    }
}

# --- load allowlist -------------------------------------------------------

$allowlistPath = Join-Path $ProjectRoot "security_allowlist.yml"
$script:Allowlist = @()
if (Test-Path $allowlistPath) {
    try {
        # Простой YAML-парсер (без зависимостей): только tool/rule_id/file
        $text = Get-Content $allowlistPath -Raw -Encoding UTF8
        $current = $null
        foreach ($line in ($text -split "`n")) {
            if ($line -match '^\s*-\s*tool:\s*(.+)$') {
                if ($current) { $script:Allowlist += $current }
                $current = [pscustomobject]@{ tool = $Matches[1].Trim(); rule_id = $null; file = $null }
            } elseif ($line -match '^\s*rule_id:\s*(.+)$' -and $current) {
                $current.rule_id = $Matches[1].Trim()
            } elseif ($line -match '^\s*file:\s*(.+)$' -and $current) {
                $current.file = $Matches[1].Trim()
            }
        }
        if ($current) { $script:Allowlist += $current }
    } catch {
        Write-Warn "Allowlist parse error: $_"
    }
}

function Is-Allowed($finding) {
    foreach ($a in $script:Allowlist) {
        if ($a.tool -and $a.tool -ne $finding.tool) { continue }
        if ($a.rule_id -and $a.rule_id -ne $finding.rule_id) { continue }
        if ($a.file -and $finding.file -and ($finding.file -notlike "*$($a.file)*")) { continue }
        return $true
    }
    return $false
}

# --- tool runners ---------------------------------------------------------

function Run-Bandit([string]$dir) {
    $out = Join-Path $ReportsDir "bandit_report.json"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Cmd "bandit")) {
        Write-Warn "Bandit not installed (pip install bandit) — skip"
        Set-ToolStatus "bandit" "skipped"
        return
    }
    Write-Step "Bandit (SAST Python) ..."
    $paths = @("manager/src","scanner/src","webui") | Where-Object { Test-Path (Join-Path $dir $_) } |
             ForEach-Object { Join-Path $dir $_ }
    if (-not $paths) { Set-ToolStatus "bandit" "skipped"; return }
    $args = @("-r") + $paths + @("-f","json","-o",$out)
    & bandit @args 2>&1 | Out-Null
    if (Test-Path $out) {
        try {
            $j = Get-Content $out -Raw | ConvertFrom-Json
            $n = 0
            foreach ($r in ($j.results | Where-Object { $_.issue_severity -in @("HIGH","MEDIUM") -and $_.issue_confidence -eq "HIGH" })) {
                Add-Finding -Tool "bandit" -Severity $r.issue_severity -Category "sast" `
                    -RuleId $r.test_id -File $r.filename -Line $r.line_number -Message $r.issue_text -Raw $r
                $n++
            }
            Set-ToolStatus "bandit" "ok" $n $sw.ElapsedMilliseconds
            Write-Ok "Bandit: $n findings"
        } catch { Set-ToolStatus "bandit" "error"; Write-Err "Bandit parse error: $_" }
    } else { Set-ToolStatus "bandit" "error" }
}

function Run-Semgrep([string]$dir) {
    $out = Join-Path $ReportsDir "semgrep_report.json"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Cmd "semgrep")) {
        Write-Warn "Semgrep not installed (pip install semgrep) — skip"
        Set-ToolStatus "semgrep" "skipped"; return
    }
    Write-Step "Semgrep (SAST Python+JS) ..."
    & semgrep --config=p/owasp-top-ten --config=p/python --config=p/javascript `
        --json -o $out $dir 2>&1 | Out-Null
    if (Test-Path $out) {
        try {
            $j = Get-Content $out -Raw | ConvertFrom-Json
            $n = 0
            foreach ($r in ($j.results | Where-Object { $_.extra.severity -eq "ERROR" })) {
                Add-Finding -Tool "semgrep" -Severity "high" -Category "sast" `
                    -RuleId $r.check_id -File $r.path -Line $r.start.line -Message $r.extra.message -Raw $r
                $n++
            }
            Set-ToolStatus "semgrep" "ok" $n $sw.ElapsedMilliseconds
            Write-Ok "Semgrep: $n findings"
        } catch { Set-ToolStatus "semgrep" "error"; Write-Err "Semgrep parse error: $_" }
    } else { Set-ToolStatus "semgrep" "error" }
}

function Run-Gitleaks([string]$dir) {
    $out = Join-Path $ReportsDir "gitleaks_report.json"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Docker)) {
        Write-Warn "Docker not available — Gitleaks skip"
        Set-ToolStatus "gitleaks" "skipped"; return
    }
    Write-Step "Gitleaks (secrets) ..."
    $src = $dir.Replace("\","/")
    & docker run --rm -v "${src}:/path" ghcr.io/gitleaks/gitleaks:latest detect `
        --source=/path --report-format=json --report-path=/path/reports/gitleaks_report.json 2>&1 | Out-Null
    if (Test-Path $out) {
        try {
            $j = Get-Content $out -Raw | ConvertFrom-Json
            $n = 0
            foreach ($r in $j) {
                Add-Finding -Tool "gitleaks" -Severity "high" -Category "secrets" `
                    -RuleId $r.RuleID -File $r.File -Line $r.StartLine -Message $r.Description -Raw $r
                $n++
            }
            Set-ToolStatus "gitleaks" "ok" $n $sw.ElapsedMilliseconds
            Write-Ok "Gitleaks: $n findings"
        } catch { Set-ToolStatus "gitleaks" "error"; Write-Err "Gitleaks parse error: $_" }
    } else { Set-ToolStatus "gitleaks" "error" }
}

function Run-PipAudit([string]$dir) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Cmd "pip-audit")) {
        Write-Warn "pip-audit not installed (pip install pip-audit) — skip"
        Set-ToolStatus "pip-audit" "skipped"; return
    }
    Write-Step "pip-audit (SCA Python) ..."
    $n = 0
    foreach ($req in @("requirements.txt","scanner/requirements.txt")) {
        $reqPath = Join-Path $dir $req
        if (-not (Test-Path $reqPath)) { continue }
        $out = Join-Path $ReportsDir ("pip_audit_" + ($req -replace "[\\/]","_") + ".json")
        & pip-audit -r $reqPath --desc -f json -o $out 2>&1 | Out-Null
        if (Test-Path $out) {
            try {
                $j = Get-Content $out -Raw | ConvertFrom-Json
                foreach ($v in $j) {
                    foreach ($d in $v.deps) {
                        foreach ($vl in $d.vulns) {
                            $sev = "high"
                            if ($vl.id -match "^(CVE|GHSA)") { $sev = "high" }
                            Add-Finding -Tool "pip-audit" -Severity $sev -Category "sca" `
                                -RuleId $vl.id -File $req -Line "" -Message $vl.description -Raw $vl
                            $n++
                        }
                    }
                }
            } catch { }
        }
    }
    Set-ToolStatus "pip-audit" "ok" $n $sw.ElapsedMilliseconds
    Write-Ok "pip-audit: $n findings"
}

function Run-TrivyImage([string]$dir) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Docker)) {
        Write-Warn "Docker not available — Trivy image skip"
        Set-ToolStatus "trivy-image" "skipped"; return
    }
    Write-Step "Trivy (image CVE) ..."
    $n = 0
    foreach ($img in @("dcap/manager:3.14.16","dcap/webui:3.14.16")) {
        $out = Join-Path $ReportsDir ("trivy_" + ($img -replace "[/:]","_") + ".json")
        & docker run --rm aquasec/trivy image $img --severity HIGH,CRITICAL --format json -o $out 2>&1 | Out-Null
        if (Test-Path $out) {
            try {
                $j = Get-Content $out -Raw | ConvertFrom-Json
                foreach ($r in ($j.Results | ForEach-Object { $_.Vulnerabilities }) | Where-Object { $_ }) {
                    Add-Finding -Tool "trivy" -Severity $r.Severity.ToLower() -Category "container-cve" `
                        -RuleId $r.VulnerabilityID -File $img -Line "" -Message $r.Title -Raw $r
                    $n++
                }
            } catch { }
        }
    }
    Set-ToolStatus "trivy-image" "ok" $n $sw.ElapsedMilliseconds
    Write-Ok "Trivy image: $n findings"
}

function Run-TrivyConfig([string]$dir) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Docker)) {
        Write-Warn "Docker not available — Trivy config skip"
        Set-ToolStatus "trivy-config" "skipped"; return
    }
    Write-Step "Trivy (config) ..."
    $out = Join-Path $ReportsDir "trivy_config_report.json"
    $src = $dir.Replace("\","/")
    & docker run --rm -v "${src}:/path" aquasec/trivy config /path --format json -o /path/reports/trivy_config_report.json 2>&1 | Out-Null
    $n = 0
    if (Test-Path $out) {
        try {
            $j = Get-Content $out -Raw | ConvertFrom-Json
            foreach ($r in $j.Results) {
                foreach ($m in $r.Misconfigurations) {
                    Add-Finding -Tool "trivy" -Severity $m.Severity.ToLower() -Category "container-config" `
                        -RuleId $m.ID -File $r.Target -Line "" -Message $m.Title -Raw $m
                    $n++
                }
            }
        } catch { }
    }
    Set-ToolStatus "trivy-config" "ok" $n $sw.ElapsedMilliseconds
    Write-Ok "Trivy config: $n findings"
}

function Run-Zap([string]$url, [string]$target, [string]$kind, [string]$outName) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not (Has-Docker)) {
        Write-Warn "Docker not available — ZAP ($kind) skip"
        Set-ToolStatus "zap-$kind" "skipped"; return
    }
    Write-Step "ZAP ($kind) ..."
    $reportsMount = (Join-Path $dir $ReportsDir).Replace("\","/")
    $args = @("run","--rm","-v","${reportsMount}:/zap/wrk/:rw","-t","zaproxy/zap-stable")
    if ($kind -eq "baseline") {
        $args += @("zap-baseline.py","-t",$target,"-r","/zap/wrk/$outName.html","-J","/zap/wrk/$outName.json")
    } else {
        $args += @("zap-api-scan.py","-t",$target,"-f","openapi","-r","/zap/wrk/$outName.html")
    }
    & docker @args 2>&1 | Out-Null
    $jsonPath = Join-Path $ReportsDir "$outName.json"
    $n = 0
    if (Test-Path $jsonPath) {
        try {
            $j = Get-Content $jsonPath -Raw | ConvertFrom-Json
            foreach ($site in $j.site) {
                foreach ($alert in $site.alerts) {
                    if ($alert.riskcode -ge 3) {  # 3=High, 4=Critical
                        Add-Finding -Tool "zap" -Severity "high" -Category "dast-$kind" `
                            -RuleId $alert.pluginid -File $alert.name -Line "" -Message $alert.desc -Raw $alert
                        $n++
                    }
                }
            }
        } catch { }
    }
    Set-ToolStatus "zap-$kind" "ok" $n $sw.ElapsedMilliseconds
    Write-Ok "ZAP ($kind): $n findings"
}

# --- main -----------------------------------------------------------------

$dir = (Resolve-Path $ProjectRoot).Path
$rd  = Join-Path $dir $ReportsDir
Ensure-Dir $rd

Write-Host "=== DCAP Security Scan ===" -ForegroundColor Cyan
Write-Host "Project: $dir"
Write-Host "Reports: $rd"
Write-Host "SkipDast: $SkipDast | SkipContainer: $SkipContainer | FailOnHigh: $FailOnHigh"
Write-Host ""

$startedAt = Get-Date

# 1. SAST/SCA/secrets
Run-Bandit $dir
Run-Semgrep $dir
Run-Gitleaks $dir
Run-PipAudit $dir

# 2. Container
if (-not $SkipContainer) {
    Run-TrivyImage $dir
    Run-TrivyConfig $dir
} else {
    Write-Warn "Trivy image/config skipped (-SkipContainer)"
    Set-ToolStatus "trivy-image" "skipped"
    Set-ToolStatus "trivy-config" "skipped"
}

# 3. DAST
if (-not $SkipDast) {
    Run-Zap "http://localhost:18001" "http://localhost:18001" "baseline" "zap_baseline_webui"
    Run-Zap "http://localhost:18000" "http://localhost:18000/openapi.json" "api" "zap_api_manager"
} else {
    Write-Warn "ZAP skipped (-SkipDast)"
    Set-ToolStatus "zap-baseline" "skipped"
    Set-ToolStatus "zap-api" "skipped"
}

# 4. Allowlist filter
$active = @()
$suppressed = 0
foreach ($f in $script:Findings) {
    if (Is-Allowed $f) { $suppressed++; continue }
    $active += $f
}

# 5. Summary
$summary = [pscustomobject]@{
    schema_version = "1.0"
    project        = "dcap-system"
    version        = "3.14.16"
    timestamp      = (Get-Date).ToUniversalTime().ToString("o")
    duration_sec   = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
    summary        = [pscustomobject]@{
        critical = ($active | Where-Object { $_.severity -eq "critical" }).Count
        high     = ($active | Where-Object { $_.severity -eq "high" }).Count
        medium   = ($active | Where-Object { $_.severity -eq "medium" }).Count
        low      = ($active | Where-Object { $_.severity -eq "low" }).Count
        info     = ($active | Where-Object { $_.severity -eq "info" }).Count
        total    = $active.Count
        suppressed = $suppressed
    }
    findings       = $active
    tools          = $script:ToolStatus
}

$summaryJson = Join-Path $rd "security_summary.json"
$summary | ConvertTo-Json -Depth 8 | Out-File -FilePath $summaryJson -Encoding UTF8

# 6. HTML (Dovetail-стиль, inline CSS)
$sevColor = @{
    critical = "#d67272"; high = "#d67272"; medium = "#b8974a"; low = "#4ea87a"; info = "#6798ff"
}
$rowsHtml = ($active | Sort-Object -Property @{Expression={ switch ($_.severity) { "critical" {0} "high" {1} "medium" {2} "low" {3} default {4} } }}, tool |
    ForEach-Object {
        $col = $sevColor[$_.severity] ?? "#888"
        "<tr><td style='color:$col;font-weight:600'>$($_.severity.ToUpper())</td><td>$($_.tool)</td><td>$($_.rule_id)</td><td>$([System.Web.HttpUtility]::HtmlEncode($_.file))</td><td>$($_.line)</td><td>$([System.Web.HttpUtility]::HtmlEncode($_.message))</td></tr>"
    }) -join "`n"

$toolsHtml = ($script:ToolStatus.GetEnumerator() | ForEach-Object {
    "<li><b>$($_.Key)</b>: $($_.Value.status), findings=$($_.Value.findings), $($_.Value.duration_ms) ms</li>"
}) -join "`n"

$html = @"
<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head><meta charset="UTF-8"><title>DCAP Security Report — $($summary.timestamp)</title>
<style>
:root { --ink:#0a0a0a; --snow:#fff; --danger:#d67272; --warn:#b8974a; --ok:#4ea87a; --accent:#6798ff; }
body { background: var(--ink); color: var(--snow); font-family: Inter, sans-serif; margin: 24px; }
h1 { color: var(--accent); }
.kpi { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin: 24px 0; }
.kpi-card { padding: 16px; border: 1px solid #1e1e1e; border-radius: 8px; }
.kpi-value { font-size: 32px; font-weight: 600; }
.severity-critical, .severity-high { color: var(--danger); }
.severity-medium { color: var(--warn); }
.severity-low { color: var(--ok); }
table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
th, td { border: 1px solid #1e1e1e; padding: 6px 8px; text-align: left; }
th { background: #161616; }
ul { line-height: 1.6; }
</style></head>
<body>
<h1>DCAP Security Report</h1>
<p>Проект: <b>$($summary.project)</b> · Версия: <b>$($summary.version)</b> · Дата: $($summary.timestamp) · Длительность: $($summary.duration_sec) c</p>
<div class="kpi">
  <div class="kpi-card"><div class="kpi-value severity-critical">$($summary.summary.critical)</div><div>CRITICAL</div></div>
  <div class="kpi-card"><div class="kpi-value severity-high">$($summary.summary.high)</div><div>HIGH</div></div>
  <div class="kpi-card"><div class="kpi-value severity-medium">$($summary.summary.medium)</div><div>MEDIUM</div></div>
  <div class="kpi-card"><div class="kpi-value severity-low">$($summary.summary.low)</div><div>LOW</div></div>
  <div class="kpi-card"><div class="kpi-value">$($summary.summary.suppressed)</div><div>suppressed</div></div>
</div>
<h2>Инструменты</h2>
<ul>$toolsHtml</ul>
<h2>Находки ($($summary.summary.total))</h2>
<table>
<thead><tr><th>Severity</th><th>Tool</th><th>Rule</th><th>File</th><th>Line</th><th>Message</th></tr></thead>
<tbody>$rowsHtml</tbody>
</table>
<p style="margin-top:24px;color:#888">DCAP Security Report · Generated by scripts/security_scan.ps1</p>
</body></html>
"@
$summaryHtml = Join-Path $rd "security_summary.html"
$html | Out-File -FilePath $summaryHtml -Encoding UTF8

# 7. Console output
$s = $summary.summary
Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host ("CRITICAL: {0}" -f $s.critical) -ForegroundColor $(if ($s.critical -gt 0) { "Red" } else { "Gray" })
Write-Host ("HIGH:     {0}" -f $s.high)     -ForegroundColor $(if ($s.high -gt 0) { "Red" } else { "Gray" })
Write-Host ("MEDIUM:   {0}" -f $s.medium)   -ForegroundColor Yellow
Write-Host ("LOW:      {0}" -f $s.low)      -ForegroundColor Green
Write-Host ("TOTAL:    {0} (suppressed: {1})" -f $s.total, $s.suppressed)
Write-Host ""
Write-Host "Reports: $summaryJson"
Write-Host "         $summaryHtml"

# 8. Format
switch ($Format) {
    "json" { $summary | ConvertTo-Json -Depth 8 | Write-Output }
    "html" { if (-not $Ci) { Start-Process $summaryHtml } }
    default { }
}

# 9. Exit code
if ($FailOnHigh -and (($s.critical + $s.high) -gt 0)) {
    Write-Err "Gate failed: CRITICAL+HIGH = $($s.critical + $s.high)"
    exit 1
}
exit 0