$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PetId = "codex-pet-ruo"

if ($env:CODEX_HOME) {
  $CodexHome = $env:CODEX_HOME
} else {
  $CodexHome = Join-Path $HOME ".codex"
}

$SourceDir = Join-Path (Join-Path $RepoRoot "pet-package") $PetId
$TargetDir = Join-Path (Join-Path $CodexHome "pets") $PetId
$SourceManifest = Join-Path $SourceDir "pet.json"
$SourceSpritesheet = Join-Path $SourceDir "spritesheet.webp"

if (!(Test-Path $SourceManifest) -or !(Test-Path $SourceSpritesheet)) {
  throw "Missing pet package files under: $SourceDir"
}

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
Copy-Item -Path $SourceManifest -Destination (Join-Path $TargetDir "pet.json") -Force
Copy-Item -Path $SourceSpritesheet -Destination (Join-Path $TargetDir "spritesheet.webp") -Force

Write-Host "Installed $PetId to $TargetDir"
Write-Host "Restart Codex to pick up the custom pet."
