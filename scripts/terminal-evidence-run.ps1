param([Parameter(Mandatory = $true)] [string] $Id)

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
try { [Console]::SetWindowSize(140, 42) } catch { }
$host.UI.RawUI.WindowTitle = "Evidence $Id - live terminal capture"
$tmp = Join-Path $env:TEMP 'opencode'
$sentinel = Join-Path $tmp "terminal_$Id.done"
Clear-Host

function Show([string] $command) {
  Write-Host ''
  Write-Host "PS C:\Users\ASUS\Desktop\kong-project> $command" -ForegroundColor Cyan
}

function Finish([bool] $ok) {
  $verdict = if ($ok) { 'PASS' } else { 'FAIL' }
  Write-Host ''
  if ($ok) { Write-Host "RESULT: $verdict" -ForegroundColor Green }
  else { Write-Host "RESULT: $verdict" -ForegroundColor Red }
  "RESULT: $verdict" | Set-Content $sentinel -Encoding UTF8
}

function HeaderValue($headers, [string] $name) {
  $line = $headers | Where-Object { $_ -match ('^' + [regex]::Escape($name) + ':') } | Select-Object -First 1
  if ($null -eq $line) { return '-' }
  return ($line -replace '^[^:]*: ?', '').Trim()
}

function StatusLine($headers) {
  $line = $headers | Where-Object { $_ -match '^HTTP/' } | Select-Object -Last 1
  if ($null -eq $line) { return '-' }
  return $line.Trim()
}

function Wait-Kong {
  for ($i = 0; $i -lt 40; $i++) {
    $ready = curl.exe -s -o NUL -w '%{http_code}' --max-time 2 -H 'apikey: premium-demo-key' http://127.0.0.1:8000/api/accounts/health
    if ($ready -eq '200') { Start-Sleep -Seconds 2; return }
    Start-Sleep -Seconds 1
  }
}

function TargetHealthLine {
  $health = Invoke-RestMethod 'http://127.0.0.1:8001/upstreams/accounts-upstream/health'
  return (($health.data | Sort-Object target | ForEach-Object { "$($_.target)=$($_.health)" }) -join ' ')
}

switch ($Id) {
  '01' {
    Show 'docker compose ps'
    docker compose ps
    Show 'docker compose exec -T kong kong version'
    $version = docker compose exec -T kong kong version
    $version
    Finish ([bool]($version -match '3\.9\.1'))
  }

  '02' {
    Show 'python scripts/fragment_lab.py parse'
    $parsed = python scripts/fragment_lab.py parse
    $parsed
    Show 'Get-Content kong/kong.yml -TotalCount 18'
    Get-Content kong\kong.yml -TotalCount 18
    Finish ([bool]($parsed -match 'parse successful'))
  }

  '03' {
    $checks = @(
      @{ Method = 'GET'; Url = 'http://127.0.0.1:8001/services'; Expected = '200' },
      @{ Method = 'GET'; Url = 'http://127.0.0.1:8001/routes'; Expected = '200' },
      @{ Method = 'GET'; Url = 'http://127.0.0.1:8001/upstreams'; Expected = '200' },
      @{ Method = 'GET'; Url = 'http://127.0.0.1:8001/upstreams/accounts-upstream/health'; Expected = '200' },
      @{ Method = 'GET'; Url = 'http://127.0.0.1:8100/status'; Expected = '200' },
      @{ Method = 'DELETE'; Url = 'http://127.0.0.1:8001/services/mock-upstream'; Expected = '405' }
    )
    $ok = $true
    foreach ($check in $checks) {
      Show "curl.exe -s -o NUL -w `"HTTP %{http_code}`" -X $($check.Method) $($check.Url)"
      $code = curl.exe -s -o NUL -w '%{http_code}' -X $check.Method $check.Url
      Write-Host "HTTP $code"
      if ($code -ne $check.Expected) { $ok = $false }
      if ($check.Method -eq 'GET') {
        $sample = curl.exe -s $check.Url
        if ($sample.Length -gt 150) { $sample = $sample.Substring(0, 150) + '...' }
        Write-Host "body: $sample"
      }
    }
    Finish $ok
  }

  '08' {
    $headers = @{ apikey = 'premium-demo-key' }
    Show 'curl.exe -s -D - -o NUL -H "apikey: premium-demo-key" http://127.0.0.1:8000/api/accounts/health'
    $h = curl.exe -s -D - -o NUL -H 'apikey: premium-demo-key' http://127.0.0.1:8000/api/accounts/health
    Write-Host (StatusLine $h)
    foreach ($name in @('X-Served-By', 'Kong-Request-ID', 'X-Consumer-Username', 'Access-Control-Expose-Headers')) {
      Write-Host "$name : $(HeaderValue $h $name)"
    }
    Show '1..6 | ForEach-Object { curl.exe -s -D - -o NUL -H "apikey: premium-demo-key" ... }'
    $served = @()
    1..6 | ForEach-Object {
      $hh = curl.exe -s -D - -o NUL -H 'apikey: premium-demo-key' http://127.0.0.1:8000/api/accounts/health
      $served += HeaderValue $hh 'X-Served-By'
    }
    Write-Host ('X-Served-By: ' + ($served -join ', '))
    Show 'curl.exe -s -D - -o NUL -X OPTIONS -H "Origin: http://localhost:3000" ...'
    $pre = curl.exe -s -D - -o NUL -X OPTIONS -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: apikey,content-type' http://127.0.0.1:8000/api/accounts
    Write-Host (StatusLine $pre)
    foreach ($name in @('Access-Control-Allow-Origin', 'Access-Control-Allow-Headers', 'Access-Control-Allow-Methods', 'Access-Control-Max-Age')) {
      Write-Host "$name : $(HeaderValue $pre $name)"
    }
    Show 'POST 2000-byte body to accounts and advisor'
    $body = '{"note":"' + ('x' * 2000) + '"}'
    $a = curl.exe -s -o NUL -w '%{http_code}' -X POST -H 'apikey: premium-demo-key' -H 'Content-Type: application/json' -d $body http://127.0.0.1:8000/api/accounts
    $b = curl.exe -s -o NUL -w '%{http_code}' -X POST -H 'apikey: premium-demo-key' -H 'Content-Type: application/json' -d $body http://127.0.0.1:8000/api/advisor/analyze
    Write-Host "accounts HTTP $a | advisor HTTP $b"
    Finish ([bool]((($served | Where-Object { $_ -match 'accounts-' } | Measure-Object).Count -eq 6) -and $a -eq '413' -and $b -eq '413'))
  }

  '19' {
    Show 'python scripts/make_jwt.py --iss fintech-free'
    $freeJwt = python scripts/make_jwt.py --iss fintech-free
    Write-Host $freeJwt
    Show 'python scripts/make_jwt.py --iss fintech-premium'
    $premiumJwt = python scripts/make_jwt.py --iss fintech-premium
    Write-Host $premiumJwt
    Show 'python scripts/make_jwt.py --iss fintech-free --bad-signature'
    $badJwt = python scripts/make_jwt.py --iss fintech-free --bad-signature
    Write-Host $badJwt
    Show 'auth matrix with curl.exe'
    $matrix = @(
      @{ Name = 'accounts, no apikey'; Url = 'http://127.0.0.1:8000/api/accounts/health'; Headers = @{}; Expected = '401' },
      @{ Name = 'accounts, free key'; Url = 'http://127.0.0.1:8000/api/accounts/health'; Headers = @{ apikey = 'free-demo-key' }; Expected = '200' },
      @{ Name = 'accounts, bad key'; Url = 'http://127.0.0.1:8000/api/accounts/health'; Headers = @{ apikey = 'wrong-key' }; Expected = '401' },
      @{ Name = 'advisor, no apikey'; Url = 'http://127.0.0.1:8000/api/advisor/health'; Headers = @{}; Expected = '401' },
      @{ Name = 'advisor, premium key'; Url = 'http://127.0.0.1:8000/api/advisor/health'; Headers = @{ apikey = 'premium-demo-key' }; Expected = '200' },
      @{ Name = 'payments, no JWT'; Url = 'http://127.0.0.1:8000/api/payments/health'; Headers = @{}; Expected = '401' },
      @{ Name = 'payments, free JWT'; Url = 'http://127.0.0.1:8000/api/payments/health'; Headers = @{ Authorization = "Bearer $freeJwt" }; Expected = '200' },
      @{ Name = 'payments, premium JWT'; Url = 'http://127.0.0.1:8000/api/payments/health'; Headers = @{ Authorization = "Bearer $premiumJwt" }; Expected = '200' },
      @{ Name = 'payments, tampered JWT'; Url = 'http://127.0.0.1:8000/api/payments/health'; Headers = @{ Authorization = "Bearer $badJwt" }; Expected = '401' }
    )
    $ok = $true
    foreach ($row in $matrix) {
      $args = @('-s', '-o', 'NUL', '-w', '%{http_code}')
      foreach ($key in $row.Headers.Keys) { $args += @('-H', "$key`: $($row.Headers[$key])") }
      $args += $row.Url
      $code = curl.exe @args
      Write-Host ('{0,-26} HTTP {1}' -f $row.Name, $code)
      if ($code -ne $row.Expected) { $ok = $false }
    }
    Show 'Invoke-RestMethod http://127.0.0.1:8001/plugins | Group-Object name'
    $plugins = (Invoke-RestMethod http://127.0.0.1:8001/plugins).data | Group-Object name | Sort-Object Name
    $plugins | ForEach-Object { Write-Host ('{0,-24} {1}' -f $_.Name, $_.Count) }
    Finish $ok
  }

  '20' {
    Show 'docker compose restart kong'
    docker compose restart kong 2>&1 | Out-Null
    Wait-Kong
    Show 'python tests/fragments/verify_token_bucket.py --url http://127.0.0.1:8000 --count 5'
    $token = python tests/fragments/verify_token_bucket.py --url http://127.0.0.1:8000 --count 5
    $token
    Show 'docker compose restart kong  # reset G3 fixed window'
    docker compose restart kong 2>&1 | Out-Null
    Wait-Kong
    Show '1..11 | free-demo-key GET /api/accounts/health'
    $free = @()
    $last = $null
    1..11 | ForEach-Object {
      $hh = curl.exe -s -D - -o NUL -H 'apikey: free-demo-key' http://127.0.0.1:8000/api/accounts/health
      $code = (((StatusLine $hh) -replace 'HTTP/1.1 ', '') -split ' ')[0]
      $free += $code
      if ($_ -eq 11) { $last = $hh }
    }
    Write-Host ('free requests 1-11: ' + ($free -join ','))
    Write-Host ('X-RateLimit-Limit-Minute on 11th: ' + (HeaderValue $last 'X-RateLimit-Limit-Minute'))
    Write-Host ('Retry-After on 11th: ' + (HeaderValue $last 'Retry-After'))
    Show '1..12 | premium-demo-key GET /api/accounts/health'
    $premium = @()
    1..12 | ForEach-Object {
      $hh = curl.exe -s -D - -o NUL -H 'apikey: premium-demo-key' http://127.0.0.1:8000/api/accounts/health
      $premium += ((((StatusLine $hh) -replace 'HTTP/1.1 ', '') -split ' ')[0])
    }
    Write-Host ('premium 12 requests: ' + ($premium -join ','))
    Show 'curl.exe --cacert certs\localhost.crt https://localhost:8443/api/accounts/health'
    $https = curl.exe -s -o NUL -w '%{http_code}' --cacert certs\localhost.crt https://localhost:8443/api/accounts/health -H 'apikey: premium-demo-key'
    Write-Host "HTTP $https"
    Show '& "C:\Program Files\OpenSSL-Win64\bin\openssl.exe" s_client -connect localhost:8443 -servername localhost -CAfile certs\localhost.crt -brief'
    $ossl = & 'C:\Program Files\OpenSSL-Win64\bin\openssl.exe' s_client -connect localhost:8443 -servername localhost -CAfile certs\localhost.crt -brief 2>&1
    $ossl | Where-Object { $_ -match 'Protocol version|Peer certificate|Verification' } | ForEach-Object { Write-Host ([string]$_).Trim() }
    $ok = ([bool]($token -match 'burst parity: PASS') -and ($free -join ',') -eq '200,200,200,200,200,200,200,200,200,200,429' -and (($premium | Where-Object { $_ -ne '200' } | Measure-Object).Count -eq 0) -and $https -eq '200' -and [bool]($ossl -match 'Verification: OK'))
    Finish ([bool]$ok)
  }

  '21' {
    Show 'curl.exe -s http://127.0.0.1:8100/metrics | Select-String "^kong_"'
    $metrics = curl.exe -s http://127.0.0.1:8100/metrics
    $samples = @()
    foreach ($pattern in @('^kong_http_requests_total', '^kong_bandwidth_bytes', '^kong_kong_latency_ms_bucket')) {
      $sample = $metrics | Where-Object { $_ -match $pattern } | Select-Object -First 1
      if ($sample) {
        $s = [string]$sample
        if ($s.Length -gt 120) { $s = $s.Substring(0, 120) + '...' }
        $samples += $s
        Write-Host $s
      }
    }
    Show 'curl.exe -s -H "apikey: premium-demo-key" -H "X-Debug: remove-me" http://127.0.0.1:8000/api/accounts/health'
    curl.exe -s -o NUL -H 'apikey: premium-demo-key' -H 'X-Debug: remove-me' http://127.0.0.1:8000/api/accounts/health
    Show 'docker compose exec -T kong sh -lc "tail -n 1 /var/log/kong/access.json" | python c2_check.py'
    $c2 = Join-Path $tmp 'c2_check.py'
    if (-not (Test-Path $c2)) {
      @'
import json
import sys

d = json.loads(sys.stdin.read())
h = {str(k).lower(): v for k, v in d.get("request", {}).get("headers", {}).items()}
r = d.get("request", {})
present = all(
    ["client_ip" in d, "method" in r, "uri" in r,
     "status" in d.get("response", {}), "latencies" in d,
     "started_at" in d]
)
print("C2 0.1.1 required fields: " + ("PRESENT" if present else "MISSING"))
print("X-Gateway forwarded: " + str(h.get("x-gateway", "-")))
print("X-Debug removed: " + ("YES" if "x-debug" not in h else "NO"))
'@ | Set-Content $c2 -Encoding UTF8
    }
    $logline = docker compose exec -T kong sh -lc 'tail -n 1 /var/log/kong/access.json'
    $logline | python $c2
    Show 'curl.exe -X POST --data-binary @fixtures\alerts.json http://127.0.0.1:5678/webhook/alertmanager'
    $hook = curl.exe -s -o NUL -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data-binary '@fixtures\alerts.json' http://127.0.0.1:5678/webhook/alertmanager
    Write-Host "webhook HTTP $hook"
    Start-Sleep -Seconds 3
    Show 'docker logs --tail 1 notify-sink'
    $notify = docker logs --tail 1 notify-sink 2>&1 | ForEach-Object { ([string]$_).Trim() }
    $notify
    Finish ([bool]($samples.Count -eq 3 -and $hook -eq '200' -and ($notify -match 'NOTIFICATION').Count -gt 0))
  }

  '22' {
    $headers = @{ apikey = 'premium-demo-key' }
    $analyze = 'http://127.0.0.1:8000/api/advisor/analyze'
    Wait-Kong

    Show '.\advisor\.venv\Scripts\python.exe -m pytest advisor -v'
    $tests = & .\advisor\.venv\Scripts\python.exe -m pytest advisor -v 2>&1 | Select-Object -Last 7
    $tests | ForEach-Object { Write-Host $_ }
    $testsOk = [bool](($tests -join "`n") -match '15 passed')

    Show 'Invoke-RestMethod POST /api/advisor/analyze {"question":"How many requests were logged?"}'
    $overview = Invoke-RestMethod -Method Post -Uri $analyze -Headers $headers -ContentType 'application/json' -Body '{"question":"How many requests were logged?"}'
    $overviewCitations = ($overview.citations | Select-Object -First 3) -join ', '
    if ($overview.citations.Count -gt 3) { $overviewCitations += " (+$($overview.citations.Count - 3) more)" }
    Write-Host ("summary : " + $overview.summary)
    Write-Host ("verified: " + $overview.verified)
    Write-Host ("requests_total: " + $overview.stats.requests_total)
    Write-Host ("citations: " + $overviewCitations)
    Write-Host ("tools: " + (($overview.tool_trace | ForEach-Object { $_.tool }) -join ' -> '))

    Show 'Invoke-RestMethod POST /api/advisor/analyze {"question":"Why were there 429s?"}'
    $spike = Invoke-RestMethod -Method Post -Uri $analyze -Headers $headers -ContentType 'application/json' -Body '{"question":"Why were there 429s?"}'
    $spikeCitations = ($spike.citations | Select-Object -First 3) -join ', '
    if ($spike.citations.Count -gt 3) { $spikeCitations += " (+$($spike.citations.Count - 3) more)" }
    Write-Host ("summary : " + $spike.summary)
    Write-Host ("verified: " + $spike.verified)
    Write-Host ("rate_limited_total: " + $spike.stats.rate_limited_total)
    Write-Host ("citations: " + $spikeCitations)

    Show 'Invoke-RestMethod POST /api/advisor/analyze {"question":"Which client IPs caused errors?"}'
    $ips = Invoke-RestMethod -Method Post -Uri $analyze -Headers $headers -ContentType 'application/json' -Body '{"question":"Which client IPs caused errors?"}'
    Write-Host ("summary : " + $ips.summary)
    Write-Host ("verified: " + $ips.verified)
    Write-Host ("distinct_client_ips: " + $ips.stats.distinct_client_ips)
    Write-Host ("top_client_ip: " + $ips.stats.top_client_ip)

    Show 'Invoke-RestMethod POST /api/advisor/analyze {"question":"Why were there 503s?"}'
    $unsupported = Invoke-RestMethod -Method Post -Uri $analyze -Headers $headers -ContentType 'application/json' -Body '{"question":"Why were there 503s?"}'
    Write-Host ("summary : " + $unsupported.summary)
    Write-Host ("verified: " + $unsupported.verified)
    Write-Host ("citations: " + $unsupported.citations.Count)
    Write-Host ("last tool: " + $unsupported.tool_trace[-1].tool)

    Show 'Invoke-RestMethod GET /api/advisor/stats/requests_total'
    $endpoint = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/advisor/stats/requests_total' -Headers $headers
    Write-Host ("stats endpoint: " + ($endpoint | ConvertTo-Json -Compress))

    $ok = $testsOk -and $overview.verified -and $spike.verified -and $ips.verified `
      -and ($ips.stats.distinct_client_ips -gt 0) `
      -and ($unsupported.summary -eq 'No verified data') `
      -and ($unsupported.verified -eq $false) `
      -and ($unsupported.citations.Count -eq 0) `
      -and ($overview.tool_trace[-1].tool -eq 'verify_answer') `
      -and ($endpoint.requests_total -gt 0)
    Finish $ok
  }

  '23' {
    Wait-Kong

    Show 'python scripts/verify_metrics_contract.py'
    $verify = python scripts/verify_metrics_contract.py 2>&1
    $verify | ForEach-Object { Write-Host $_ }

    Show 'promtool check config monitoring/prometheus.yml (prom/prometheus:v3.16.0)'
    $promCfg = docker run --rm --entrypoint promtool `
      -v "${PWD}/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro" `
      -v "${PWD}/monitoring/rules:/etc/prometheus/rules:ro" `
      prom/prometheus:v3.16.0 check config /etc/prometheus/prometheus.yml 2>&1
    $promCfg | Where-Object { $_ -match 'SUCCESS' } | ForEach-Object { Write-Host $_ }

    Show 'promtool check rules monitoring/rules/alerts.yml'
    $promRules = docker run --rm --entrypoint promtool `
      -v "${PWD}/monitoring/rules:/etc/prometheus/rules:ro" `
      prom/prometheus:v3.16.0 check rules /etc/prometheus/rules/alerts.yml 2>&1
    $promRules | Where-Object { $_ -match 'SUCCESS' } | ForEach-Object { Write-Host $_ }

    Show 'Invoke-RestMethod http://127.0.0.1:9090/api/v1/targets'
    $targets = Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/targets'
    $target = $targets.data.activeTargets | Where-Object { $_.labels.job -eq 'kong' } | Select-Object -First 1
    Write-Host ("kong target: health=" + $target.health + " lastError='" + $target.lastError + "'")

    Show 'Invoke-RestMethod http://127.0.0.1:9090/api/v1/rules'
    $rules = Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/rules'
    $ruleCount = 0
    $rules.data.groups | ForEach-Object { $ruleCount += $_.rules.Count }
    Write-Host ("rule groups: " + (($rules.data.groups | ForEach-Object { $_.name + '=' + $_.rules.Count }) -join ', '))

    Show 'Invoke-RestMethod http://127.0.0.1:9090/api/v1/alertmanagers'
    $ams = Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/alertmanagers'
    $amUrls = @($ams.data.activeAlertmanagers | ForEach-Object { $_.url })
    Write-Host ("active alertmanagers: " + ($amUrls -join ', '))

    $successCount = (@($promCfg) + @($promRules) | Where-Object { $_ -match 'SUCCESS' } | Measure-Object).Count
    $ok = (($verify -join "`n") -match 'M1 RESULT: PASS') `
      -and ($successCount -ge 4) `
      -and ($target.health -eq 'up') `
      -and ($ruleCount -eq 3) `
      -and (($amUrls -join ',') -match 'alertmanager:9093')
    Finish $ok
  }

  '24' {
    Wait-Kong

    Show 'python scripts/fragment_lab.py parse'
    $parsed = python scripts/fragment_lab.py parse 2>&1
    $parsed | Where-Object { $_ -match 'parse successful' } | ForEach-Object { Write-Host $_ }

    $hcText = Get-Content kong\kong.yml -Raw
    $activeCount = [regex]::Matches($hcText, 'active:').Count
    $passiveCount = [regex]::Matches($hcText, 'passive:').Count
    $pathCount = [regex]::Matches($hcText, 'http_path: /health').Count
    Show 'Select-String kong/kong.yml (healthchecks)'
    Write-Host ("active=$activeCount passive=$passiveCount http_path=/health=$pathCount")

    Show 'GET /upstreams/accounts-upstream/health (baseline)'
    $baseline = TargetHealthLine
    Write-Host $baseline

    Show 'docker compose --profile load run --rm k6 (2 VUs, 45s)'
    $job = Start-Job -ScriptBlock {
      Set-Location 'C:\Users\ASUS\Desktop\kong-project'
      docker compose --profile load run --rm k6 2>&1
    }
    Start-Sleep -Seconds 6

    Show 'docker compose --profile core stop accounts-2'
    docker compose --profile core stop accounts-2 2>&1 | Out-Null
    Start-Sleep -Seconds 14

    Show 'GET /upstreams/accounts-upstream/health (replica offline)'
    $offline = TargetHealthLine
    Write-Host $offline

    Show 'docker compose --profile core start accounts-2'
    docker compose --profile core start accounts-2 2>&1 | Out-Null
    Start-Sleep -Seconds 14

    Show 'GET /upstreams/accounts-upstream/health (recovered)'
    $recovered = TargetHealthLine
    Write-Host $recovered

    $k6 = Receive-Job $job -Wait
    Remove-Job $job
    $k6Text = ($k6 -join "`n")
    $checks = $k6 | Where-Object { $_ -match 'checks_succeeded' } | Select-Object -First 1
    $failed = $k6 | Where-Object { $_ -match 'http_req_failed' } | Select-Object -Last 1
    $served = $k6 | Where-Object { $_ -match 'served_by' } | Select-Object -Last 1
    if ($null -ne $checks) { Write-Host $checks.Trim() }
    if ($null -ne $failed) { Write-Host $failed.Trim() }
    if ($null -ne $served) { Write-Host $served.Trim() }

    Show 'docker compose --profile load run --rm locust -t 10s --only-summary'
    $locust = docker compose --profile load run --rm locust `
      -f /mnt/locust/locustfile.py --headless --host http://kong:8000 `
      -u 2 -r 1 -t 10s --only-summary 2>&1
    $locustText = ($locust -join ' ')
    $locustReqs = 0
    if ($locustText -match 'Aggregated\s+(\d+)\s+0\(0\.00%\)') {
      $locustReqs = [int]$matches[1]
    }
    $distribution = $locust | Where-Object { $_ -match 'X-Served-By distribution' } | Select-Object -First 1
    Write-Host ("Locust: $locustReqs reqs, 0 fails (0.00%)")
    if ($null -ne $distribution) { Write-Host $distribution.Trim() }

    $ok = (($parsed -join "`n") -match 'parse successful') `
      -and ($activeCount -eq 3) -and ($passiveCount -eq 3) -and ($pathCount -eq 3) `
      -and ($baseline -match 'accounts-1[^=]*=HEALTHY') -and ($baseline -match 'accounts-2[^=]*=HEALTHY') `
      -and ($offline -match 'accounts-2[^=]*=UNHEALTHY') -and ($offline -match 'accounts-1[^=]*=HEALTHY') `
      -and ($recovered -match 'accounts-1[^=]*=HEALTHY') -and ($recovered -match 'accounts-2[^=]*=HEALTHY') `
      -and ($k6Text -match 'checks_succeeded\.+: 100\.00%') `
      -and ($k6Text -match 'http_req_failed\.+: 0\.00%') `
      -and ($k6Text -match 'served_by\.+: [1-9]\d*') `
      -and ($locustReqs -gt 0) `
      -and ($null -ne $distribution) `
      -and ($distribution -match 'accounts-1') -and ($distribution -match 'accounts-2')
    Finish $ok
  }

  default {
    Write-Host "unknown evidence id $Id" -ForegroundColor Red
    Finish $false
  }
}
