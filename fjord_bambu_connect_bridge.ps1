$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProgressPreference = 'SilentlyContinue'

function ConvertTo-UrlPart([string]$Value) {
    return [System.Uri]::EscapeDataString($Value)
}

$defaultSite = 'https://fjord-render-apercu-20261104.onrender.com'
$site = $defaultSite
$root = Join-Path $env:LOCALAPPDATA 'LesImpressionsDuFjord\BambuConnectBridge'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$tokenFile = Join-Path $root 'token.dpapi'
 $siteFile = Join-Path $root 'site.txt'
function New-BridgeToken {
    $code = Read-Host 'Code à usage unique généré dans Admin > Pont Bambu Connect'
    $pairBody = @{ code = $code.Trim(); device_name = $env:COMPUTERNAME } | ConvertTo-Json -Compress
    $pair = Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/pair" -ContentType 'application/json' -Body $pairBody
    if (-not $pair.ok -or -not $pair.token) { throw 'Association refusée. Génère un nouveau code dans le site et réessaie.' }
    $secure = ConvertTo-SecureString $pair.token -AsPlainText -Force
    Set-Content -LiteralPath $tokenFile -Value (ConvertFrom-SecureString $secure) -Encoding ascii
    Set-Content -LiteralPath $siteFile -Value $site -Encoding ascii
    return [string]$pair.token
}

$savedSite = if (Test-Path -LiteralPath $siteFile) { (Get-Content -LiteralPath $siteFile -Raw).Trim() } else { '' }
$token = $null
if ((Test-Path -LiteralPath $tokenFile) -and ($savedSite -eq $site)) {
    try {
        $encryptedToken = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
        if ([string]::IsNullOrWhiteSpace($encryptedToken)) { throw 'Jeton local vide.' }
        $secure = ConvertTo-SecureString $encryptedToken -ErrorAction Stop
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
        if ([string]::IsNullOrWhiteSpace($token)) { throw 'Jeton local invalide.' }
    } catch {
        Write-Host 'Le jeton enregistré sur ce PC est illisible; une nouvelle association est nécessaire.' -ForegroundColor Yellow
        Remove-Item -LiteralPath $tokenFile -Force -ErrorAction SilentlyContinue
        $token = New-BridgeToken
    }
} else {
    $token = New-BridgeToken
}
$headers = @{ Authorization = "Bearer $token" }
Write-Host 'Pont associé. Garde cette fenêtre PowerShell ouverte.' -ForegroundColor Green
Write-Host 'Lorsqu’un travail arrive, Bambu Connect s’ouvrira. Vérifie la X2D et confirme dans l’application.'

while ($true) {
    try {
        $response = Invoke-RestMethod -Method Get -Uri "$site/api/fjord-print-bridge/next" -Headers $headers -TimeoutSec 20
        $job = $response.job
        if (-not $job) { Start-Sleep -Seconds 5; continue }

        $seenPath = Join-Path $root 'last-job.txt'
        $alreadyOpened = (Test-Path $seenPath) -and ((Get-Content -LiteralPath $seenPath -Raw).Trim() -eq [string]$job.id)
        if ($alreadyOpened) {
            try { Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/ack/$($job.id)" -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 20 | Out-Null } catch { }
            Start-Sleep -Seconds 5
            continue
        }

        $randomName = [System.IO.Path]::GetRandomFileName()
        $fileName = "{0}.gcode.3mf" -f $randomName
        $filePath = Join-Path -Path $root -ChildPath $fileName
        Invoke-WebRequest -Method Get -Uri "$site/api/fjord-print-bridge/file/$($job.id)" -Headers $headers -OutFile $filePath -TimeoutSec 120
        if ((Get-Item -LiteralPath $filePath).Length -lt 100) { throw 'Le 3MF téléchargé est incomplet.' }

        $connectName = [string]$job.file_name
        if ($connectName -notmatch '(?i)\.gcode\.3mf$') {
            $connectName = $connectName -replace '(?i)\.3mf$', ''
            $connectName += '.gcode.3mf'
        }
        $encodedPath = ConvertTo-UrlPart $filePath
        $encodedName = ConvertTo-UrlPart $connectName
        $uri = "bambu-connect://import-file?path=$encodedPath&name=$encodedName&version=1.0.0"
        Start-Process $uri
        Set-Content -LiteralPath $seenPath -Value ([string]$job.id) -Encoding ascii
        Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/ack/$($job.id)" -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 20 | Out-Null
        Write-Host "Fichier remis à Bambu Connect : $($job.file_name)" -ForegroundColor Cyan
        Write-Host 'Confirme l’imprimante, le matériau et le lancement dans Bambu Connect.' -ForegroundColor Yellow
    }
    catch {
        $detail = $_.Exception.Message
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
        $statusCode = 0
        try { $statusCode = [int]$_.Exception.Response.StatusCode } catch { }
        if ($statusCode -eq 401) {
            Write-Host 'Le serveur a refusé le jeton enregistré. Génère un nouveau code sur la page Pont Bambu Connect; cette fenêtre PowerShell va te le demander.' -ForegroundColor Yellow
            Remove-Item -LiteralPath $tokenFile -Force -ErrorAction SilentlyContinue
            $token = New-BridgeToken
            $headers = @{ Authorization = "Bearer $token" }
            Write-Host 'Nouvelle association réussie. Reprise de la surveillance.' -ForegroundColor Green
            continue
        }
        Write-Host ("Erreur du pont : {0}" -f $detail) -ForegroundColor Red
        Write-Host 'Nouvelle tentative dans 10 secondes.' -ForegroundColor DarkYellow
        Start-Sleep -Seconds 10
    }
}
