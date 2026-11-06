$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProgressPreference = 'SilentlyContinue'

function ConvertTo-UrlPart {
    param([string]$Value)
    return [System.Uri]::EscapeDataString($Value)
}

function Confirm-BambuConnectImport {
    param([string]$ExpectedName)

    try {
        Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
        Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
    }
    catch {
        return $false
    }

    $deadline = (Get-Date).AddSeconds(18)
    while ((Get-Date) -lt $deadline) {
        try {
            $condition = [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::NameProperty,
                'Import Gcode 3MF')
            $button = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
                [System.Windows.Automation.TreeScope]::Descendants, $condition)

            if ($button -and $button.Current.IsEnabled) {
                $window = $button
                for ($level = 0; $level -lt 16 -and $window; $level++) {
                    if ($window.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window) {
                        break
                    }
                    $window = [System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($window)
                }

                if (-not $window -or $window.Current.Name -notmatch '(?i)bambu.?connect') {
                    Start-Sleep -Milliseconds 750
                    continue
                }

                $fileFound = $false
                $elements = $window.FindAll(
                    [System.Windows.Automation.TreeScope]::Descendants,
                    [System.Windows.Automation.Condition]::TrueCondition)
                foreach ($element in $elements) {
                    if ($element.Current.Name -and $element.Current.Name.Contains($ExpectedName)) {
                        $fileFound = $true
                        break
                    }
                }

                if ($fileFound) {
                    $invoke = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                    $invoke.Invoke()
                    return $true
                }
            }
        }
        catch {
            # Keep waiting; Bambu Connect may still be opening its import dialog.
        }
        Start-Sleep -Milliseconds 750
    }

    return $false
}

function New-BridgeToken {
    $code = Read-Host 'Enter the one-time code from Admin > Pont Bambu Connect'
    $pairBody = @{ code = $code.Trim(); device_name = $env:COMPUTERNAME } | ConvertTo-Json -Compress
    $pair = Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/pair" -ContentType 'application/json' -Body $pairBody
    if (-not $pair.ok -or -not $pair.token) {
        throw 'Pairing failed. Generate a fresh code on the site and run the bridge again.'
    }
    $newToken = [string]$pair.token
    $secure = ConvertTo-SecureString $newToken -AsPlainText -Force
    $encrypted = ConvertFrom-SecureString $secure
    Set-Content -LiteralPath $tokenFile -Value $encrypted -Encoding ascii
    Set-Content -LiteralPath $siteFile -Value $site -Encoding ascii
    return $newToken
}

$site = 'https://fjord-render-apercu-20261104.onrender.com'
$root = Join-Path $env:LOCALAPPDATA 'LesImpressionsDuFjord\BambuConnectBridge'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$tokenFile = Join-Path $root 'token.dpapi'
$siteFile = Join-Path $root 'site.txt'
$token = ''

if ((Test-Path -LiteralPath $tokenFile) -and (Test-Path -LiteralPath $siteFile)) {
    $savedSite = (Get-Content -LiteralPath $siteFile -Raw).Trim()
    if ($savedSite -eq $site) {
        try {
            $encryptedToken = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
            $secureToken = ConvertTo-SecureString $encryptedToken -ErrorAction Stop
            $tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
            $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
        }
        catch {
            $token = ''
            Remove-Item -LiteralPath $tokenFile -Force -ErrorAction SilentlyContinue
        }
    }
}

if ([string]::IsNullOrWhiteSpace($token)) {
    $token = New-BridgeToken
}

$headers = @{ Authorization = "Bearer $token" }
Write-Host 'Bridge helper started. Checking server authorization...' -ForegroundColor Green
Write-Host 'When a file arrives, confirm the printer and print in Bambu Connect.'

while ($true) {
    try {
        $response = Invoke-RestMethod -Method Get -Uri "$site/api/fjord-print-bridge/next" -Headers $headers -TimeoutSec 20
        $job = $response.job
        if (-not $job) {
            Start-Sleep -Seconds 5
            continue
        }

        $seenPath = Join-Path $root 'last-job.txt'
        $alreadyOpened = $false
        if (Test-Path -LiteralPath $seenPath) {
            $lastJob = (Get-Content -LiteralPath $seenPath -Raw).Trim()
            if ($lastJob -eq [string]$job.id) { $alreadyOpened = $true }
        }
        if ($alreadyOpened) {
            Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/ack/$($job.id)" -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 20 | Out-Null
            Start-Sleep -Seconds 5
            continue
        }

        $fileName = [System.IO.Path]::GetRandomFileName() + '.gcode.3mf'
        $filePath = Join-Path -Path $root -ChildPath $fileName
        Invoke-WebRequest -Method Get -Uri "$site/api/fjord-print-bridge/file/$($job.id)" -Headers $headers -OutFile $filePath -TimeoutSec 120
        if ((Get-Item -LiteralPath $filePath).Length -lt 100) {
            throw 'The downloaded 3MF is incomplete.'
        }

        $connectName = [string]$job.file_name
        if ($connectName -notmatch '(?i)\.gcode\.3mf$') {
            $connectName = $connectName -replace '(?i)\.3mf$', ''
            $connectName = $connectName + '.gcode.3mf'
        }
        $encodedPath = ConvertTo-UrlPart $filePath
        $encodedName = ConvertTo-UrlPart $connectName
        $separator = [string][char]38
        $uri = 'bambu-connect://import-file?path=' + $encodedPath
        $uri = $uri + $separator + 'name=' + $encodedName
        $uri = $uri + $separator + 'version=1.0.0'
        Start-Process -FilePath $uri -ErrorAction Stop | Out-Null
        $importConfirmed = Confirm-BambuConnectImport -ExpectedName $connectName
        Set-Content -LiteralPath $seenPath -Value ([string]$job.id) -Encoding ascii
        Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/ack/$($job.id)" -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 20 | Out-Null
        if ($importConfirmed) {
            Write-Host 'File import confirmed automatically. Select the X2D and explicitly confirm the print in Bambu Connect.' -ForegroundColor Cyan
        }
        else {
            Write-Host 'Click Import Gcode 3MF manually, then select the X2D and explicitly confirm the print in Bambu Connect.' -ForegroundColor Yellow
        }
    }
    catch {
        $errorMessage = $_.Exception.Message
        if ($errorMessage -match '401|Unauthorized') {
            Write-Host 'Render refused the saved token. Pair this PC again with a fresh one-time code.' -ForegroundColor Yellow
            Remove-Item -LiteralPath $tokenFile -Force -ErrorAction SilentlyContinue
            $token = New-BridgeToken
            $headers = @{ Authorization = "Bearer $token" }
            Write-Host 'Pairing renewed. Checking the bridge again...' -ForegroundColor Green
            continue
        }
        Write-Host ("Bridge error: {0}" -f $errorMessage) -ForegroundColor Red
        Start-Sleep -Seconds 10
    }
}
