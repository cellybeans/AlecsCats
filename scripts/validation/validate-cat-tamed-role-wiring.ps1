Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Read-Json($relativePath) {
    $path = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing expected asset: $relativePath"
    }
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
}

function Assert-Equal($actual, $expected, $message) {
    if ($actual -ne $expected) {
        throw "$message Expected '$expected', got '$actual'."
    }
}

function Test-Property($object, $name) {
    return $null -ne $object -and $null -ne ($object.PSObject.Properties[$name])
}

$wildRoles = @{
    "Server/NPC/Roles/AlecsCats/Mobs/Cat.json" = "Cat_Pet"
    "Server/NPC/Roles/AlecsCats/Mobs/Cat_Longhair.json" = "Cat_Longhair_Pet"
    "Server/NPC/Roles/AlecsCats/Mobs/Cat_Shorthair.json" = "Cat_Shorthair_Pet"
    "Server/NPC/Roles/AlecsCats/Mobs/Cat_Bobtail.json" = "Cat_Bobtail_Pet"
}

foreach ($entry in $wildRoles.GetEnumerator()) {
    $role = Read-Json $entry.Key
    Assert-Equal $role.Parameters.TamedRoleId.Value $entry.Value "$($entry.Key) has an incorrect tame target."
}

$predatorTemplate = Read-Json "Server/NPC/Roles/AlecsCats/Templates/Template_Predator_Cat.json"
$petTemplate = Read-Json "Server/NPC/Roles/AlecsCats/Templates/Template_Cat_Pet.json"
Assert-Equal $predatorTemplate.TamedRoleId.Compute "TamedRoleId" "Template_Predator_Cat must expose TamedRoleId as a role field for Tamework RoleParam resolution."
Assert-Equal $petTemplate.TamedRoleId.Compute "TamedRoleId" "Template_Cat_Pet must expose TamedRoleId as a role field for Tamework RoleParam resolution."

$tempInteraction = Read-Json "Server/Tamework/Interactions/ACIntCatTemp.json"
$tameInteraction = $tempInteraction.Interactions | Where-Object { $_.Type -eq "Tame" } | Select-Object -First 1
if ($null -eq $tameInteraction) {
    throw "ACIntCatTemp.json is missing its Tame interaction."
}
Assert-Equal $tameInteraction.RoleParam "TamedRoleId" "ACIntCatTemp tame interaction must resolve the per-role tame target."

$setRoleEffects = @()
foreach ($interaction in $tempInteraction.Interactions) {
    if ((Test-Property $interaction "Effects") -and (Test-Property $interaction.Effects "SetRole")) {
        $setRoleEffects += $interaction.Effects.SetRole
    }
}
if ($setRoleEffects.Count -lt 2) {
    throw "ACIntCatTemp.json should keep feed and mode-cycle SetRole repair effects."
}
foreach ($effect in $setRoleEffects) {
    Assert-Equal $effect.RoleParam "TamedRoleId" "ACIntCatTemp SetRole effects must resolve the per-role tame target."
}

Write-Host "Cat tame role wiring validated."
