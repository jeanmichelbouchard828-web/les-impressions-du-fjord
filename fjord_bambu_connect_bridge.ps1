$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function ConvertTo-UrlPart([string]$Value) {
    return [System.Uri]::EscapeDataString($Value)
}

$site = (Read-Host 'Adresse Render du site (ex. https://fjord-render-apercu-20261104.onrender.com)').Trim().TrimEnd('/')
if ($site -notmatch '^https://[A-Za-z0-9.-]+(?::[0-9]+)?$') { throw 'Adresse HTTPS invalide.' }
$root = Join-Path $env:LOCALAPPDATA 'LesImpressionsDuFjord\BambuConnectBridge'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$tokenFile = Join-Path $root 'token.dpapi'
 $siteFile = Join-Path $root 'site.txt'
$savedSite = if (Test-Path -LiteralPath $siteFile) { (Get-Content -LiteralPath $siteFile -Raw).Trim() } else { '' }
if ((Test-Path -LiteralPath $tokenFile) -and ($savedSite -eq $site)) {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $tokenFile -Raw)
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
} else {
    $code = Read-Host 'Code à usage unique généré dans Admin > Pont Bambu Connect'
    $pairBody = @{ code = $code.Trim(); device_name = $env:COMPUTERNAME } | ConvertTo-Json -Compress
    $pair = Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/pair" -ContentType 'application/json' -Body $pairBody
    if (-not $pair.ok -or -not $pair.token) { throw 'Association refusée. Génère un nouveau code dans le site et réessaie.' }
    $secure = ConvertTo-SecureString $pair.token -AsPlainText -Force
    Set-Content -LiteralPath $tokenFile -Value (ConvertFrom-SecureString $secure) -Encoding ascii
    Set-Content -LiteralPath $siteFile -Value $site -Encoding ascii
    $token = $pair.token
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

        $filePath = Join-Path $root ([IO.Path]::GetRandomFileName() + '.3mf')
        Invoke-WebRequest -Method Get -Uri "$site/api/fjord-print-bridge/file/$($job.id)" -Headers $headers -OutFile $filePath -TimeoutSec 120
        if ((Get-Item -LiteralPath $filePath).Length -lt 100) { throw 'Le 3MF téléchargé est incomplet.' }

        $uri = 'bambu-connect://import-file?path=' + (ConvertTo-UrlPart $filePath) +
               '&name=' + (ConvertTo-UrlPart ([string]$job.file_name)) + '&version=1.0.0'
        Start-Process $uri
        Set-Content -LiteralPath $seenPath -Value ([string]$job.id) -Encoding ascii
        Invoke-RestMethod -Method Post -Uri "$site/api/fjord-print-bridge/ack/$($job.id)" -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 20 | Out-Null
        Write-Host "Fichier remis à Bambu Connect : $($job.file_name)" -ForegroundColor Cyan
        Write-Host 'Confirme l’imprimante, le matériau et le lancement dans Bambu Connect.' -ForegroundColor Yellow
    }
    catch {
        Write-Host 'Pont en attente ou erreur temporaire. Nouvelle tentative dans 10 secondes.' -ForegroundColor DarkYellow
        Start-Sleep -Seconds 10
    }
}
