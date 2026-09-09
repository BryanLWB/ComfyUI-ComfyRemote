$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$output = Join-Path $root 'artifacts'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$metadata = & git -C $root show HEAD:pyproject.toml
if ($LASTEXITCODE -ne 0) { throw 'Unable to read committed release version' }
$versionMatch = [regex]::Match(($metadata -join "`n"), '(?m)^version = "([0-9A-Za-z.+-]+)"$')
if (-not $versionMatch.Success) { throw 'Missing committed release version' }
$archive = Join-Path $output ("ComfyUI-ComfyRemote-" + $versionMatch.Groups[1].Value + '.zip')
if (Test-Path -LiteralPath $archive) { throw 'Archive exists; use a new output directory instead of overwriting a release.' }
& git -C $root archive --format=zip --prefix=ComfyUI-ComfyRemote/ -o $archive HEAD __init__.py comfyremote_connector web requirements.txt pyproject.toml README.md LICENSE CHANGELOG.md docs/privacy.md docs/server-setup.md docs/hosted-beta.md docs/release-0.2.0.md
if ($LASTEXITCODE -ne 0) { throw 'Unable to build preview archive' }
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $output 'SHA256SUMS.txt'), ($hash + '  ' + [IO.Path]::GetFileName($archive) + "`n"), [Text.Encoding]::ASCII)
Write-Output $archive
Write-Output $hash
