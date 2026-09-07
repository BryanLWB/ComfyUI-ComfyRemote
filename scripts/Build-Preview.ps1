$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$output = Join-Path $root 'artifacts'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$archive = Join-Path $output 'ComfyUI-ComfyRemote-0.1.1.zip'
& git -C $root archive --format=zip --prefix=ComfyUI-ComfyRemote/ -o $archive HEAD __init__.py comfyremote_connector web requirements.txt pyproject.toml README.md LICENSE CHANGELOG.md docs
if ($LASTEXITCODE -ne 0) { throw 'Unable to build preview archive' }
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $output 'SHA256SUMS.txt'), ($hash + '  ' + [IO.Path]::GetFileName($archive) + "`n"), [Text.Encoding]::ASCII)
Write-Output $archive
Write-Output $hash
